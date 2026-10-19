"""Peer-review reconciliation and report generation.

Ports the identity-reconciliation logic from the Google-Forms era Swift script
(email-keyed records, fuzzy email correction, cross-team collision guards, ghost
records for non-submitters) onto the zero-sum capstone model in ags.scoring.

Pure functions and dataclasses only -- no Canvas calls -- so it is unit-testable.
"""
from dataclasses import dataclass, field
import html, re

# Institutional addresses are letters, then digits, then the domain
# (e.g. abc123@example.edu). Both the pattern and the repairs below are built
# from whatever domain the course config supplies -- call configure() once at
# startup. The default is deliberately a placeholder, not anyone's real domain.
DEFAULT_DOMAIN = "example.edu"
DOMAIN = DEFAULT_DOMAIN
EMAIL_RE = re.compile(r"^[a-z]+[0-9]+@" + re.escape(DEFAULT_DOMAIN) + r"$")


def configure(domain):
    """Point email parsing at your institution's domain. Safe to call repeatedly."""
    global DOMAIN, EMAIL_RE
    DOMAIN = (domain or DEFAULT_DOMAIN).strip().lstrip("@").lower()
    EMAIL_RE = re.compile(r"^[a-z]+[0-9]+@" + re.escape(DOMAIN) + r"$")
    return EMAIL_RE


# Backwards-compatible alias; EMAIL_RE is the name to use.
NAU_EMAIL = EMAIL_RE
FUZZY_THRESHOLD = 2

NULLISH = {"", "n/a", "na", "n.a.", "n.a", "none", "nothing", "no comment", "no comments",
           "no other comments", "no further comments", "-", "--", ".", "nope", "nil"}


def meaningful(s):
    """Return the trimmed string, or None for empty / N-A style filler."""
    if s is None:
        return None
    t = " ".join(str(s).split())
    return None if t.lower() in NULLISH else t


