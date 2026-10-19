# Accountable Grading System

A peer-evaluation toolkit for Canvas group projects. Teams keep **one shared grade** on every
deliverable, and individual contribution is handled separately: each student's teammates
distribute a fixed pool of points, that becomes a multiplier on the team's earned credit, and the
difference is posted as a signed number on a **zero-point** assignment. The mechanism is
consequential, the arithmetic is auditable, and the syllabus can still honestly say "all teammates
receive the same grade on the deliverable."

It is four things: a student-facing calculator, a set of Canvas templates, a scoring library with
101 tests, and one command that runs a whole evaluation round end to end.

## The problem it solves

Group work rewards the wrong people. The usual fixes fail in specific, familiar ways:

- **A peer-evaluation slice of the course grade** (worth a few percent) is not consequential enough
  to change behaviour. Doerry & Palmer measured this and abandoned it.
- **Splitting the team grade per student** breaks the promise that the team shares a grade, and
  turns every deliverable into a negotiation.
- **A term-long "teamwork" score** produces negative carry-over: one bad fortnight follows a student
  to the final grade with no way to recover.
- **Free-form 1-5 ratings** are not zero-sum, so raters inflate everyone and the signal disappears.

This toolkit implements the alternative: a fixed budget per rater, attached to a specific
deliverable window, applied as a direct multiplier. On the origin course a student who was
persistently rated at the floor lost **13.41 percentage points** of final grade — enough to matter,
bounded enough to survive an appeal.

## Is this for you?

**Yes, if** you run team projects of 2-4 students, with **multiple graded deliverables** across
several weeks, and you already grade the team as a unit. Two or more evaluation rounds per project
is where this earns its keep: students see a low factor early, and can act on it before the round
that carries the most points.

**No, if** it is one group assignment, once. The setup cost (a group set, a survey, a zero-point
assignment, a hosted calculator, a config file) is not worth it for a single deliverable — use a
rubric line item and your judgement.

**Also no, if** your teams are larger than about six. The distribution tables, the anonymity
guarantees, and the flag thresholds are all tuned for small teams; nothing breaks mathematically,
but the guidance stops fitting.

You need Canvas **Classic Quizzes** (graded surveys). New Quizzes has no API that exposes
per-question responses this way, so the round runner cannot read them.

## What a student sees

1. **A calculator.** [`allocator/index.html`](allocator/index.html) — one self-contained HTML file,
   no dependencies, no backend, nothing transmitted. The student picks a team size (2/3/4), can
   start from a named pattern ("One did clearly less", "One barely appeared" — every pattern already
   totals correctly), and types one row per teammate *including themselves*. It refuses to produce
   output until the points total exactly team size x 100, every address matches the institutional
   email form, and no address appears twice. Then it emits the block to paste.

2. **A survey**, six free-text/numeric questions
   ([`canvas/quiz-peer-evaluation-questions.json`](canvas/quiz-peer-evaluation-questions.json)):
   the allocation, strengths per teammate, improvements per teammate, a required justification for
   any rating below 80 or above 120, a private note to the instructor, and a numeric self-check that
   accepts only 200, 300, or 400. Two attempts, so a bad total is fixable.

3. **A zero-point adjustment assignment**
   ([`canvas/assignment-0pt-adjustment.html`](canvas/assignment-0pt-adjustment.html)) whose
   description states the arithmetic, the 0.60-1.10 bounds, and five worked outcomes for the same
   team grade. Most students score **0** here, and the page says so in the first sentence.

4. **A private report** as a submission comment: how many teammates rated them, their mean, their
   factor, the multiplication, the posted adjustment, and their teammates' written comments **with
   names stripped**.

## What an instructor does

Per round, after the team deliverables are graded:

```
cd scripts
python3 peer_report.py tangible_draft            # dry run: reads Canvas, writes nothing
```

