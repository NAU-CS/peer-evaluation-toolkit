# Canvas setup: building the peer-evaluation machinery in your own course

This is a build guide. Follow it in order in a **development or sandbox copy** of your
course, then move it to the live section. Every step gives you the Canvas UI path and, where
the UI cannot do the job or does it wrong, the API call that can.

You do not need to write code to follow this guide. You do need to be willing to paste a
`curl` command into a terminal for roughly six of the steps, because Canvas's own interface
either hides the setting (assignment post policy), silently ignores it (same), or would take
an hour of clicking to do what one loop does (posting 24 quiz questions across four surveys).

Throughout, these placeholders stand in for your own values:

| Placeholder | Meaning | Where to find it |
|---|---|---|
| `$CANVAS` | your institution's Canvas host, e.g. `https://canvas.nau.edu` | your browser's address bar |
| `$TOKEN` | a personal API access token | Account → Settings → **+ New Access Token** |
| `$COURSE` | numeric course id | the `/courses/<id>` part of any course URL |
| `$GROUP_SET` | a group category id | `python3 scripts/discover.py --groups` |
| `$PARTICIPATION_GROUP` | assignment group the surveys live in | `/api/v1/courses/$COURSE/assignment_groups` |
| `$DELIVERABLE` | a group assignment id | `python3 scripts/discover.py --assignments` |
| `$ADJUSTMENT` | a 0-point adjustment assignment id | `python3 scripts/discover.py --assignments` |

Put these in your shell once per session. **Do not type the token on the command line** —
`export TOKEN=7~abc...` is appended verbatim to `~/.zsh_history` and stays there:

```bash
export CANVAS=https://canvas.your-university.edu
export COURSE=000000              # your numeric course id

read -rs TOKEN && export TOKEN     # paste at the prompt; nothing is echoed or saved
```

Better still on macOS, store it once in the keychain — encrypted at rest, unlocked by your
login, never in plaintext on disk — and pull it per session:

```bash
security add-generic-password -U -s canvas-api-token -a "$USER" -w
export TOKEN=$(security find-generic-password -s canvas-api-token -w)
```

The scripts in `scripts/` read that same keychain item automatically, so once it is stored
you do not need `$TOKEN` set at all for them.

The scripts read the host and course id from `scripts/course.yml`, and the token from the
keychain or `CANVAS_TOKEN` (see `scripts/ags/canvas.py`, which scrubs the token out of any error it
prints).

## Before you start: two things that will bite you later if you skip them

**Your course must be published before you can test negative scores.** Canvas returns 403 on
any attempt to grade a submission in an unpublished course *(gotcha 9)*. The whole mechanism
turns on posting a negative number to a 0-point assignment, and you cannot smoke-test that in
a draft shell. Plan to publish a sandbox course, or to run the smoke test in the live course
during the first week with your own test-student enrollment and the assignment unpublished
until after you have checked it.

**The shipped code assumes NAU-shaped email addresses.** Three places hard-code the pattern
"letters, then digits, then `@nau.edu`":

- `scripts/ags/peerreview.py`, line ~13: `NAU_EMAIL = re.compile(r"^[a-z]+[0-9]+@nau\.edu$")`
- `allocator/index.html`: `var NAU=/^[a-z]+[0-9]+@nau\.edu$/i`
- the example addresses inside `canvas/quiz-peer-evaluation-questions.json` and
  `canvas/quiz-peer-evaluation-description.html`

Edit all of them to match your institution before you deploy anything, or the allocator will
reject your students' own addresses and the parser will treat every ballot line as an unknown
address. This is the single most common way an adoption fails on day one.

---

## Step 1 — Assignment groups and weights

The adjustment assignment must live in the **same assignment group as the deliverables it
modifies**. That is not a stylistic preference; it is how the delta reaches the grade. A
weighted Canvas gradebook computes each group's percentage independently, so a delta parked in
a different group is multiplied by that group's weight instead of the project's, and if that
group has a small denominator the delta is wildly amplified.

**UI:** Assignments → three-dot menu → **Assignment Groups Weight** → check *Weight final
grade based on assignment groups*.