def levenshtein(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def normalize_email(raw):
    """Lowercase, strip, and repair the most common shapes of a mistyped address."""
    if raw is None:
        return ""
    e = "".join(str(raw).split()).lower().strip(".,;:<>()[]\"'")
    if not e or e in NULLISH:
        return ""
    at = "@" + DOMAIN
    tld = "." + DOMAIN.rsplit(".", 1)[-1]        # ".edu"
    if e.endswith(at[:-1]) and not e.endswith(at):   # truncated: "@example.ed"
        e = e[: -len(at) + 1] + at
    if e.endswith(at + at[-1]):                      # doubled: "@example.eduu"
        e = e[:-1]
    if "@" not in e:                                 # bare institutional id
        e = e + at
    if e.endswith(at + tld):                         # doubled tld
        e = e[: -len(tld)]
    return e


def correct_email(raw, known):
    """Map a possibly-mistyped address onto a known roster address.

    Order: exact -> unique prefix within the same domain -> nearest Levenshtein
    neighbour inside FUZZY_THRESHOLD. Returns (resolved, was_corrected, note).
    """
    e = normalize_email(raw)
    if not e:
        return "", False, "empty"
    if e in known:
        return e, False, "exact"

    if "@" in e:
        typed, _, domain = e.partition("@")
        domain = "@" + domain
        cands = [k for k in known
                 if k.endswith(domain) and typed and k.split("@")[0].startswith(typed)
                 and len(k.split("@")[0]) > len(typed)]
        if len(cands) == 1:
            return cands[0], True, f"unique prefix of {cands[0]}"
        if len(cands) > 1:
            return e, False, f"ambiguous prefix ({len(cands)} candidates)"

    best, best_d = None, 10 ** 9
    for k in known:
        d = levenshtein(k, e)
        if d < best_d:
            best_d, best = d, k
    if best is not None and best_d <= FUZZY_THRESHOLD:
        return best, True, f"levenshtein {best_d} from {best}"
    return e, False, "unresolved"


@dataclass
class PeerComment:
    rater_email: str
    rater_name: str
    strengths: str = ""
    improvements: str = ""
    other: str = ""
    points: float = None


@dataclass
class StudentRecord:
    email: str
    name: str = ""
    team: str = ""
    user_id: int = None
    submitted: bool = False
    self_points: float = None
    self_strengths: str = ""
    self_improvements: str = ""
    justification: str = ""
    received: list = field(default_factory=list)   # list[PeerComment]
    problems: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    factor: float = None
    mean_received: float = None
    adjustment: float = None
    # Set from the scoring result. `received` carries PEER comments only (a student
    # should not be shown their own self-praise as teammate feedback), so deriving the
    # rating count from it is wrong in two directions: it misses the self-rating, and
    # it counts raters whose ballots were later rejected as invalid. Trust the scorer.
    n_ratings_counted: int = None
    self_counted: bool = None

    @property
    def n_raters(self):
        return len([p for p in self.received if p.points is not None])


SEP = "=" * 60
SUB = "-" * 60


def render_report(rec, arc, phase, team_score, covered_points, anonymous=True):
    """Build the pasteable block. anonymous=True is the student-facing copy."""
    L = [SEP]
    L.append(f"PEER REVIEW REPORT{'' if anonymous else '  (INSTRUCTOR COPY -- NAMES SHOWN)'}")
    L.append(f"{arc} -- {phase}")
    L.append(f"Student: {rec.name or '(unknown)'}" + ("" if anonymous else f"  <{rec.email}>"))
    if not anonymous:
        L.append(f"Team: {rec.team or '(unknown)'}")
    L.append(SUB)

    if rec.factor is None:
        L.append("No adjustment could be computed (no ratings received).")
    else:
        if rec.n_ratings_counted is not None:
            n = rec.n_ratings_counted
            self_incl = bool(rec.self_counted)
        else:
            n = rec.n_raters
            self_incl = any(p.rater_email == rec.email and p.points is not None
                            for p in rec.received) or rec.self_points is not None
        L.append(f"Ratings received: {n}" +
                 (" (including your own self-rating)" if self_incl
                  else " (you did not submit an evaluation, so your own rating is not among them)"))
        L.append(f"Mean rating      : {rec.mean_received:.1f}")
        L.append(f"Factor           : {rec.factor:.2f}"
                 + ("  [clamped]" if rec.factor in (0.60, 1.10) else ""))
        L.append(SUB)
        L.append(f"Team earned {team_score:g} of {covered_points:g} on the covered deliverables.")
        L.append(f"{team_score:g} x {rec.factor:.2f} = {team_score * rec.factor:.2f}")
        sign = "+" if (rec.adjustment or 0) >= 0 else ""
        L.append(f"ADJUSTMENT POSTED: {sign}{rec.adjustment:.2f}")
        if abs(rec.adjustment or 0) < 0.005:
            L.append("  (no change -- your team reported an even distribution of effort)")

    def bullets(getter):
        out = []
        for p in rec.received:
            t = meaningful(getter(p))
            if not t:
                continue
            out.append(f"  - {t}" if anonymous else f"  - [{p.rater_name or p.rater_email}] {t}")
        return out or ["  (none)"]

    if rec.received:
        L.append(SUB); L.append("WHAT YOUR TEAMMATES SAID YOU DID WELL:")
        L += bullets(lambda p: p.strengths)
        L.append(SUB); L.append("AREAS FOR IMPROVEMENT:")
        L += bullets(lambda p: p.improvements)
        if not anonymous:
            L.append(SUB); L.append("OTHER COMMENTS (instructor only):")
            L += bullets(lambda p: p.other)

    if not anonymous:
        L.append(SUB)
        L.append(f"Submitted own evaluation: {'YES' if rec.submitted else 'NO'}")
        if rec.self_points is not None:
            L.append(f"Self-rating: {rec.self_points:g}")
            peers = [p.points for p in rec.received
                     if p.points is not None and p.rater_email != rec.email]
            if peers:
                pm = sum(peers) / len(peers)
                L.append(f"Peer mean excluding self: {pm:.1f}  (gap {rec.self_points - pm:+.1f})")
        if meaningful(rec.self_strengths):
            L.append(f"Self -- contribution: {meaningful(rec.self_strengths)}")
        if meaningful(rec.self_improvements):
            L.append(f"Self -- could improve: {meaningful(rec.self_improvements)}")
        if meaningful(rec.justification):
            L.append(f"Justification given: {meaningful(rec.justification)}")
        if rec.flags:
            L.append(SUB); L.append("FLAGS:")
            L += [f"  ! {f}" for f in rec.flags]
        if rec.problems:
            L.append("BALLOT PROBLEMS:")
            L += [f"  ! {p}" for p in rec.problems]
    L.append(SEP)
    return "\n".join(L)


# --------------------------------------------------------------------------
# Free-text block parsing (single-question allocation format)
# --------------------------------------------------------------------------

_ALLOC = re.compile(
    r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+|\b[a-z]+[0-9]+\b)"   # address or bare NAU id
    r"\s*(?:=|:|-|\u2013|\u2014|\t|\s{2,})\s*"             # = : - en/em dash tab or gap
    r"(-?\d+(?:\.\d+)?)")                                    # the number


def parse_allocation(text, known):
    """Parse 'email = points' lines from one free-text answer.

    Returns (ratings, notes) where ratings maps resolved email -> int points.
    Tolerates =, :, -, tabs, and wide whitespace as the separator, and accepts a
    bare NAU id without the domain. Notes record every repair and rejection.
    """
    ratings, notes = {}, []
    if not text:
        return ratings, ["no allocation text supplied"]
    for raw_line in re.split(r"[\r\n;]+", str(text)):
        line = raw_line.strip()
        if not line:
            continue
        m = _ALLOC.search(line)
        if not m:
            if meaningful(line):
                notes.append(f"could not read a 'email = points' pair from: {line[:60]!r}")
            continue
        who, num = m.group(1), m.group(2)
        resolved, corrected, note = correct_email(who, known)
        if resolved not in known:
            notes.append(f"unknown address {who!r} ({note})")
            continue
        if corrected:
            notes.append(f"corrected {who!r} -> {resolved} ({note})")
        try:
            val = float(num)
        except ValueError:
            notes.append(f"unreadable number for {resolved}: {num!r}")
            continue
        if val != int(val):
            notes.append(f"{resolved}: {val} rounded to whole points")
        if resolved in ratings:
            notes.append(f"{resolved} listed more than once; keeping the last value")
        ratings[resolved] = int(round(val))
    return ratings, notes