That pulls the roster, the group set, the team scores on the covered deliverables, and every
ballot; reconciles mistyped email addresses against the roster; validates each ballot; computes a
factor per student; and writes a report plus a JSON row set to `scripts/reports/`. It prints a
summary: who did not submit, every flagged student, every allocation problem, every auto-corrected
address, every cross-team address it refused to merge, and the full table of adjustments it intends
to post.

You read that. You decide. Then:

```
python3 peer_report.py tangible_draft --post     # writes the deltas and the comments
```

Grades land under a **manual** post policy, so nothing is visible until you release it in the
gradebook. The judgement calls the tool deliberately leaves to you: held ballots, `UNANIMOUS_LOW`
(every teammate independently rated someone below 80 — that is a conversation, not a number), teams
that came in undersized, and anything a student appeals.

## At a glance

| Component | File | What it is |
|---|---|---|
| Point allocator | `allocator/index.html` | Student-facing zero-sum calculator. Vanilla JS, single file, no network calls. |
| Scoring core | `scripts/ags/scoring.py` | Ballot validation, factor arithmetic, safety rails, instructor flags. Pure functions. |
| Reconciliation & reporting | `scripts/ags/peerreview.py` | Email repair, free-text allocation parsing, budget/coverage checks, report rendering. Pure functions. |
| Canvas client | `scripts/ags/canvas.py` | Minimal REST wrapper: pagination, throttle retries, token scrubbing in errors. |
| Round runner | `scripts/peer_report.py` | The one command. Dry run by default; `--post` writes. |
| Allocator embedder | `scripts/embed_allocator.py` | Injects the hosted calculator into the page and quizzes, with a preflight that refuses a URL that will not run scripts. |
| Canvas templates | `canvas/*.html`, `canvas/*.json` | Assignment description, quiz description, the survey questions, the fallback distribution tables. |
| Configuration | `scripts/course.example.yml` | Your whole course in one file: host, id, rounds, deliverables, thresholds. Read by every script. Your token is deliberately not in it. |
| Id discovery | `scripts/discover.py` | Prints the Canvas ids `course.yml` needs, so you do not hunt through URLs. |
| Provisioner | `scripts/provision.py` | Creates the surveys, 0-point adjustments and module items. `plan` / `apply` / `verify`. |
| Survey definition | `scripts/ags/survey.py` | The three questions, defined once and shared by the builder and the reader so they cannot drift. |
| Tests | `scripts/test_*.py` | 101 tests. Readable as the spec. |

The scoring model in one line:

```
factor = clamp(mean of all ratings a student received / 100, floor 0.60, ceiling 1.10)
adjustment posted = round(team_earned x factor - team_earned, 2)
```

## What it costs to adopt

| Cost | Reality |
|---|---|
| Programming skill | None. Copy `course.example.yml` to `course.yml`, run `discover.py`, paste in the ids. Then three commands in Terminal. If you can edit a YAML file you can run this. |
| Software | Python 3, plus `requests` and `python-dotenv`. The tests need neither. |
| Accounts | A Canvas API access token you generate yourself (Account -> Settings -> New Access Token) — no admin rights needed. A place to serve one static HTML file; GitHub Pages is free and is what the toolkit assumes. |
| First-course setup | Budget an afternoon. Per project arc: one self-signup group set, one graded survey per round, one zero-point assignment per round, one guide page, assignment-group weights, and the round table in the config. |
| Per round, ongoing | Roughly ten minutes of machine time and reading, plus however long the flagged conversations take. The conversations are the real cost and the toolkit cannot remove them. |
| Student time | A few minutes with the calculator; the survey itself is short and carries small completion credit. |

The one structural decision that costs nothing to make and a lot to get wrong: **the adjustment
assignment must be worth zero points, and it should cover the whole project arc rather than just
the final deliverable.** Both claims are measured, not asserted:

| Choice | Measured effect on the origin course |
|---|---|
| Adjustment carries the deliverable's own point value | A team at 85% with a factor of exactly 1.00 fell to **54.24%** in its assignment group — the delta's points entered the denominator (67 -> 105). A 0.60 factor then costs only 1.85 points of final grade. |
| Adjustment worth 0 points | The delta lands in the numerator only. Denominator untouched. |
| Covers the final two deliverables only (78 of 153 group points) | A persistent 0.60 student loses **6.76** percentage points of final grade. |
| Covers the whole arc (all 153 points) | The same student loses **13.41**. Same number of Canvas objects, roughly double the consequence. |

## Quick start (15 minutes)

Fifteen minutes is enough to decide whether this fits your course. It is not enough to deploy it —
that is an afternoon, and it is [docs/02-canvas-setup.md](docs/02-canvas-setup.md).

```
git clone https://github.com/NAU-CS/peer-evaluation-toolkit.git
cd peer-evaluation-toolkit

# 1. Run the spec. No Canvas, no token, no dependencies.
cd scripts && python3 -m unittest discover -p 'test_*.py'      # 101 tests

# 2. Be a student for two minutes.
open ../allocator/index.html
```

3. Read [examples/worked-round.md](examples/worked-round.md) — one real round, from what three
   students typed (messy on purpose: mixed separators, a bare user id with no domain) through to
   the comment each of them received.
4. Read [docs/01-how-it-works.md](docs/01-how-it-works.md) for why the model is shaped
   this way, then [docs/03-gradebook-math.md](docs/03-gradebook-math.md) for why the
   zero-point assignment is load-bearing.
5. If you are still in, [docs/02-canvas-setup.md](docs/02-canvas-setup.md) is the ordered build path.

## Setting it up

Four steps. The only thing that is not a copy-paste is deciding which deliverables
each round covers.

```bash
pip3 install -r scripts/requirements.txt
```

**1. Store your token.** It never goes in a file you could commit. On macOS:

```bash
security add-generic-password -U -s canvas-api-token -a "$USER" -w
```

The prompt shows nothing as you paste — press Return when done. Not on macOS, or
prefer an env var? `export CANVAS_TOKEN=...`, or put it in `scripts/.env`
(gitignored). Create the token at **Account → Settings → + New Access Token**;
it needs teacher rights on the course, and give it an expiry.

**2. Make your config.**

```bash
cd scripts && cp course.example.yml course.yml
```

`course.yml` is gitignored and holds everything about your course: host, course
id, rounds, and the thresholds. Your token is deliberately *not* in it, so the
file is safe to hand a colleague as a starting point.

**3. Fill in the ids.**

```bash
python3 discover.py
```

That prints your course's group sets, quizzes and assignments with their ids, so
you can paste them into `course.yml` instead of hunting through Canvas URLs.

**4. Build the Canvas objects** — or skip this and create them by hand if you
would rather see every click.

```bash
python3 provision.py plan     # prints what it would create, touches nothing
python3 provision.py apply
python3 provision.py verify   # re-checks the things Canvas silently gets wrong
```

Then, once a round closes and **every covered deliverable is graded**:

```bash
python3 peer_report.py <round-key>          # dry run, writes a report file
python3 peer_report.py <round-key> --post   # writes grades and comments
```

`<round-key>` is a key from the `rounds:` table in your `course.yml`.

## Repository map

```
allocator/index.html                      student-facing calculator (host this)
canvas/                                   HTML/JSON templates for the Canvas objects
docs/                                     see below
examples/worked-round.md                  input -> output for one round
scripts/
  course.example.yml   >>> COPY THIS <<<  your whole course in one file
  discover.py                             prints the Canvas ids course.yml needs
  provision.py                            creates the Canvas objects for you
  peer_report.py                          run a round
  embed_allocator.py                      embed the hosted allocator in the survey
  ags/config.py                           reads course.yml
  ags/survey.py                           the survey, defined once for both scripts
  ags/scoring.py                          factor math + safety rails
  ags/peerreview.py                       reconciliation, parsing, reports
  ags/canvas.py                           REST client
  test_*.py                               101 tests
LICENSE  CONTRIBUTING.md
```

