"""The peer-evaluation survey: one definition, used to build it AND to read it.

This module exists because the builder and the reader drifted apart once already.
`provision.py` was still creating a six-question survey (points, strengths,
improvements, justification, instructor, checksum) long after the allocator
started emitting one combined block and the survey was cut to three questions.
Nothing failed loudly: `peer_report.py` went on reading Q2 as the justification
and Q3 as the instructor channel, so an adopter's strengths were silently filed
as justifications. Both sides now import this file, so they cannot disagree.

The layout is three questions:

    Q1  everything that is fed back to students -- the allocator's combined
        POINTS / STRENGTHS / IMPROVEMENTS block.
    Q2  instructor only -- justification for ratings outside 80-120.
    Q3  instructor only -- anything else.

`audience` is not decoration. `peer_report.render_report(anonymous=True)` is the
copy posted to the student, and it renders nothing from an INSTRUCTOR question.
If you add a question, set its audience honestly.
"""
from dataclasses import dataclass

STUDENTS = "students"
INSTRUCTOR = "instructor"

DEFAULT_ALLOCATOR_URL = "https://nau-cs.github.io/peer-evaluation-toolkit/allocator/"


@dataclass(frozen=True)
class Question:
    key: str          # stable name the code refers to; never shown to anyone
    position: int     # 1-based; also the Canvas question_name ("Q1")
    title: str
    audience: str
    body: str         # callable name resolved below

    @property
    def canvas_name(self):
        return f"Q{self.position}"


def _q1(cfg):
    url = cfg.get("allocator_url") or DEFAULT_ALLOCATOR_URL
    ex = cfg.get("email_example", "abc123@example.edu")
    stem = ex.split("@")[0]
    dom = "@" + ex.split("@")[1] if "@" in ex else "@example.edu"
    a, b, c = stem, "bcd456", "cde789"
    return (
        f'<p data-allocator-embed="1"><iframe src="{url}" width="100%" height="1180" '
        f'style="border:1px solid #c7cdd1;border-radius:6px;" '
        f'title="Peer Evaluation Helper" loading="lazy"></iframe></p>'
        f'<p style="font-size:0.9em;">If the tool does not load, '
        f'<a href="{url}" target="_blank">open it in a new tab</a>.</p>'
        f'<p><strong>Use the tool above, then paste its output here.</strong> It will not let '
        f'you finish until your points add up correctly, and it writes the strengths and '
        f'improvements into the same block. Everything the tool needs to explain is inside it '
        f'&mdash; open the two grey sections at the top if you want the detail.</p>'
        f'<p>Your answer should look like this:</p><pre>POINTS\n'
        f'{a}{dom} = 110\n{b}{dom} = 100\n{c}{dom} = 90\n\n'
        f'STRENGTHS\n{b}{dom}: built the card deck\n{c}{dom}: wrote the rulebook\n\n'
        f'IMPROVEMENTS\n{b}{dom}: n/a\n{c}{dom}: missed the second build session</pre>'
    )


def _q2(cfg):
    lo = cfg.get("justify_below", 80)
    hi = cfg.get("justify_above", 120)
    return (
        f'<p><strong>Justification.</strong> Required for any rating you gave below {lo} or '
        f'above {hi}. Explain it in terms of tasks assigned and tasks completed &mdash; not '
        f'personality. Name the person by email.</p>'
        f'<p>Write <code>n/a</code> if every rating you gave was between {lo} and {hi}.</p>'
    )


def _q3(cfg):
    return (
        '<p><strong>Anything else your instructor should know?</strong> Never shared with your '
        'teammates. Write <code>n/a</code> if nothing.</p>'
        '<p>If something on your team needs attention <em>now</em> rather than at grading time, '
        'email directly &mdash; do not wait for this form.</p>'
    )


_BODIES = {"block": _q1, "justification": _q2, "instructor": _q3}

QUESTIONS = (
    Question("block",         1, "Peer feedback",            STUDENTS,   "block"),
    Question("justification", 2, "Justification",            INSTRUCTOR, "justification"),
    Question("instructor",    3, "For the instructor only",  INSTRUCTOR, "instructor"),
)

# Position lookups, so no caller hardcodes 1/2/3.
POSITION = {q.key: q.position for q in QUESTIONS}
BY_POSITION = {q.position: q for q in QUESTIONS}


def question_text(key, cfg):
    """Render one question's HTML body for this course's config."""
    return _BODIES[key](cfg or {})


def build(cfg):
    """Every question, ready to POST to Canvas, in order."""
    return [
        {"question_name": q.canvas_name,
         "question_type": "essay_question",
         "question_text": question_text(q.key, cfg),
         "points_possible": 0}
        for q in QUESTIONS
    ]