`canvas/examples/assignment-group-weights.json` is the origin course's real weighting, as a
worked reference: three project groups (15 / 15 / 25), Critical Writing 15, Quizzes 15,
Participation 10, Portfolio 5, Bonus 2, and two zero-weight groups used for organizing
non-graded material.

Decide now, and write it down:

- which assignment group holds each project arc's deliverables
- which low-stakes group will hold the peer-evaluation surveys themselves (the origin course
  uses *Participation and Attendance*, 10%; `scripts/course.yml` records it as
  `eval_quiz.assignment_group_id`)

**API:** `GET $CANVAS/api/v1/courses/$COURSE/assignment_groups?per_page=100` prints ids,
names and weights. Keep that output; you will need the group ids in steps 3 and 4.

## Step 2 — Group sets, self-signup, and a group limit

Create **one group set per project arc**, not one for the whole term. Doerry & Palmer's
central design point is that evaluation attaches to specific deliverables so that one bad week
does not taint a semester; re-forming teams per arc is the structural half of that, and it also
lets `peer_report.py` read a round's teams from exactly one group category. The origin course's
`scripts/course.yml` shows the shape:

```yaml
group_category_sets:
  tangible: 100001     # "Tangible Board Game"   <- your group_category_id
  construct: 100002    # "Construct Game"        <- your group_category_id
```

**UI:** People → **+ Group Set**. Name it after the arc. Check *Allow self sign-up*, set
*Group Structure* to the number of groups you want to exist up front, and set **Limit groups
to \_\_ members** to your target team size. Leave *Require group members to be in the same
section* off unless your section structure demands it.

**API:**

```bash
curl -X POST "$CANVAS/api/v1/courses/$COURSE/group_categories" \
  -H "Authorization: Bearer $TOKEN" \
  -d "name=Tangible Board Game" \
  -d "self_signup=enabled" \
  -d "group_limit=3" \
  -d "create_group_count=10"
```

Two honest limitations. `group_limit` enforces the **maximum only** — self-signup will happily
leave you a team of one and a team of two, and nothing in this toolkit fixes that
automatically. `peer_report.py` reports undersized teams; you resolve them by hand, in People,
before the round opens. And teams of two are a genuinely degraded case: there is no averaging,
and each partner can derive the other's rating from their own posted result. `scoring.py`
handles this with a `pair_policy` (default `clamp`, which narrows the factor range to
0.80–1.10; `neutralize` forces 1.00; `full` applies the normal clamp) and always attaches a
`team_of_2` flag saying the ratings are not anonymous. Choosing among those three is your
judgement call, not the tool's.

Record each group set's id — it appears in the URL when you open the set, and
`GET $CANVAS/api/v1/courses/$COURSE/group_categories` lists them.

## Step 3 — Configure the group deliverables

Every deliverable in the arc keeps **one shared grade for the whole team**. This is what lets
the syllabus say, truthfully, that all teammates receive the same grade on group work. All
individual differentiation happens in step 4.

**UI:** open each deliverable → Edit → under *Group Assignment*: check **This is a Group
Assignment**, pick the arc's group set, and leave *Assign Grades to Each Student
Individually* **unchecked**. Set *Allowed Attempts* to unlimited (leave the box unchecked).
Any one member submits on behalf of the team; Canvas does this by default once the assignment
is a group assignment.

**API:**

```bash
curl -X PUT "$CANVAS/api/v1/courses/$COURSE/assignments/$DELIVERABLE" \
  -H "Authorization: Bearer $TOKEN" \
  -d "assignment[group_category_id]=$GROUP_SET" \
  -d "assignment[grade_group_students_individually]=false" \
  -d "assignment[allowed_attempts]=-1"
```

### Manual posting, and why it is not optional

Set every group deliverable **and** every adjustment assignment to a manual post policy. Two
reasons, both practical. First, the adjustment is computed from a team grade that must already
be final — if a deliverable grade changes after you have run the round, every factor built on
it is stale. Second, a negative number appearing in a student's grades with no explanatory
comment attached yet is the single worst way for this system to introduce itself. Manual
posting lets you post score plus comment together, for the whole round at once.

