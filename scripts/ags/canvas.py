"""Minimal Canvas REST client: pagination, retries, and no token leakage in errors."""
import binascii
import os
import time
import re
import shutil
import subprocess
try:
    import requests
except ImportError:                      # pragma: no cover
    requests = None                      # only needed to actually talk to Canvas
from urllib.parse import urljoin

class CanvasError(RuntimeError):
    pass


KEYCHAIN_SERVICE = os.environ.get("CANVAS_KEYCHAIN_SERVICE", "canvas-api-token")

_env_loaded = False


def _load_env_once():
    """Load the nearest .env so ad-hoc one-liners behave like the CLIs.

    Without this, `python3 -c "...Canvas()..."` fails on CANVAS_BASE_URL even though
    every entry-point script works, which is a confusing difference to debug.
    Walks up from this file, then from the working directory.
    """
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    here = os.path.dirname(os.path.abspath(__file__))
    seen = set()
    for base in (here, os.getcwd()):
        d = base
        while d and d not in seen:
            seen.add(d)
            f = os.path.join(d, ".env")
            if os.path.isfile(f):
                load_dotenv(f, override=False)
                return
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent


def token_from_keychain(service=None):
    """Read the Canvas token out of the macOS login keychain.

    Preferred over a .env file: the keychain is encrypted at rest, unlocked only by
    your login, and the value never sits in plaintext on disk or in shell history.
    Returns None on any non-macOS platform, or if no such item exists.
    """
    if not shutil.which("security"):
        return None
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", service or KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    val = out.stdout.strip()
    if not val:
        return None
    # `security -w` prints the value as HEX when it contains bytes it will not emit raw.
    # Taking that at face value yields a confusing 401 instead of an obvious error.
    if len(val) % 2 == 0 and all(ch in "0123456789abcdefABCDEF" for ch in val):
        try:
            val = binascii.unhexlify(val).decode("utf-8")
        except Exception:
            pass
    return val or None


class Canvas:
    def __init__(self, base_url=None, token=None, timeout=30):
        _load_env_once()
        self.base_url = (base_url or os.environ.get("CANVAS_BASE_URL", "")).rstrip("/")
        # Resolution order: explicit argument, environment (.env included), then keychain.
        self._token = token or os.environ.get("CANVAS_TOKEN", "") or token_from_keychain() or ""
        # A value that is clearly not a Canvas token is worth catching here: the common
        # cause is a clipboard mix-up, and a 401 three calls later does not say so.
        if self._token and not re.match(r"^[0-9]+~[A-Za-z0-9]", self._token):
            preview = self._token[:28].replace("\n", " ")
            raise CanvasError(
                "The stored credential does not look like a Canvas access token.\n"
                f"  Got {len(self._token)} characters beginning: {preview!r}\n"
                "  A Canvas token looks like 7~aBcDeF... (digits, a tilde, then letters "
                "and numbers).\n"
                "  Check what is actually in the keychain item or .env -- a clipboard "
                "mix-up is the usual cause.")
        if not self.base_url:
            raise CanvasError("CANVAS_BASE_URL is not set")
        if not self._token:
            raise CanvasError(
                "No Canvas token found. Store one in the keychain:\n"
                f"    security add-generic-password -U -s {KEYCHAIN_SERVICE} "
                "-a \"$USER\" -w\n"
                "  The prompt shows nothing as you paste. If it keeps saving an empty\n"
                "  value, use Keychain Access.app (File > New Password Item) instead,\n"
                f"  with item name '{KEYCHAIN_SERVICE}'.\n"
                "Or set CANVAS_TOKEN in a .env file with chmod 600.")
        self.timeout = timeout
        if requests is None:
            raise CanvasError(
                "The `requests` package is required to talk to Canvas.\n"
                "    pip3 install -r requirements.txt")
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {self._token}"})

    def _scrub(self, text):
        """Never let the token appear in output."""
        return text.replace(self._token, "<TOKEN>") if self._token else text

    def request(self, method, path, **kw):
        url = path if path.startswith("http") else urljoin(self.base_url + "/api/v1/", path.lstrip("/"))
        for attempt in range(5):
            r = self.s.request(method, url, timeout=self.timeout, **kw)
            # Canvas throttles with 403 + a Forbidden body, or 429
            if r.status_code == 429 or (r.status_code == 403 and "throttled" in r.text.lower()):
                time.sleep(2 ** attempt)
                continue
            if r.status_code >= 400:
                raise CanvasError(
                    f"{method} {self._scrub(url)} -> {r.status_code}: {self._scrub(r.text[:600])}"
                )
            return r
        raise CanvasError(f"rate limited after retries: {self._scrub(url)}")

    def get(self, path, **params):
        return self.request("GET", path, params=params).json()

    def paginate(self, path, per_page=100, **params):
        """Yield every item across all pages, following Link rel=next."""
        params = {**params, "per_page": per_page}
        r = self.request("GET", path, params=params)
        while True:
            body = r.json()
            page = self._unwrap(body)
            if page is None:
                # A genuine single object (not a paginated collection).
                yield body
                return
            for item in page:
                yield item
            nxt = self._next_link(r.headers.get("Link", ""))
            if not nxt:
                return
            r = self.request("GET", nxt)

    @staticmethod
    def _unwrap(body):
        """Return the list of items in a page body, or None if not a collection.

        Most Canvas collection endpoints return a bare JSON array, but a few
        wrap it in a single-key envelope -- e.g. /quizzes/:id/submissions
        returns {"quiz_submissions": [...]} and /quiz_submissions/:id/questions
        returns {"quiz_submission_questions": [...]}. Yielding the envelope
        makes callers silently see one unusable item instead of N real ones.
        """
        if isinstance(body, list):
            return body
        if isinstance(body, dict):
            # Canvas may sideload a pagination envelope alongside the collection.
            keys = [k for k in body if k not in ("meta", "pagination")]
            if len(keys) == 1 and isinstance(body[keys[0]], list):
                return body[keys[0]]
        return None

    @staticmethod
    def _next_link(link_header):
        for part in link_header.split(","):
            m = re.match(r'\s*<([^>]+)>\s*;\s*rel="next"', part)
            if m:
                return m.group(1)
        return None