def parse_comments(text, known):
    """Parse 'email: comment' lines into {resolved_email: comment}."""
    out, notes = {}, []
    if not text or not meaningful(text):
        return out, notes
    for raw_line in re.split(r"[\r\n]+", str(text)):
        line = raw_line.strip()
        if not line:
            continue
        m = re.match(r"\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+|[a-z]+[0-9]+)\s*[:=\-\u2013]\s*(.+)", line)
        if not m:
            notes.append(f"unattributed comment line: {line[:60]!r}")
            continue
        resolved, _, _ = correct_email(m.group(1), known)
        body = meaningful(m.group(2))
        if resolved in known and body:
            out[resolved] = (out.get(resolved, "") + " " + body).strip()
    return out, notes


def check_budget(ratings, members=None, team_size=None):
    """The arithmetic check, plus coverage.

    Summing to N*100 is necessary but NOT sufficient: a student who omits themselves
    and inflates two teammates still hits the target. So when `members` is supplied we
    also require every team member to appear exactly once, and nobody else.
    """
    if members is not None:
        members = list(members)
        n = len(members)
    else:
        n = int(team_size or 0)
        members = None
    target = n * 100
    total = sum(ratings.values())
    missing = sorted(set(members) - set(ratings)) if members is not None else []
    extra = sorted(set(ratings) - set(members)) if members is not None else []
    ok = (total == target) and not missing and not extra
    problems = []
    if total != target:
        problems.append(f"lines total {total}, but a team of {n} must distribute exactly {target}")
    if missing:
        problems.append(f"no line for {', '.join(missing)} -- every team member must be rated, "
                        f"including yourself")
    if extra:
        problems.append(f"{', '.join(extra)} is not on this team")
    return dict(target=target, total=total, ok=ok, off_by=total - target,
                off_pct=(abs(total - target) / target * 100.0) if target else 0.0,
                missing=missing, extra=extra, problems=problems)


def html_to_text(raw):
    """Flatten a Canvas rich-text answer into plain line-separated text.

    Canvas stores essay answers as HTML, so the calculator's block arrives as
    `<p>POINTS<br>a@nau.edu = 100<br>...</p>`. Without this the whole ballot
    collapses onto one line and every allocation fails to parse.
    """
    if not raw:
        return ""
    t = str(raw)
    # Line-level tags become newlines before anything else is stripped.
    t = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", t)
    t = re.sub(r"(?i)</\s*(p|div|li|tr|h[1-6])\s*>", "\n", t)
    t = re.sub(r"(?i)<\s*(p|div|li|tr|h[1-6])\b[^>]*>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)            # any remaining tags
    t = html.unescape(t)
    t = t.replace("\u00a0", " ")            # &nbsp;
    lines = [ln.strip() for ln in t.splitlines()]
    out, blank = [], False
    for ln in lines:                          # collapse runs of blank lines
        if ln:
            out.append(ln)
            blank = False
        elif out and not blank:
            out.append("")
            blank = True
    return "\n".join(out).strip()


def parse_block(text, known):
    """Parse the calculator's combined output out of ONE free-text answer.

    Expected shape (headings case-insensitive, order-independent, extra blank lines fine):

        POINTS
        abc123@nau.edu = 110
        ...
        STRENGTHS
        abc123@nau.edu: built the deck
        IMPROVEMENTS
        abc123@nau.edu: n/a

    Falls back gracefully: if no headings are present the whole text is treated as an
    allocation block, so a student who pastes only their numbers still scores.
    Returns (ratings, strengths, improvements, notes).
    """
    if not text:
        return {}, {}, {}, ["no response supplied"]
    HEAD = re.compile(r"^\s*(POINTS|ALLOCATION|STRENGTHS|STRENGTH|IMPROVEMENTS|IMPROVEMENT|"
                      r"AREAS FOR IMPROVEMENT)\s*:?\s*$", re.I)
    buckets, cur = {"points": [], "strengths": [], "improvements": []}, None
    for line in re.split(r"[\r\n]+", str(text)):
        m = HEAD.match(line)
        if m:
            h = m.group(1).upper()
            cur = ("points" if h in ("POINTS", "ALLOCATION")
                   else "strengths" if h.startswith("STRENGTH")
                   else "improvements")
            continue
        if line.strip():
            buckets[cur if cur else "points"].append(line)
    notes = []
    if cur is None:
        notes.append("no POINTS/STRENGTHS/IMPROVEMENTS headings found; "
                     "treated the whole answer as the point allocation")
    ratings, n1 = parse_allocation("\n".join(buckets["points"]), known)
    strengths, n2 = parse_comments("\n".join(buckets["strengths"]), known)
    improvements, n3 = parse_comments("\n".join(buckets["improvements"]), known)
    return ratings, strengths, improvements, notes + n1 + n2 + n3