**UI:** Gradebook → the assignment's column menu → **Grade Posting Policy** → *Manually*.

**API — and here is gotcha 7.** `assignment[post_manually]` over REST returns HTTP 200 and
changes nothing. It is silently ignored. The setting is only reachable through GraphQL:

```bash
curl -X POST "$CANVAS/api/graphql" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation { setAssignmentPostPolicy(input: {assignmentId: \"$ADJUSTMENT\", postManually: true}) { postPolicy { postManually } errors { message } } }"}'
```

Read `postPolicy.postManually` back out of the response. If you used REST and believed it, you
will discover the truth when the first adjustment posts itself to a student unannounced.

## Step 4 — The 0-point adjustment assignments

One adjustment assignment per **round** — that is, per set of deliverables you evaluate
together. The origin course runs four: draft and final for each of two arcs. The `rounds:` table in
`scripts/course.yml` maps each one to its survey, its adjustment assignment, its group set,
and the deliverable ids it covers.

Settings that matter:

| Setting | Value | Why |
|---|---|---|
| Points possible | **0** | see below — this is the load-bearing choice |
| Assignment group | the same one as the covered deliverables | so the delta is weighted like the project |
| Display grade as | Points | the gradebook shows a signed number |
| Submission type | No submission | students never submit here |
| Omit from final grade | **off** | omitting it removes the entire mechanism |
| Post policy | Manually | as in step 3 |

**UI:** Assignments → **+ Assignment**. Name it so a student can tell what it covers, e.g.
"Tangible Board Game — Peer Review Grade Adjustment (Parts 1–3)". Points **0**, Display Grade
as *Points*, Submission Type *No Submission*, and the arc's assignment group. Paste
`canvas/assignment-0pt-adjustment.html` into the description via the HTML editor (the `</>`
button); it is a real, student-tested description with the arithmetic, a five-row worked
example at one team grade, and the floor explained.

**API:**

```bash
curl -X POST "$CANVAS/api/v1/courses/$COURSE/assignments" \
  -H "Authorization: Bearer $TOKEN" \
  -d "assignment[name]=Tangible Board Game — Peer Review Grade Adjustment (Parts 1–3)" \
  -d "assignment[points_possible]=0" \
  -d "assignment[grading_type]=points" \
  -d "assignment[submission_types][]=none" \
  -d "assignment[assignment_group_id]=270111" \
  -d "assignment[published]=true" \
  --data-urlencode "assignment[description]@canvas/assignment-0pt-adjustment.html"
```

Then apply the manual post policy from step 3 to this assignment too.

### Why zero points, in numbers

Canvas computes an assignment group's percentage as `sum(scores) / sum(points_possible)` over
graded submissions, then multiplies by the group weight. If the adjustment assignment carries
the deliverable's own point value, those points join the **denominator**, and the mechanism
breaks in both directions at once. Measured on the origin course:

| Adjustment assignment worth | What happens to a team at 85% with factor 1.00 | Cost of a 0.60 factor |
|---|---|---|
| the deliverables' own points | group falls 85.0% → **54.24%** (denominator 67 → 105) | only **1.85** percentage points of final grade |
| **0 points** | unchanged at 85.0% | the full designed consequence |

Read the first row carefully: a student who did *precisely* their share, adjustment exactly 0,
loses thirty points of group percentage purely as an artifact of the denominator. With
`points_possible = 0` the delta lands in the numerator only and the denominator is untouched.

### How much of the arc to cover

This is the adopter's most consequential judgement call, and it costs nothing extra to get
right. With group work at 40% of the final grade and a team at 85%:

| Coverage | Loss for a persistent 0.60 student |
|---|---|
| Draft and Final deliverables only (78 of 153 group points) | 6.76 percentage points |
| the whole arc (all 153 points) | 13.41 percentage points |

Full-arc coverage roughly doubles the consequence at an identical number of assignment objects.
If the mechanism is meant to be consequential — and the paper's finding is that a
non-consequential version is not worth running — cover the whole arc.

## Step 5 — The peer-evaluation survey

