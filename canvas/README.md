# Canvas templates

Ready-to-paste HTML captured from a live, working course, with course-specific
strings replaced by tokens. Substitute these before use:

| Token | Meaning | Example |
|---|---|---|
| `{{ARC_NAME}}` | the project's student-facing name | `Tangible Board Game` |
| `{{INSTRUCTOR_NAME}}` | how students should refer to you | `Dr. Duval` |
| `{{EMAIL_DOMAIN}}` | your institutional address suffix | `@nau.edu` |
| `{{EMAIL_EXAMPLE}}` | a realistic example address | `abc123@nau.edu` |
| `{{COURSE_ID}}` | your numeric Canvas course id | `123456` |

## Files

| File | What it is |
|---|---|
| `assignment-0pt-adjustment.html` | Description for a 0-point adjustment assignment, including the worked table showing what number gets entered as the grade |
| `quiz-peer-evaluation-description.html` | Description for the peer-evaluation graded survey |
| `quiz-peer-evaluation-questions.json` | The three questions, generated from `scripts/ags/survey.py`. Q1 is student-facing; Q2 and Q3 are instructor-only |
| `page-distribution-guide.html` | The JS-free fallback: valid point distributions in a DesignPLUS accordion |
| `examples/assignment-group-weights.json` | A real weighted-group layout for reference |

## Two notes

**The markup uses DesignPLUS classes** (`dp-content-block`, `dp-callout`, `dp-panels-wrapper`).
Without the DesignPLUS add-on these degrade to plain semantic HTML — readable, just
unstyled. Nothing depends on it functionally.

**You do not need to paste any of this by hand.** `scripts/provision.py` builds all of
it from `course.yml`. These files are here for reading, for cherry-picking wording,
and for anyone who would rather click than script.
