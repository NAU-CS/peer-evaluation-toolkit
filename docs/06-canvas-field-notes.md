# Canvas field notes

This file is for whoever automates the Canvas side of this toolkit — or of anything
else. It is not written for the instructor; it is written for the person holding an
API token.

Every item below was verified empirically against a live Canvas instance while
building this toolkit (Canvas LMS, `canvas.nau.edu`, 2026). None of it is inferred
from documentation. Several of these behaviours are *not* documented, and four of
them return HTTP success while doing nothing at all — which is the single most
important thing on this page, and the reason for the closing section.

Canvas is a moving target. Treat the specific payloads as a starting point and the
verification discipline as the durable part: **read the state back after every write
that matters.**

## Quick index

| # | If you see this | The rule |
|---|---|---|
| 1 | JavaScript in a file you uploaded to Canvas never runs | Canvas Files serve `script-src 'none'` + `Content-Disposition: attachment`. Host interactive tools externally. |
| 2 | Your `<script>` / `<input>` / `onclick` vanished from a page body | Canvas sanitises page and quiz HTML. `<iframe>` and inline styles survive. |
| 3 | You are trying to make a quiz validate one answer against another | No quiz engine can. "Formula" questions use Canvas-generated variables, not student responses. |
| 4 | You need one numeric field constrained to a small set of legal values | A single numerical question accepts multiple exact answers. This is the only native cross-check. |
| 5 | Your parser assigns the wrong answer to the wrong question | `position` is not persisted on API-created questions; it reads back `None`. Key off `question_name`. |
| 6 | A numerical range question accepts only `0` | You wrote `start`/`end`. The real fields are `answer_range_start` / `answer_range_end`. |
| 7 | `post_manually` returns 200 and stays `false` | REST silently ignores it. Use the GraphQL `setAssignmentPostPolicy` mutation. |
| 8 | Quiz `points_possible` is stale after editing questions | The value is cached. Unpublish, then republish. |
| 9 | Grading calls 403 in a course you own | Canvas refuses to grade in an unpublished course. Publish before smoke-testing. |
| 10 | A question's text reverted after an unrelated edit | Partial question updates can drop fields. Always send the full question payload. |
| 11 | You cannot clear a module item's completion requirement | `type:""` → 400; JSON `null` → silent no-op. Send `{"completion_requirement": {}}`. |
| 12 | A 0-point module item is permanently incomplete | Only `must_mark_done` can complete a `not_graded` assignment. |

---

## 1. Canvas Files cannot host an interactive tool

**Symptom.** You upload a self-contained HTML file with inline JavaScript to Canvas
Files, link it from a page, and the page renders — but nothing is interactive.
Buttons do nothing. The browser console shows a CSP violation, or nothing at all
because the file downloaded instead of rendering.

**Cause.** Canvas serves files from the Files area with:

```
Content-Security-Policy: sandbox; script-src 'none'; object-src 'none'
Content-Disposition: attachment
```

`script-src 'none'` means inline and external JavaScript in that document never
executes, under any circumstances. `Content-Disposition: attachment` means the
browser is being told to download rather than render. This is deliberate — Canvas
Files is a hostile-upload surface and it is locked down accordingly. There is no
course setting, account setting, or file flag that lifts it.