Build it as a Canvas **graded survey**, not a quiz and not an ungraded survey. Graded gets you
a gradebook column for completion credit and a due date; ungraded gets you neither.

**UI:** Quizzes → **+ Quiz** → Quiz Type *Graded Survey*. Then:

| Setting | Value | Why |
|---|---|---|
| Quiz type | Graded Survey | completion credit + due date |
| Keep submissions anonymous | **unchecked** | see the warning below |
| Allow multiple attempts | on, **2** attempts | lets a student fix a bad total |
| Assignment group | your low-stakes completion group | the accountability lives in step 4, not here |
| Shuffle answers / time limit | off | free-text questions |

> **Do not check "Keep submissions anonymous."** The evaluation must be anonymous *to peers*,
> and it is: `peerreview.py`'s report renderer strips rater names from every comment before it
> reaches a student. Canvas's anonymous-survey option hides the respondent from *you*, which
> makes it impossible to know whose ballot is whose — and the entire round becomes unscorable.

**API:**

```bash
curl -X POST "$CANVAS/api/v1/courses/$COURSE/quizzes" \
  -H "Authorization: Bearer $TOKEN" \
  -d "quiz[title]=Peer Evaluation: Tangible Board Game (Parts 1–3)" \
  -d "quiz[quiz_type]=graded_survey" \
  -d "quiz[allowed_attempts]=2" \
  -d "quiz[anonymous_submissions]=false" \
  -d "quiz[assignment_group_id]=$PARTICIPATION_GROUP" \
  -d "quiz[due_at]=2026-10-08T23:59:00Z" \
  -d "quiz[published]=false" \
  --data-urlencode "quiz[description]@canvas/quiz-peer-evaluation-description.html"
```

`canvas/quiz-peer-evaluation-description.html` is the shipped description: the rules, the
N × 100 budget, the justification threshold, the email-format warning, and the anonymity
statement including the honest note that a two-person team can derive each other's ratings.

### The three questions

`canvas/quiz-peer-evaluation-questions.json` holds them exactly as authored, each worth 0.5
points (3 points total as shipped — completion credit, nothing more):

| Name | Type | Asks for |
|---|---|---|
| `Q1` | essay | **everything fed back to students.** The allocator iframe, and the combined `POINTS` / `STRENGTHS` / `IMPROVEMENTS` block the student pastes out of it |
| `Q2` | essay | **instructor only.** Justification for any rating below 80 or above 120 |
| `Q3` | essay | **instructor only.** Anything else the instructor should know |

The audience split is enforced, not just documented: the comment posted to a student is
rendered with `anonymous=True`, which emits nothing from an instructor-only question.

> **Gotcha 5, and it is the one that will silently ruin a round.** Canvas does **not** persist
> `position` on quiz questions created or updated through the API — it reads back as `None`.
> `peer_report.py` therefore keys every answer off `question_name`, matching `^Q(\d+)$`. The
> three questions **must** be named exactly `Q1`, `Q2`, `Q3`, in that meaning. Rename or
> reorder them and ballots will misparse with no error at all. The layout lives in
> `scripts/ags/survey.py`, which both `provision.py` and `peer_report.py` import, so the
> builder and the reader cannot drift apart; `provision.py verify` re-checks the live quiz
> against it.

Posting them by hand through the UI works but is tedious and easy to get wrong; the question
text for Q1 is several thousand characters of tables. The shipped client makes it a loop —
run this from the repository root once `scripts/course.yml` is filled in:

```python
import json, pathlib, sys
sys.path.insert(0, "scripts")
from ags.canvas import Canvas

COURSE, QUIZ = 000000, 000000   # your course id, your quiz id
c = Canvas()
for q in json.loads(pathlib.Path("canvas/quiz-peer-evaluation-questions.json").read_text()):
    payload = {"question_name": q["name"], "question_type": q["type"],
               "question_text": q["text"], "points_possible": q["points_possible"]}
    if q["answers"]:
        payload["answers"] = q["answers"]
    c.request("POST", f"courses/{COURSE}/quizzes/{QUIZ}/questions",
              json={"question": payload})
    print("posted", q["name"])
```