## Documentation

| Doc | Read it when |
|---|---|
| [docs/01-how-it-works.md](docs/01-how-it-works.md) | You want to know why zero-sum, why per-deliverable, why a multiplier. |
| [docs/02-canvas-setup.md](docs/02-canvas-setup.md) | You are building the group sets, surveys, assignments, and pages. The ordered build path. |
| [docs/03-gradebook-math.md](docs/03-gradebook-math.md) | Before you create a single assignment. The zero-point trick, the weighting arithmetic, and what to say when a student disputes a number. |
| [docs/04-running-a-round.md](docs/04-running-a-round.md) | A round has closed and you want to score it. |
| [docs/05-adapting-it.md](docs/05-adapting-it.md) | Your course is not IMG 186 — which is to say, always. Cadence, coverage, clamps, and flag thresholds. |
| [docs/06-canvas-field-notes.md](docs/06-canvas-field-notes.md) | Canvas is lying to you. Empirically verified failures, several of which return HTTP success while doing nothing. |

## Known limitations

Stated plainly, because finding these out in week ten is worse.

- **Teams of two are not anonymous.** With no averaging, each partner can derive the other's rating
  from their own posted result. This is arithmetic, not a policy choice. The default policy narrows
  the factor range to 0.80-1.10 rather than pretending otherwise; `neutralize` (force 1.00) and
  `full` (normal clamp) are also selectable per round.
- **Institution-specific assumptions.** The email pattern (`letters + digits @nau.edu`) is hard-coded
  in both `allocator/index.html` and `ags/peerreview.py`. The Canvas templates use DesignPLUS markup
  that degrades to plain HTML elsewhere but will not look the same.
- **`embed_allocator.py` reads a wiring file** (`scripts/backups/peer_eval_wiring.json`) produced by
  the origin course's build scripts and not shipped here.
- **Classic Quizzes only**, and **Canvas will not accept grades in an unpublished course** (403), so
  negative-score behaviour cannot be smoke-tested before you publish.
- **The tool does not decide anything that matters.** It holds suspicious ballots, raises flags, and
  refuses to guess. A held ballot, a unanimous low rating, or an appeal is yours to resolve.

## Attribution

The model is from Doerry and Palmer, *Improving Efficacy of Peer-Evaluation in Team Project
Scenarios*, ASEE Annual Conference, 2011 — the peer-evaluation schema developed for the
**Design4Practice** program at Northern Arizona University. The zero-sum
budget, the requirement that ratings be anonymous, the per-deliverable scope, the direct-multiplier
application (their "Version 4", after a percentage-of-grade "Version 3" proved insufficiently
consequential), the justification band, and the flat-ballot dysfunction profile are all theirs.
The tests in `test_scoring.py` pin the arithmetic to that paper's worked examples.

What is added here is the Canvas implementation: the zero-point adjustment mechanism, the safety
rails (rescale limits, coverage checks, quorum bounds, pair policies), the reconciliation of messy
student input, and the field notes on Canvas behaviour.

## Provenance and licence

Built for one course — **IMG 186, Game History and Theory, Northern Arizona University** — and
generalised afterwards. **Every number in the examples is that course's**: the 153 group points, the
40% group weight, the 85% team, the assignment ids, the arc names, the NAU email pattern. They are
included because a measured number is more useful than an invented one, not because they will match
your course. Recompute the consequence for your own weighting before you tell students what a
factor costs; [docs/03-gradebook-math.md](docs/03-gradebook-math.md) shows the arithmetic.

MIT licensed — see [LICENSE](LICENSE). Contributions, especially new Canvas field notes and real
examples of what students actually typed, are welcome: [CONTRIBUTING.md](CONTRIBUTING.md).