**Fix.** Host the tool anywhere that serves real HTML with scripts (GitHub Pages is
free, static, and adequate) and embed it into Canvas with an `<iframe>`. Iframes are
not stripped (see #2).

**Verify before you embed.** A broken embed is invisible in the Canvas editor — the
iframe renders as blank space. This toolkit's embedder refuses to write to Canvas
until it has fetched the URL and confirmed it will actually run
(`scripts/embed_allocator.py`, `preflight()`): HTTP 200, a `<script>` tag present in
the served bytes, no `script-src 'none'` in the CSP header, no `attachment`
disposition, and a known string from the page body. Four of those five checks exist
because a real failure produced a silently blank iframe.

```python
r = requests.get(url, timeout=30)
if "script-src 'none'" in r.headers.get("content-security-policy", ""):
    return False, "host blocks scripts"
if r.headers.get("content-disposition", "").startswith("attachment"):
    return False, "served as a download, not a page"
if "<script>" not in r.text:
    return False, "no script tag in the served HTML"
```

Run this against your Pages URL immediately after the first deploy; GitHub Pages
serves a 404 for a minute or two after a fresh enable, and a 404 embedded in a quiz
question looks exactly like a working embed until a student opens it.

## 2. What Canvas strips from HTML, and what it keeps

**Symptom.** You paste rich HTML into a page body, quiz description, or quiz
question text via the API. The write returns 200. You read it back and your
`<script>` block, `<form>`, `<input>`, or `onclick` attribute is simply gone — no
error, no warning. The rest of the markup survived.

**Cause.** Canvas runs user HTML through a sanitiser on save. This applies to
content set through the API exactly as it does to content typed in the RCE.

| Element / attribute | Page body | Quiz description | Quiz question text |
|---|---|---|---|
| inline `<script>` | stripped | stripped | stripped |
| `<script src>` | stripped | stripped | stripped |
| `onclick` and other inline handlers | stripped | stripped | stripped |
| `<input>`, `<form>` | stripped | stripped | stripped |
| `<iframe src>` | **kept** | **kept** | **kept** |
| inline `style` attributes | kept | kept | kept |
| `data-*` attributes | kept | kept | kept |
| `<details>` / `<summary>` | kept | kept | kept |

**Fix.** Anything interactive goes in an iframe pointed at external hosting. Anything
merely *presentational* — collapsible sections, styled tables, callouts — can be done
natively with `<details>`/`<summary>` and inline styles, and should be, because
iframes do not resize to their content and do not inherit the reader's Canvas theme.

Two practical consequences for this toolkit. First, the interactive point allocator
lives on GitHub Pages and is injected as an iframe into the quiz's *first question
text* as well as the description, because a student who lands mid-quiz never sees the
description again. Second, the fallback distribution tables
(`canvas/page-distribution-guide.html`, and the tables baked into
`canvas/quiz-peer-evaluation-questions.json`) are plain sanitiser-safe HTML with no
scripting, so that a student with iframes blocked, a locked-down browser, or a bad
network still has a way to produce a legal ballot.

## 3. No quiz engine can validate one answer against another

**Symptom.** You want the quiz itself to enforce "these three numbers must add up to
300." You go looking for a way to reference question 1's response from question 4.
There isn't one.

**Cause.** Neither Classic Quizzes nor New Quizzes evaluates across questions. Each
question is scored in isolation against its own answer set. The "Formula question"
type looks like the answer and is not: its variables are **Canvas-generated random
values** used to build the prompt, with the schema

```json
{"variables": [{"name": "a", "min": 1.0, "max": 10.0, "scale": 0}]}
```

Canvas picks `a`, substitutes it into the question text, and evaluates your formula
against the student's single response. There is no syntax by which a formula can read
another question's response, because at generation time no response exists. Verified
by building one and trying.

**Fix.** Give up on native cross-question validation and use three layers instead:

1. **Client-side, outside Canvas.** The allocator iframe (#1) does the real
   arithmetic enforcement — it will not enable its copy button until the numbers total
   exactly `team size x 100`, every address matches the expected form, and no address
   is duplicated.
2. **One native single-field constraint.** See #4.
3. **Server-side, at scoring time.** The authoritative check is in Python and refuses
   to guess. `ags.scoring.validate_ballot()` holds a ballot for human review if the
   total is more than 10% off target rather than rescaling it, and
   `ags.peerreview.check_budget()` separately verifies that every team member appears
   exactly once — because summing to `N x 100` is necessary but not sufficient. A
   student who omits themselves and inflates two teammates hits the target exactly.

Design the quiz on the assumption that ballots arrive malformed, because they will.

## 4. One numerical question can accept several exact answers

**Symptom.** You assume a numerical question has a single correct answer, so you
cannot express "200 or 300 or 400, depending on team size, and nothing else."

**Cause / discovery.** A numerical question's `answers` array may contain multiple
entries, each independently correct with `weight: 100`. Canvas marks the response
correct if it matches *any* of them. This is the only cross-checking Canvas will do
for you natively, and it is worth using.

**What works** (this was the survey's old checksum question; the toolkit no longer ships
one, but the gotcha is real and bites any numerical question):

```json
{
  "name": "Q6",
  "type": "numerical_question",
  "points_possible": 0.5,
  "answers": [
    {"weight": 100, "numerical_answer_type": "exact_answer", "exact": 200.0},
    {"weight": 100, "numerical_answer_type": "exact_answer", "exact": 300.0},
    {"weight": 100, "numerical_answer_type": "exact_answer", "exact": 400.0}
  ]
}
```

The student is asked to add up the numbers they typed into the free-text allocation
question and enter the total here. It cannot check that the total matches their own
lines — only that it is a legal total for *some* team size. That still catches the
most common arithmetic slip at the moment the student can still fix it, and the
scoring script closes the remaining gap by comparing the stated total against both
what the lines actually add to and what the student's real team size requires
(`scripts/peer_report.py`, the `stated` block: three distinct error messages for
"not a legal total", "does not match your lines", and "legal but wrong for a team of
N").

Note the small, equal `points_possible` on each question: the survey is
graded for *completion*, and correctness of the checksum is not what earns the credit
(the quiz's total is set in `scripts/course.yml` under `eval_quiz`). Set
`allowed_attempts` to at least 2 so a student can fix a rejected total without an
instructor unlocking anything.

## 5. `position` is not persisted on questions created via the API

**Symptom.** The worst failure mode in this whole project. You create quiz questions
through the API with explicit `position` values, everything returns 200, the quiz
looks correct in the browser — and then your parser silently attributes the
justification text to the allocation field, or reads the checksum as a comment.
Nobody notices because there is no error; the numbers are just wrong for some
students.

**Cause.** Canvas does not store `position` for questions created or updated through
the API. `GET /courses/:id/quizzes/:id/questions` reads it back as `None`. The
browser renders questions in an order derived elsewhere, so the UI gives no hint that
the field is empty.

**Fix.** Never key off `position`. Put a stable identifier in `question_name` when you
author the question, and parse that. This toolkit names its questions `Q1`..`Q3` and
maps them by regex:

```python
# scripts/peer_report.py -- answer_map()
qs = {}
for q in c.paginate(f"courses/{CID}/quizzes/{quiz_id}/questions"):
    m = re.fullmatch(r"Q(\d+)", (q.get("question_name") or "").strip())
    qs[q["id"]] = int(m.group(1)) if m else q.get("position")   # fallback, usually None
```

Anything that reads back `None` is skipped rather than guessed at. If you inherit a
quiz built in the UI, its questions *do* have positions — but do not mix the two
sources of truth in one parser.

Two related notes on reading submissions. Ask for `include[]=submission_history` and
pick the attempt with the highest `attempt` number yourself; with multiple attempts
allowed you cannot assume the top-level submission carries the latest answers. And a
free-text answer may arrive under `text` or under `answer` depending on question
type, so check both.

## 6. Numerical range answers: `answer_range_start`, not `start`

**Symptom.** You author a numerical question with a range answer. The write returns
200. Students report the question rejects everything. You inspect it and the accepted
range is `0` to `0`.

**Cause.** The correct field names are `answer_range_start` and `answer_range_end`.
Writing `start` / `end` is *silently accepted* — unknown keys are dropped, the range
fields default to zero, and you get a question that accepts only the number zero.

**Fails silently:**

```json
{"weight": 100, "numerical_answer_type": "range_answer", "start": 200, "end": 400}
```

**Works:**

```json
{"weight": 100, "numerical_answer_type": "range_answer",
 "answer_range_start": 200, "answer_range_end": 400}
```

Always read the question back and assert on the stored bounds. This toolkit ended up
not needing ranges — three exact answers (#4) express the constraint better — but the
trap is generic to any numerical question you build by script.

## 7. `post_manually` over REST is ignored; use GraphQL

**Symptom.** You set a manual post policy on an assignment so that grades are not
released to students the instant you write them. `PUT /courses/:id/assignments/:id`
with `assignment[post_manually]=true` returns 200 with a normal assignment object.
The value is unchanged. Read it back: still `false`. Your negative adjustments went
live to students the moment your script wrote them.

For a peer-evaluation workflow this is not a cosmetic bug. Adjustments must be
reviewed — held ballots, `UNANIMOUS_LOW` flags, and coverage failures all need human
judgement before anyone sees a number.

**Cause.** REST accepts the parameter and drops it. Post policy is implemented in
Canvas's GraphQL layer.

**Fails silently:**

```
PUT /api/v1/courses/:course_id/assignments/:assignment_id
    assignment[post_manually]=true
→ 200, post_manually still false
```

**Works** — `POST /api/graphql` with the same bearer token:

```graphql
mutation {
  setAssignmentPostPolicy(input: {assignmentId: "<ADJUSTMENT_ID>", postManually: true}) {
    postPolicy { postManually }
    errors { attribute message }
  }
}
```

Note that `assignmentId` is a **string** in GraphQL. Check both the returned
`postPolicy.postManually` and the `errors` array — a GraphQL endpoint returns HTTP
200 for a request that failed, with the failure in the body. Then read the
assignment back over REST as an independent confirmation.

A course-wide default post policy exists as a separate mutation
(`setCoursePostPolicy`), and setting it at the course level is the more robust move
if the whole course should behave this way: an assignment created later inherits it,
whereas per-assignment calls are one more thing to remember.

## 8. Quiz `points_possible` is cached and does not recompute

**Symptom.** You add, remove, or repoint quiz questions through the API. Every call
succeeds. The quiz's own `points_possible` still reports the old total, so the
gradebook column and the assignment group denominator are wrong.

**Cause.** `points_possible` on the quiz object is a denormalised cache, recomputed
by Canvas's own save paths — which API question edits do not trigger.

**Fix.** Unpublish and republish the quiz. That forces recomputation.

```
PUT /api/v1/courses/:id/quizzes/:qid   quiz[published]=false
PUT /api/v1/courses/:id/quizzes/:qid   quiz[published]=true
GET /api/v1/courses/:id/quizzes/:qid   → check points_possible
```

Caveat worth knowing before you do this on a live course: unpublishing a quiz that
already has submissions is restricted, and unpublishing hides the quiz from students
for the interval between the two calls. Do all question edits first, then flip the
publish state once, then verify. Never leave the unpublish and the republish in
separate script runs.

## 9. Canvas will not grade in an unpublished course

**Symptom.** You build the whole pipeline in an unpublished course to keep it away
from students, then try to write a score to a submission and get `403 Forbidden` on an
account you fully control.

**Cause.** Grading requires a published course. There is no override.

**Consequence to plan for.** The behaviour you most want to smoke-test — does a
*negative* score on a 0-point assignment actually do what the grade model says it
does? — cannot be tested until the course is published. Publish early, keep the
assignments themselves unpublished or the module locked, and do your end-to-end test
with a Test Student or a co-instructor's dummy enrolment before real students exist.

Also make sure your client does not mistake this 403 for throttling. Canvas signals
rate limiting with **either** `429` **or** `403` with a "throttled" body, so a naive
"retry all 403s" loop turns a hard permission error into a 30-second silent stall
followed by a misleading message. This toolkit's client distinguishes them by
inspecting the body (`scripts/ags/canvas.py`):

```python
if r.status_code == 429 or (r.status_code == 403 and "throttled" in r.text.lower()):
    time.sleep(2 ** attempt)     # back off
    continue
if r.status_code >= 400:
    raise CanvasError(...)       # a real 403 fails fast, with the body attached
```

## 10. Partial quiz-question updates can revert `question_text`

**Symptom.** You update one property of an existing quiz question — its points, its
name, an answer — and afterwards the question text is missing, truncated, or reverted
to an earlier version. No error was returned.

**Cause.** The question update endpoint does not reliably merge; omitted fields can be
written as empty rather than left alone.

**Fix.** Always send a complete question payload: read the question, mutate the field
you care about in the object you just read, and PUT the whole thing back. This is what
the iframe embedder does even though it only touches the text:

```python
c.request("PUT", f"courses/{CID}/quizzes/{quiz_id}/questions/{q['id']}",
          json={"question": {"question_name":    "Q1",
                             "question_text":    new_text,
                             "question_type":    q["question_type"],
                             "points_possible":  q["points_possible"]}})
```

Then read it back and assert your marker is present. The embedder does exactly that
and prints a per-question true/false, which is how you find out that one of four
quizzes silently did not take.

Two adjacent encoding notes, since this endpoint differs from most of the API:

- Quiz question writes want **nested JSON** (`json={"question": {...}}`).
- Most other endpoints want **form-encoded bracket notation**
  (`data={"submission[posted_grade]": -2.97}`). Mixing these up produces 200s that
  change nothing.
- Make your edits **idempotent**. The embedder strips any previous copy of its own
  block by regex before inserting a new one, so running it twice does not stack two
  iframes.

## 11. Clearing a module item's completion requirement

**Symptom.** You want to remove a completion requirement from a module item. The two
obvious attempts both fail, in different and equally unhelpful ways.

**Cause.** `type: ""` is rejected outright; JSON `null` is accepted and ignored.

| Payload | Result |
|---|---|
| `{"module_item": {"completion_requirement": {"type": ""}}}` | `400 Bad Request` |
| `{"module_item": {"completion_requirement": null}}` | `200`, requirement unchanged — a silent no-op |
| `{"module_item": {"completion_requirement": {}}}` | **Works** — requirement cleared |

An empty object, not an empty string and not null. Read the module item back and
confirm `completion_requirement` is absent.

## 12. Only `must_mark_done` can complete a `not_graded` item

**Symptom.** You add the 0-point adjustment assignment to a module with a
`must_submit` requirement. It can never be satisfied, so every student's module — and
any prerequisite chain behind it — is permanently incomplete.

**Cause.** The adjustment assignment has `submission_types: ["not_graded"]` (or
otherwise takes no submission). There is nothing for a student to submit, so
`must_submit` never fires. `must_view` completes on view but is a weak signal, and
`min_score` is meaningless against a 0-point assignment.

**Works:**

```json
{"module_item": {"completion_requirement": {"type": "must_mark_done"}}}
```

`must_mark_done` gives the student a "Mark as done" button and, usefully, a record
that they acknowledged the item — appropriate for a page whose entire job is to
explain why a number appeared in their gradebook. If you would rather the item impose
no gate at all, clear the requirement using #11 instead of picking a weaker type.

---

## 13. Three ways to read a quiz submission and come back empty

All three of these fail *silently* -- no exception, no error field, just an
empty or useless result. Together they made a round of 27 real ballots report
`ballots received: 0`.

**13a. Some collections arrive inside an envelope.** Most Canvas list endpoints
return a bare JSON array, but a few wrap it:

```
GET /courses/:id/quizzes/:qid/submissions
  -> {"quiz_submissions": [ ... ]}                 # not [ ... ]
GET /quiz_submissions/:id/questions
  -> {"quiz_submission_questions": [ ... ]}
```

A pagination helper that yields a non-list body as a single item hands the
caller one dict that looks like a submission but has no `user_id`. If the caller
tolerates missing keys, every ballot silently parses as empty. `Canvas._unwrap`
unwraps a single-key envelope and treats anything else as a real single object.

**13b. The envelope may carry a sideload key.** Adding `include[]` can turn the
body into `{"quiz_submissions": [...], "meta": {...}}`, so "exactly one key" is
too strict a test. Ignore `meta`/`pagination` before deciding.

**13c. Quiz answers are not on the quiz submission.** This is the big one.
`/quizzes/:qid/submissions` accepts `include[]=submission_history` and
**silently ignores it** -- a 200 with rows that contain no `submission_data` at
all. The answers are only reachable through the Submissions API on the quiz's
backing assignment:

```
aid = GET /courses/:id/quizzes/:qid           -> ["assignment_id"]
GET /courses/:id/assignments/:aid/submissions?include[]=submission_history
  -> [ { "user_id": ..., "submission_history": [ { "submission_data": [...] } ] } ]
```

Take the entry with the highest `attempt` that actually has `submission_data`;
earlier attempts can be present but empty.

## 14. Essay answers are HTML, not text

A free-text answer comes back as stored rich text:

```html
<p>POINTS<br>abc123@nau.edu = 100<br>def456@nau.edu = 110</p>
```

Any parser that splits on newlines sees **one line** and matches nothing. Convert
`<br>` and block-level closing tags to newlines, strip remaining tags, then
`html.unescape` (students really do type `&` and `<`). `ags/peerreview.html_to_text`
does this; `parse_block` assumes it has already run.

## 15. "Rejected ballot" is not "did not submit"

A student whose ballot fails validation still *submitted* one. If the pipeline
drops invalid ballots before scoring, the scorer never sees that rater and flags
them `did_not_submit_evaluation` -- which is both false and consequential, since
completion credit and the instructor's follow-up list key off that flag. Record
the ballot as `Ballot(valid=False, problems=[...])` instead of skipping it, so
"submitted but not counted" stays distinguishable from "submitted nothing".

## Appendix: writing the adjustment

The grade-model rationale for a 0-point assignment lives in the grading design doc;
the API mechanics are three lines. Score and comment go in one call, form-encoded:

```python
c.request("PUT", f"courses/{CID}/assignments/{ADJ_ID}/submissions/{user_id}",
          data={"submission[posted_grade]": -2.97,          # negative is fine
                "comment[text_comment]":    anonymised_report})
```

Points worth knowing:

- **Negative scores are accepted** on an assignment with `points_possible: 0`, and
  land in the numerator without touching the denominator. This is the whole
  mechanism. Confirm it in a published course (#9) before you trust it.
- **The comment is the audit trail.** Each student's posted comment carries their
  mean, rater count, factor, the arithmetic, and their teammates' written feedback
  with names stripped — see `examples/worked-round.md` for exactly what a student
  receives.
- **Nothing is written unless you ask.** `scripts/peer_report.py` is a dry run by
  default; it writes a report file and prints a summary, and only `--post` touches
  Canvas. Given that a bad run posts negative grades to a whole class, an
  automation script here should default to read-only and make the destructive path
  explicit.
- **Post policy first.** Combine with #7 so the writes land held rather than live.

## The general lesson: verify by reading state back

Six of the twelve behaviours above returned HTTP success while doing nothing, doing
something different, or undoing something else:

| Failure shape | Examples |
|---|---|
| 200, field ignored entirely | `post_manually` (#7), `null` completion requirement (#11) |
| 200, wrong value stored | `start`/`end` range answers stored as 0/0 (#6) |
| 200, an unrelated field clobbered | partial question update wipes `question_text` (#10) |
| 200, value never written in the first place | `position` on API-created questions (#5) |
| 200, derived value left stale | quiz `points_possible` (#8) |
| 200, content sanitised out | stripped `<script>`, `<input>`, `<form>` (#2) |

None of these produce a traceback. Several of them produce *wrong grades* rather than
a broken page, which is worse, because a broken page gets reported by a student on day
one and a subtly misparsed ballot does not get reported at all.

Practical rules that follow:

1. **Assert on read-back, not on the response.** After any write you would be upset to
   lose, `GET` the object and check the specific field. Cheap; catches every row in
   that table.
2. **Treat 200 as "the request was well-formed", not "the change happened."** This is
   doubly true of GraphQL, which returns 200 with errors in the body.
3. **Send full payloads on merge-unsafe endpoints.** Read-modify-write beats patching
   a field you hope is independent.
4. **Never key on a field you did not write and verify.** `position` is the cautionary
   tale; the fix — a stable name you control — generalises.
5. **Default to dry run.** Print what would change, diff it, then re-run with a flag.
6. **Make writes idempotent.** Strip-then-insert rather than append, so a re-run
   converges instead of accumulating.
7. **Preflight external dependencies.** A blank iframe and a working iframe look
   identical in an editor; fetch the URL and inspect the headers before embedding it in
   four quizzes.
8. **Publish the course before you believe any grading test.** Half this pipeline
   cannot be exercised in an unpublished course.

### Client-level notes

Small things, all in `scripts/ags/canvas.py`, that any Canvas script needs and that
are easy to get wrong:

- **Pagination is via the `Link` header**, not a page count in the body. Follow
  `rel="next"` until it is absent, with `per_page=100`. Reading only the first page is
  a silent-truncation bug that appears the moment a course exceeds 100 students, which
  is precisely when nobody is checking.
- **403 is ambiguous** — throttling or permission. Distinguish by body (#9).
- **Scrub the token out of every error message.** Errors get pasted into tickets and
  chat logs. One `str.replace` on the way out of the client is enough:
  `text.replace(self._token, "<TOKEN>")`.
- **Keep the token in a `.env` that is not in version control**, and give it the
  narrowest role that works. A token that can write grades can write all of them.

### Files in this repo worth reading as examples

| Path | What it demonstrates |
|---|---|
| `scripts/ags/canvas.py` | pagination, 403-vs-throttle, token scrubbing |
| `scripts/peer_report.py` | reading answers via the assignment Submissions API, keying by `question_name`, dry-run default, posting scores + comments |
| `scripts/embed_allocator.py` | preflighting an external URL, full-payload question updates, read-back verification, idempotent edits |
| `canvas/quiz-peer-evaluation-questions.json` | multi-exact-answer numerical question, sanitiser-safe rich HTML |
| `scripts/ags/scoring.py` | the validation Canvas cannot do for you |