Then **read every question back** and check the text and the answers survived.

### Why the arithmetic is enforced outside Canvas

Canvas cannot validate one question against another. Neither Classic nor New Quizzes can do
it, and the "Formula" question type is not the escape hatch it looks like: its variables are
**Canvas-generated random numbers** (fields `name`/`min`/`max`/`scale`) and cannot reference a
student's answer to another question *(gotcha 3, verified by building one)*. So the survey
itself cannot check that the numbers in Q1 add up.

An earlier version of this toolkit worked around that with a numerical "total" question
accepting 200/300/400 *(gotcha 4)*. That is gone. It could not catch a legal total that was
wrong for the student's own team size — a three-person team typing 400 passed it — and it
added a field students could fail after the allocator had already told them they were
correct.

The allocator now does the enforcement, in front of the student: it refuses to produce output
until the points total their team size x 100, and it writes the strengths and improvements
into the same block. `peer_report.py` then re-checks both the arithmetic **and** the coverage
when it reads the ballot, so an allocation that omits a teammate is held rather than scored.

The shipped answers array is three exact answers:

```json
{"weight": 100, "numerical_answer_type": "exact_answer", "exact": 200.0}
```

> **Gotcha 6.** The file above records the shape Canvas *reads back*. On the write side the
> field names differ: send `numerical_answer_type: "exact_answer"` with `answer_exact` (and
> `answer_error_margin: 0`). If you ever switch to a tolerance range, the fields are
> `answer_range_start` and `answer_range_end` — writing `start`/`end` is **silently accepted
> and stores 0/0**, producing a question that accepts only zero. Always read the question back
> and confirm the three accepted values before you publish.

> **Gotcha 10.** Partial question updates can silently revert `question_text`. When you edit a
> question through the API, always send the **full** payload — name, type, text, points, and
> answers — as `embed_allocator.py` does.

> **Gotcha 8.** A quiz's cached `points_possible` does not recompute when you add or edit
> questions through the API. It will read 0 while the questions clearly total 3. **Unpublish
> and republish** the quiz to force the recount, and check the gradebook column afterwards.

## Step 6 — Host the allocator and embed it

The allocator (`allocator/index.html`) is a single dependency-free HTML file: the student picks
a team size, optionally starts from a pattern, enters one row per teammate including
themselves, and the Copy button stays disabled until the points total exactly team size × 100
and every address is valid and unique. It has no backend, stores nothing, and transmits
nothing.

> **Gotcha 1, the reason this step exists at all.** Canvas serves uploaded HTML files with
> `Content-Security-Policy: sandbox; script-src 'none'; object-src 'none'` and
> `Content-Disposition: attachment`. JavaScript in a Canvas-hosted file **never executes**.
> Canvas Files cannot host an interactive tool, full stop. External hosting plus an iframe is
> not a preference; it is the only route.

> **Gotcha 2, the reason the iframe works.** Canvas strips inline `<script>`, external
> `<script src>`, `onclick`, `<input>`, and `<form>` from page bodies and quiz text. It
> **permits** `<iframe>`, inline styles, `data-*` attributes, and `<details>`/`<summary>`.
> Iframes survive in page bodies, in quiz **descriptions**, and in quiz **question text** —
> which is why the allocator can sit directly above the question it feeds.

**Hosting on GitHub Pages:**

1. Put the repository on GitHub (a fork or a fresh repo containing `allocator/index.html`).
2. Edit the NAU email regex and the example addresses in `allocator/index.html` for your
   institution, and adjust the `PAT` pattern table if your teams are a different size.
3. Repo **Settings → Pages** → *Build and deployment* → Source *Deploy from a branch*, branch
   `main`, folder `/ (root)` if the file is at the root, or move/copy it to `/docs` and select
   that.
4. Wait for the Pages build to finish (Actions tab), then confirm the host is not stripping
   scripts:

```bash
curl -sI https://USERNAME.github.io/peer-evaluation-toolkit/ | grep -i -e content-security -e content-disposition
```

Any other static host works identically — the tool needs no server. What it must not do is
serve with `script-src 'none'` or as an attachment.

