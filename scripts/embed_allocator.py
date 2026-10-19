#!/usr/bin/env python3
"""Embed the GitHub Pages allocator into the four peer-evaluation quizzes.

    python3 embed_allocator.py https://USERNAME.github.io/peer-evaluation-toolkit/
    python3 embed_allocator.py <url> --remove     # take the iframes back out

Verifies the URL serves real JavaScript before touching Canvas.
"""
import argparse, json, os, pathlib, re, sys
import requests
from dotenv import load_dotenv

HERE = pathlib.Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))
from ags.canvas import Canvas, CanvasError
from ags.config import load as load_config, ConfigError  # noqa: E402

# Everything course-specific comes from course.yml, same as the other scripts.


def load_quiz_targets(cfg):
    """The surveys to embed into, from course.yml. A round whose survey has not been
    created yet is skipped: the page still gets the iframe either way."""
    out = []
    for key, r in cfg.rounds.items():
        if r.survey_quiz_id:
            out.append((r.survey_quiz_id, r.title))
        else:
            print(f"note: {key} has no survey_quiz_id yet — skipping "
                  f"(run `provision.py apply`, or fill it in with `discover.py`)")
    return out


def iframe(url):
    return (f'{MARK}<iframe src="{url}" width="100%" height="1020" '
            f'style="border:1px solid #c7cdd1;border-radius:6px;" '
            f'title="Peer Evaluation Point Allocator" loading="lazy"></iframe></p>'
            f'<p style="font-size:0.9em;">If the tool does not load, '
            f'<a href="{url}" target="_blank" rel="noopener">open it in a new tab</a>. '
            f'It is a calculator &mdash; nothing you type in it is submitted or recorded.</p>')


def strip_embed(html):
    """Remove a previously embedded block, matching on the data attribute Canvas keeps."""
    out = re.sub(r'<p[^>]*' + MARK_ATTR + r'[^>]*>.*?</p>', "", html or "", flags=re.S)
    # the explanatory note that follows the iframe
    return re.sub(r'<p[^>]*>\s*If the tool does not load.*?</p>', "", out, flags=re.S)


def preflight(url):
    """Refuse to embed a URL that will not actually run the tool."""
    try:
        r = requests.get(url, timeout=30)
    except Exception as e:
        return False, f"could not fetch: {e}"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    csp = r.headers.get("content-security-policy", "")
    if "script-src 'none'" in csp:
        return False, f"host blocks scripts (CSP: {csp[:60]})"
    if "Point Allocator" not in r.text:
        return False, "page does not look like the allocator"
    if "<script>" not in r.text:
        return False, "no script tag in the served HTML"
    if r.headers.get("content-disposition", "").startswith("attachment"):
        return False, "served as a download, not a page"
    return True, (f"HTTP 200, {len(r.text)} bytes, script present, "
                  f"CSP={csp or 'none'}, type={r.headers.get('content-type','?')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="the GitHub Pages URL, e.g. https://user.github.io/peer-evaluation-toolkit/")
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--skip-preflight", action="store_true")
    ap.add_argument("--config", help="path to course.yml (default: auto-detect)")
    a = ap.parse_args()
    url = a.url.rstrip("/") + "/"
    c = Canvas()

    if not a.remove:
        ok, why = preflight(url)
        print(f"preflight: {'PASS' if ok else 'FAIL'} -- {why}")
        if not ok and not a.skip_preflight:
            sys.exit("refusing to embed a URL that will not run. "
                     "Wait for Pages to finish building, or pass --skip-preflight.")

    block = iframe(url)
    try:
        cfg = load_config(getattr(args, "config", None))
    except ConfigError as e:
        sys.exit(f"config: {e}")
    CID = cfg.course_id
    targets = [("page", PAGE, None)] + [("quiz", qid, title)
                                        for qid, title in load_quiz_targets(cfg)]

    for kind, ident, title in targets:
        if kind == "page":
            obj = c.get(f"courses/{CID}/pages/{ident}")
            body = obj.get("body") or ""
            new = strip_embed(body)
            if not a.remove:
                new = new.replace("<h3>How to use this</h3>", block + "<h3>How to use this</h3>", 1) \
                      if "<h3>How to use this</h3>" in new else new + block
            c.request("PUT", f"courses/{CID}/pages/{ident}", data={"wiki_page[body]": new})
            live = c.get(f"courses/{CID}/pages/{ident}")["body"]
            print(f"  page {ident}: iframe {'removed' if a.remove else 'present'} = "
                  f"{(MARK_ATTR in live) != a.remove}")
        else:
            for q in c.paginate(f"courses/{CID}/quizzes/{ident}/questions"):
                if q.get("question_name") != "Q1":
                    continue
                txt = q["question_text"]
                new = strip_embed(txt)
                if not a.remove:
                    new = block + new
                c.request("PUT", f"courses/{CID}/quizzes/{ident}/questions/{q['id']}",
                          json={"question": {"question_name": "Q1", "question_text": new,
                                             "question_type": q["question_type"],
                                             "points_possible": q["points_possible"]}})
                live = [x for x in c.paginate(f"courses/{CID}/quizzes/{ident}/questions")
                        if x["question_name"] == "Q1"][0]["question_text"]
                print(f"  {str(title)[:42]:<42} iframe {'removed' if a.remove else 'present'} = "
                      f"{(MARK_ATTR in live) != a.remove}")
                break
    print("\ndone" + ("" if a.remove else f" -- embedded {url}"))


if __name__ == "__main__":
    try:
        main()
    except ConfigError as e:
        raise SystemExit(f"config: {e}")
    except CanvasError as e:
        raise SystemExit(f"Canvas: {e}")