**Embedding.** Paste this anywhere Canvas keeps iframes — the top of Q1 is where it earns its
place:

```html
<iframe src="https://USERNAME.github.io/peer-evaluation-toolkit/"
        width="100%" height="1020"
        style="border:1px solid #c7cdd1;border-radius:6px;"
        title="Peer Evaluation Point Allocator" loading="lazy"></iframe>
```

`scripts/embed_allocator.py` does this for all four surveys plus the guide page in one command,
and it **preflights the URL before touching Canvas**: it refuses to embed unless the URL
returns HTTP 200, carries a real `<script>` tag, is not served as an attachment, and is not
under a `script-src 'none'` policy. `--remove` takes the iframes back out.

```bash
python3 scripts/embed_allocator.py https://USERNAME.github.io/peer-evaluation-toolkit/
```

`embed_allocator.py` takes the course and the survey ids from `scripts/course.yml`, the page
slug from the constant at the top of the file. A round whose `survey_quiz_id` is not filled
in yet is skipped with a note, and the guide page still gets the iframe.

Also publish `canvas/page-distribution-guide.html` as a Canvas **page** ("Point Distribution
Guide"). It is the no-JavaScript fallback: pre-computed distribution tables for teams of 2, 3,
and 4 where every row already sums correctly. Students on a phone with a blocked iframe, or
students who simply prefer a table, need this. The same tables are also inlined in Q1 behind
`<details>`-style panels, so the fallback survives even if the page does not.

## Step 7 — Modules and completion requirements

Put the round's items in one module, in the order a student meets them:

1. **Point Distribution Guide** (page) — requirement *view*
2. **Peer Evaluation** survey — requirement *submit*
3. **Peer Review Grade Adjustment** (the 0-point assignment) — **no requirement**, or *mark as
   done*

**UI:** Modules → **+** → pick the item type → then the module's *Edit* dialog → *Add
requirement*.

**API:**

```bash
curl -X POST "$CANVAS/api/v1/courses/$COURSE/modules/$MODULE/items" \
  -H "Authorization: Bearer $TOKEN" \
  -d "module_item[type]=Page" \
  -d "module_item[page_url]=point-distribution-guide" \
  -d "module_item[completion_requirement][type]=must_view"
```

> **Gotcha 12.** `must_mark_done` is the **only** requirement type that can complete a
> `not_graded` assignment. If you make the adjustment assignment ungraded — don't; you need to
> post scores to it — or if you have any other not-graded placeholder in the module,
> `must_submit` makes the item **permanently incomplete** and quietly blocks every student
> from finishing the module. The adjustment assignment as built in step 4 is graded with 0
> points and has no submission, so `must_submit` is wrong for it too: there is nothing to
> submit. Leave it with no requirement, or use `must_mark_done`.

> **Gotcha 11.** Removing a completion requirement is not obvious. `type: ""` returns HTTP
> 400. JSON `null` returns success and does nothing. The form that actually works is an empty
> object:

```bash
curl -X PUT "$CANVAS/api/v1/courses/$COURSE/modules/$MODULE/items/$ITEM" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"module_item":{"completion_requirement":{}}}'
```

## Step 8 — Smoke test, in a published course

This is the step people skip and then regret. It requires a published course *(gotcha 9:
Canvas refuses to grade submissions in an unpublished course with a 403)*, and it takes five
minutes.

1. Note a test student's current percentage in the project assignment group, and the group's
   denominator.
2. Enter **-1.50** by hand in the adjustment assignment's gradebook cell.
3. Confirm: the denominator did **not** change; the group percentage moved down by roughly
   1.50 divided by that denominator, times the group weight; the cell displays a negative
   number rather than refusing it.
4. Enter **+1.50** and confirm it moves the other way.
5. Clear the cell.

If the denominator changed, `points_possible` is not 0. If the percentage barely moved, the
assignment is in the wrong assignment group, or *omit from final grade* is on.

## Pre-launch checklist

Institution and code:

- [ ] the NAU email regex is replaced in `scripts/ags/peerreview.py`, `allocator/index.html`,
      and both Canvas HTML files
- [ ] example addresses in Q1, Q2, Q3 use your institution's form
- [ ] the test suite still passes after your edits — from `scripts/`, run
      `python3 -m unittest discover -s . -p 'test_*.py'` (83 tests: the scoring rules and the
      ballot parser, readable as a specification of the grade math)
- [ ] `scripts/.env` has `CANVAS_BASE_URL` and `CANVAS_TOKEN`, and is not committed

Structure:

- [ ] assignment groups are weighted, and you have written down which group holds each arc
- [ ] one group set per arc, self-signup on, `group_limit` = target team size
- [ ] every team has at least 3 members, or you have consciously chosen a `pair_policy`
- [ ] every group deliverable: group assignment on, *grade individually* **off**, attempts
      unlimited
- [ ] every group deliverable and every adjustment assignment: post policy manual, verified by
      reading `postPolicy.postManually` back from GraphQL, not by trusting REST *(7)*

The adjustment assignments:

- [ ] `points_possible` is exactly **0** on every one
- [ ] each sits in the **same assignment group** as the deliverables it covers
- [ ] *omit from final grade* is off; display grade as Points
- [ ] coverage decision made deliberately — whole arc, or a documented subset
- [ ] description pasted from `canvas/assignment-0pt-adjustment.html`, with the arc's real
      deliverable names and points substituted

The surveys:

- [ ] quiz type is `graded_survey`
- [ ] **"Keep submissions anonymous" is unchecked**
- [ ] 2 attempts allowed
- [ ] questions named exactly `Q1`, `Q2`, `Q3` — Q1 student-facing, Q2 and Q3 instructor-only *(5)*
- [ ] `python3 scripts/provision.py verify` passes for every round
- [ ] every question's `question_text` read back intact after any edit *(10)*
- [ ] unpublished and republished once, and the gradebook column shows the expected points
      *(8)*
- [ ] due dates set, and each round's due date is **after** the covered deliverables are
      graded

The allocator:

- [ ] hosted somewhere that serves real JavaScript; `curl -I` shows no `script-src 'none'`
      and no `attachment` *(1)*
- [ ] embedded in each survey's Q1 (and the guide page), verified by loading the quiz as a
      student *(2)*
- [ ] Point Distribution Guide page published as the no-JavaScript fallback

Modules and the live check:

- [ ] module items in order: guide page, survey, adjustment assignment
- [ ] no `must_submit` requirement on any not-graded or no-submission item *(12)*
- [ ] smoke test done in a **published** course: ±1.50 moves the grade the expected amount and
      leaves the denominator alone *(9)*
- [ ] one full dry run of the round script against real submissions before anything is posted
      (`peer_report.py` is dry-run by default and writes a report file; it writes to Canvas
      only with `--post`)

## What this setup does not give you

- **No cross-question validation in Canvas.** The allocator enforces the total before the
  student copies anything out, and `peer_report.py` re-checks it. Canvas itself catches
  wrong for the student's team size, and not a ballot that hits the target while omitting the
  student themselves. Both of those are caught after the fact, by `check_budget` in
  `peerreview.py`, and land in your report as problems to resolve.
- **No automatic team repair.** Self-signup produces undersized teams. You fix them by hand.
- **No anonymity on a team of two.** Arithmetic, not policy. Say so out loud, in the
  assignment description, as `canvas/assignment-0pt-adjustment.html` does.
- **Nothing in `scripts/` is course-specific.** Every id, threshold and round lives in
  `scripts/course.yml`, which you create by copying `course.example.yml`. It is gitignored,
  and it is the one file you fill in. The scripts are identical for every adopter, so you
  can pull an update without re-applying your edits.
- **Your token is not in that file.** It is read from the macOS keychain, or from
  `CANVAS_TOKEN`. So a config file is safe to hand a colleague as a starting point, and a
  leaked config file is not a leaked credential.
- **Grade every covered deliverable before you run a round.** The adjustment is
  `team_earned x factor - team_earned`; an ungraded deliverable silently shrinks
  `team_earned` and every adjustment with it. That is not something to discover at 11pm on
  a grading night.
