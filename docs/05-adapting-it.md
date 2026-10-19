# Adapting it to your course

Nothing in this toolkit knows anything about your course except what you tell it. Retargeting
it is two different jobs, and it helps to keep them apart:

- **Configuration.** Course and object ids, dates, team sizes, your email domain, the deliverables
  each round covers, the wording students read. Mechanical. A couple of hours, mostly proofreading.
- **Judgement.** How hard the floor bites, what happens on a two-person team, whether a unanimous
  low rating becomes a number or a conversation, and what your syllabus promises. No config file
  can make these for you, and this document will not pretend otherwise.

Do them in that order, then run one complete round with grading turned off before anything counts.

## The files you will actually edit

| File | What it controls |
|---|---|
| `scripts/.env` (from `.env.example`) | Canvas host, API token, course id. Never committed. |
| `scripts/course.yml` (from `course.example.yml`) | Everything `provision.py` builds in Canvas: the adjustment assignments, the three-question surveys, module placement, and the student-facing text generated from them. |
| `scripts/course.yml` | The per-course record of your decisions — scoring policy, cadence, thresholds, which Canvas objects belong to which round. Read the honest note below about what code does and does not consume. |
| `scripts/peer_report.py` | `CID` and the `ROUNDS` table near the top; the `Q_*` question-slot constants. |
| `scripts/ags/scoring.py` | Every threshold, as a keyword-argument default. |
| `scripts/ags/peerreview.py` | `NAU_EMAIL`, `normalize_email`, `FUZZY_THRESHOLD`, `NULLISH`. |
| `allocator/index.html` | Team sizes offered, the starting patterns, the email pattern, the on-page copy. |
| `canvas/*.html`, `canvas/quiz-peer-evaluation-questions.json` | The as-authored student-facing text, if you prefer editing HTML to running the provisioner. |
| `scripts/embed_allocator.py` | `CID`, the `PAGE` slug, and the iframe caption. |

### An honest note about where settings live

`course.yml` reads like a settings file, and in an ideal version of this toolkit it would
be one. In the code as it stands it is a **worksheet**: a single place to write down and review one
course's decisions. The YAML that a script actually parses is `course.yml`, consumed by
`provision.py`. `peer_report.py` takes `--floor`, `--ceiling` and `--pair-policy` on the command
line and carries the course id and the round table as constants; every other threshold is a
keyword default inside `ags/scoring.py`.

Practically: expect to edit two YAML files and roughly half a dozen lines of Python. That is more
honest than a config file that silently fails to be read. Where a field below is a worksheet entry
rather than a wired setting, it says so, and it says which line of code carries the live value.

## `course.yml`, field by field

Every script reads this one file through `ags/config.py`. There are no "live values"
elsewhere to keep in sync — that split used to exist and was a reliable source of bugs.
Anything you leave out falls back to the default shown.

### `canvas`

**`base_url`** — your Canvas host, no trailing slash and no `/api/v1`.

**`course_id`** — the number in your course URL, `/courses/<this>`.

### `email`

**`domain`** / **`example`** — your institution's address shape. The domain drives both the
accepted-address pattern and the repairs for a mistyped one (a truncated `.ed`, a doubled
`.edu.edu`, a bare user id with no domain at all). The example appears in the student-facing
instructions. Set these and a student typing `abc123` still resolves to the right person.

### `allocator_url`

Where the point allocator is served. The default is the public copy and works as-is; host
your own if you would rather not depend on someone else's GitHub Pages. This URL is embedded
into survey question 1.

### `rounds`

One entry per checkpoint. The key (`tangible_draft`) is what you type on the command line.

**`arc`** / **`phase`** — appear in every student-facing string and in the report headings.

**`group_category_id`** — the Canvas *group set* holding this round's teams. One set per
project arc matters if you re-form teams between projects, which the paper's logic favours:
a fresh set means a student's reputation does not follow them. If your teams are stable all
term, repeat the same id.

**`survey_quiz_id`** — the graded survey students fill in. `provision.py` creates it and
fills this in; `discover.py --quizzes` finds it if you built it by hand. May be blank until
then — the scripts say so plainly rather than failing with a 404.

**`adjustment_assignment_id`** — the 0-point assignment the adjustment is posted to. Must be
worth 0 points and live in the same assignment group as the deliverables it covers;
[docs/03-gradebook-math.md](03-gradebook-math.md) explains why both constraints are
load-bearing.

**`covers`** — the group deliverables this round's factor multiplies, as
`{name, points, assignment_id}`. The adjustment is `team_earned x factor - team_earned`
summed across exactly these, so list all of them and nothing else. **Grade every one before
running the round**: an ungraded deliverable silently shrinks `team_earned` and every
adjustment with it.

Optional build-time fields, used only by `provision.py` when it creates the Canvas objects:
`module` (must match the module name exactly), `assignment_group_id` (the project's group,
for the adjustment), `quiz_due` and `adjustment_due`.

### `scoring`

**`floor`** / **`ceiling`** (0.60 / 1.10) — the clamp. `factor = clamp(mean received / 100,
floor, ceiling)`. These are interpolated into the text students read, so the number they are
told and the number they are graded by cannot drift. `--floor` / `--ceiling` override per run.
See [Choosing the clamp](#choosing-the-clamp).

**`include_self_rating`** (true) — whether a student's own self-rating counts toward their
own mean. True is faithful to the paper and easier to defend in an appeal.

**`max_rescale_pct`** (10.0) — a ballot further off the required total than this is held for
review rather than rescaled. Rescaling a wildly wrong ballot manufactures extreme factors
from numbers the student never intended.

**`justify_below`** / **`justify_above`** (80 / 120) — the band outside which a written
justification is required. These numbers are rendered into survey question 2, so changing
them changes what students are asked. A missing justification is recorded as a ballot
*problem*; the ballot still scores.

### `teams`

**`pair_policy`** (`clamp`), **`pair_floor`** / **`pair_ceiling`** (0.80 / 1.10) — how to
handle a two-person team, where ratings cannot be anonymous. See
[Team sizes and the pair problem](#team-sizes-and-the-pair-problem).

**`min_raters`** (2) and **`single_ballot_cap`** (0.10) — below `min_raters` on a team of
three or more, one voice would set someone's whole factor, so it is bounded to
1.00 +/- the cap.

### `flags`

**`low_mean_received`** (85), **`self_minus_peer_gap`** (10), **`flat_ballot_spread`** (8),
**`unanimous_low`** (80) — triage thresholds. They never change a grade; they decide what
lands on your desk. Full table in
[Flag thresholds and how to tune them](#flag-thresholds-and-how-to-tune-them).

### `grading`

**`cap_at_points_possible`** (true) — avoid `14.3/13` artifacts in a weighted gradebook.
**`decimals`** (2) — rounding on the posted adjustment.

### `provisioning`

Read only by `provision.py`, and only when creating Canvas objects.
**`participation_group_id`** — the assignment group the surveys go in, usually participation
rather than the project group. **`completion_points`** — credit for submitting an evaluation.
Keep it small: it should not outweigh the contribution consequence the adjustment creates.

## Cadence: how many rounds

The paper's argument is for **more rounds rather than fewer**, and it is not a workload argument —
it is about what a rating can honestly mean. Evaluation attached to a specific deliverable asks
students a question they can answer: who did what on *this* prototype, in *these* three weeks.
Evaluation attached to the whole term asks them to summarise a relationship, which is where
"negative carry-over" comes from: one bad fortnight in September colours every rating in December,
and a student who fixed their behaviour gets no credit for having fixed it.

Frequent rounds also make the mechanism corrective instead of merely punitive. A student who sees a
−2.97 in October with three teammate comments attached has time and reason to change. The same
student meeting the entire consequence in the last week of term has neither.

The origin course runs five: one practice round with no grade effect, then draft and final for each
of two project arcs.

| Cadence | Rounds | What it costs you | What it buys |
|---|---|---|---|
| One, at the end | 1 | least | almost nothing worth having: no correction window, maximum carry-over, and every grievance of the term lands in one ballot |
| Mid and final on one project | 2 | one extra survey, one extra CLI run | a real correction window; the minimum I would defend |
| Draft and final per arc | 4 | four runs, four flag lists | each rating covers ~3 weeks of specific work |
| Add a practice round | +1 | one run, no grades touched | students learn the arithmetic and the format when it is free, so your first graded round is not also your first format-error triage |

The marginal cost of a round is one `provision.py apply` (which builds the survey and the adjustment
assignment together), one `peer_report.py <round>` dry run, reading the flag list, and one
`--post`. The flag list is the part that takes real time, and it scales with the number of teams
in trouble, not with the number of rounds.

Run the practice round. It costs nothing, and it converts the "my numbers don't add up" support
load from a graded week into an ungraded one.

## Coverage: which deliverables a round scales

Cadence and consequence are separate knobs, and this is the one people get wrong. How *often* you
collect ballots determines how corrective the system is. How many *points* each round's factor
multiplies determines how much it matters. Measured on the origin course, where group work is 40% of
the final grade and the example team sits at 85%:

| Adjustment covers | Covered points | A student persistently at factor 0.60 loses |
|---|---|---|
| Draft and Final deliverables only | 78 of 153 | 6.76 percentage points of final grade |
| The whole project arc | 153 of 153 | 13.41 percentage points of final grade |

Same number of Canvas objects. Same amount of your time. Roughly double the consequence. If you
have decided that this mechanism should matter, cover the whole arc.

To estimate your own numbers before you commit:

```
loss in final-grade percentage points  ≈  W × T × (1 − floor) × (C / G)

W     = group work's share of the final grade      (0.40 in the origin course)
T     = the team's percentage on those deliverables (0.85)
floor = your factor floor                           (0.60)
C / G = covered points ÷ total group points         (78/153 or 153/153)
```

That formula gives 13.6 and 6.9 against measured values of 13.41 and 6.76. It runs slightly high
because the origin course's group points are split across two assignment groups with different
weights; treat it as a planning estimate, not a promise.

Two operational warnings about coverage:

1. **Every covered deliverable must be graded before you run the round.** `peer_report.py` sums the
   team's posted scores across the covered assignments and skips any submission with no score. If
   one covered deliverable is still ungraded, the sum is quietly smaller, the adjustment is computed
   against a smaller base, and the report tells the student "Team earned 19 of 32", which reads like
   a bad team grade rather than an unfinished gradebook. Check the covered set is complete first.
2. **A deliverable should be covered by exactly one round.** Nothing enforces this. If two rounds
   both list Part 3, Part 3's team score is scaled twice, and a student at the floor is charged for
   it twice.

## Team sizes and the pair problem

Team size is handled entirely by the allocator: the student picks their size, and the tool
refuses to produce output until the points total size x 100. There is no longer a numerical
checksum question in the survey to keep in sync — `peer_report.py` re-checks the arithmetic
*and* the coverage when it reads the ballot, which catches what a single total never could
(300 is a legal total, but wrong for a two-person team).

For teams of five or more, edit `allocator/index.html`: add an `<option value="5">`, a
five-column `PAT` array whose every row totals 500, and raise the `max` on the points input,
which is currently `max="400"`.

Larger teams are otherwise kinder to this design: more raters means more averaging, so a single
harsh or generous ballot moves a factor less, and the quorum rule almost never binds.

### Pairs

A two-person team breaks the two things that make the model defensible. There is no averaging — the
partner *is* the mean, minus your own self-rating — and the arithmetic is reversible. A test in
`test_scoring.py` demonstrates it explicitly: `2 × mean_received − self_rating` recovers exactly
what the partner privately said. Whatever you promise about anonymity, on a pair it is false.

Three policies ship, selected with `--pair-policy`:

| Policy | Factor range on a pair | When it is right |
|---|---|---|
| `clamp` (default) | 0.80–1.10 | Pairs happen in your course and you still want accountability. Halves the downside while keeping the mechanism alive. |
| `neutralize` | forced to 1.00 | You judge that a non-anonymous, non-averaged rating should never move a grade. Defensible and easy to explain; also means a student stuck carrying a pair gets nothing. |
| `full` | 0.60–1.10 | You are confident the pair is a real team and want the normal rule. Be ready for "she gave me 70 because I gave her 70". |

Whichever you choose, every member of a pair is flagged `team_of_2: ratings are NOT anonymous`, and
the team gets `team_size_2` — the warning is not suppressible, on purpose. Decide the policy before
the term, put it in the syllabus, and prefer not having pairs at all: `min_size: 3`, and when a team
collapses mid-arc, either merge it or write to both students telling them plainly that at this size
their partner can derive their rating.

### Below quorum

On a team of three or more where fewer than `min_raters` (2) ratings arrive, one voice would
otherwise set someone's entire factor. The code bounds the factor to 1.00 ± `single_ballot_cap`
(0.10) and flags `below_quorum`. If your students are reliable submitters this rule will almost
never fire; if they are not, leave it alone.

## Choosing the clamp

The default range, 0.60 to 1.10, is deliberately asymmetric. The floor is where the mechanism does
its work, so it is far from 1.00. The ceiling is close to 1.00 because a generous ceiling turns the
zero-sum ballot into a collusion payoff: a team that agrees to rate each other 130 should not be
able to manufacture grades, and with a 1.10 ceiling the most they can gain is 10%.

Set the floor by deciding what the maximum consequence should be, then working backwards with the
formula above. At the origin course's weighting — 40% group work, a team at 85%, whole-arc coverage:

| Floor | Estimated maximum loss in final grade |
|---|---|
| 0.60 | ~13.6 points (measured: 13.41) |
| 0.75 | ~8.5 points |
| 0.85 | ~5.1 points |
| 0.90 | ~3.4 points |

Only the 0.60 row is measured; the rest come from the estimate. Read them as "roughly a letter and a
half" versus "roughly a third of a letter" and pick the one you are willing to defend to a student
with a parent on the phone. A 0.60 floor in a first-year class where group work is most of the grade
is aggressive; the same floor in a capstone where the team *is* the course is arguably lenient.

Three things to keep in sync when you change the clamp: `--floor`/`--ceiling` (or the defaults in
`score_team`), `floor:`/`ceiling:` in `course.yml` — which are interpolated into the worked
example students read, including the "this is the floor" row — and the range quoted in your
syllabus. And if you raise the ceiling above 1.10, re-read the note under
`grading.cap_at_points_possible`: the adjustment path does not cap, so a high ceiling on a
high-scoring team is extra credit.

## `include_self_rating` and what it buys you

With `include_self_rating: true` (the default, and what the paper describes), your own self-rating is
one of the numbers averaged into your own factor. On a three-person team that is a third of your own
grade adjustment, which sounds alarming until you notice the budget is fixed: every point you award
yourself is a point you take from a teammate, and their ballots are averaged in too.

| | `true` (default) | `false` |
|---|---|---|
| Factor from | every rating received, self included | teammates' ratings only |
| Self-inflation | possible, but bounded by the zero-sum budget and visible | impossible |
| `self_over_peer` flag | works — it compares self-rating against peer mean | **cannot fire**, because no self-rating is collected into the mean |
| Zero-sum invariant | holds: the team's means sum to exactly N × 100 (asserted in `test_scoring.py`) | broken; means no longer reconcile against the budget |
| Non-submitter | loses their own vote, so their factor is set purely by peers | no change, since self never counted |
| On a pair | mean is (self + partner) ÷ 2 | the partner alone sets your factor |

The trade is: `true` lets a student argue their own case and gives you the single most useful
diagnostic in the whole system — the paper's signature dysfunction profile is precisely a
high self-rating over a low peer mean. `false` closes off self-inflation, at the cost of that
diagnostic, the reconciliation invariant, and any protection on small teams. Keep the default unless
you have a specific reason. The live value is `score_team`'s keyword default;
`peer_report.py` does not pass it, so flipping it means editing one of those two places.

## Flag thresholds and how to tune them

Flags never change a grade. The only things that move a factor are the clamp, the pair policy and
the quorum bound. Everything below is triage: it tells you which of forty students to look at.

| Threshold | Default | Fires when | Tune it when |
|---|---|---|---|
| `max_rescale_pct` (`validate_ballot`) | 10.0 | A ballot's total is more than 10% off N × 100 → **held**, not rescaled | Never loosen this. It exists because `{100, 0, 0}` on a three-person team was once rescaled to `{300, 0, 0}`, which passed validation and put one student at the ceiling and two honest teammates at the floor. Small slips (285 of 300) still rescale proportionally, and the 0–200 range is re-checked *after* rescaling. |
| Hard rating bounds | 0–200 | Any single rating outside → ballot invalid | Raise only if you allow team sizes where 200 is a plausible fair-share multiple. |
| Justification minimum length | 20 characters | Reason required but shorter than this → problem note | Raise if "he was lazy" is passing as a justification. It is a length check, not a quality check; only you can do the second one. |
| `justify_below` / `justify_above` | 80 / 120 | Any rating outside the band requires narrative | Widen to 70/130 if your students are timid about using the range; narrow to 90/110 if you want a reason for anything non-trivial. Must match the text in Q1, Q4 and the quiz description. |
| `low_mean_received` | 85 | A student's mean is below 85 | Raise to 90 to see near-misses; lower to 80 if too many teams are normally uneven. |
| `self_minus_peer_gap` | 10 | self-rating − peer mean ≥ 10 | 10 is tightened from the 15 the paper implies, because a three-person team compresses the gap. On teams of four or more, 15 is a better setting; below 8 you will flag ordinary self-confidence. |
| `flat_ballot_spread` | 8 | A rater's own ballot is perfectly flat while some teammate's ballot spreads at least this far | The other half of the dysfunction profile. On larger teams spreads are naturally wider, so raise it; a genuinely even team trips nothing, because the rule requires *disagreement* somewhere on the team. |
| `flag_all_even` | true | Every valid ballot on the team is all 100s | Leave on. Most of the time it means a genuinely even team, which is fine; occasionally it means nobody engaged. |
| `unanimous_low` | 80 | Every teammate independently rated someone below 80 | Do not weaken this one either. It is the paper's cue that the situation needs a conversation rather than a number, and it is the flag most likely to be a real problem rather than a data-entry error. |
| `min_raters` / `single_ballot_cap` | 2 / 0.10 | Team of 3+ with fewer than 2 ratings → factor bounded to 1.00 ± 0.10 | Only if your rounds routinely come in below quorum, which is a submission-compliance problem, not a threshold problem. |
| `pair_floor` / `pair_ceiling` | 0.80 / 1.10 | The `clamp` pair policy's narrowed range | Together with the pair policy itself. |
| `FUZZY_THRESHOLD` (`peerreview.py`) | 2 | Levenshtein distance within which a mistyped address is silently corrected to a roster address | Lower to 1 if your institution's ids are short enough that two ids can be two edits apart — with `abc12`-style ids that is a real risk, and a wrong correction posts a rating to the wrong student. Every correction is listed in the report; read that list. |
| `NULLISH` (`peerreview.py`) | `n/a`, `none`, `-`, … | Filler answers treated as empty, so "n/a" never reaches a teammate as feedback | Add whatever your students actually type. This is the single most valuable thing to contribute back. |

A useful default posture: run the first round with everything as shipped, then loosen only the
flags that generated noise you correctly ignored, and never loosen `max_rescale_pct` or
`unanimous_low`.

## Adapting the allocator

`allocator/index.html` is one self-contained file with no dependencies, no network calls, no storage,
and no analytics. Keep it that way — the survey text promises students that nothing they type is
submitted or recorded, and that promise is only true because the file has nothing in it that could.

**Team sizes.** The `<select>` options and the keys of the `PAT` object must match. Adding a size
means adding both, plus rows in `PAT[n]` that each total n × 100, plus raising `max="400"` on the
points input. The tool refuses to emit output until the numbers total exactly n × 100, so a pattern
row that does not add up is silently useless.

**The email pattern.** One regex, `NAU = /^[a-z]+[0-9]+@nau\.edu$/i`, gates both the per-row warning
and the copy button. Replacements, in rising order of permissiveness:

```js
// letters then digits at your domain (NAU-style ids)
var NAU=/^[a-z]+[0-9]+@your-university\.edu$/i;
// firstname.lastname@
var NAU=/^[a-z]+\.[a-z-]+@your-university\.edu$/i;
// anything at your domain — safest if you cannot characterise your ids
var NAU=/^[^@\s]+@your-university\.edu$/i;
```

The regex is not the only institution-specific thing about addresses. Four places carry that
assumption, and only two of them matter:

- `allocator/index.html` — the regex above. **Must change**, or every student sees a false warning.
- `ags/peerreview.py`, `normalize_email` — appends `@nau.edu` to a bare id and repairs `@nau.ed`,
  `@nau.eduu`, `@nau.edu.edu`. **Must change**, or a student who types their bare id gets
  `id@nau.edu`, which is not on your roster, and the rating is dropped as an unknown address.
- `ags/peerreview.py`, `NAU_EMAIL` — used only to print a "roster emails not in the expected form"
  section in the report. Cosmetic; update it so that section is meaningful.
- `ags/peerreview.py`, the `_ALLOC` regex — already matches any `user@domain`, plus a bare
  `letters+digits` id. Leave it unless your ids contain characters it does not accept.

**The patterns.** `PAT` maps a plain-language description to a distribution: "One did clearly less"
→ `[110, 110, 80]`. They exist so a student never has to do arithmetic, and they double as an
implicit statement of what the scale means — the fact that "One barely appeared" is `[130, 130, 40]`
rather than `[110, 110, 80]` is a pedagogical choice about how much of the range you expect students
to use. Write your own in your own language, keep every row exact, and remember the same tables
appear in three places: `PAT`, `canvas/page-distribution-guide.html`, and the accordion inside Q1.
Change one and students will find the contradiction.

**Output format.** The tool emits `email = points`, one per line. `parse_allocation` accepts `=`,
`:`, `-`, en/em dashes, tabs and wide whitespace as separators, so you have latitude — but if you
change the emitted format, run `test_peerreview.py` before you trust it.

**Hosting and embedding.** Canvas serves uploaded HTML with `script-src 'none'` and as an
attachment, so JavaScript in a Canvas-hosted file never runs; the tool must live somewhere else and
arrive by `<iframe>`. `embed_allocator.py` handles the wiring and refuses to embed a URL whose
headers show scripts are blocked. Two gotchas when you retarget it: `CID` and the `PAGE` slug are
constants, and the `--remove` path finds the old block by matching the literal caption text ending
`recorded.</p>`. Rewrite that caption and `--remove` stops finding anything.

## What to change in the student-facing text

Two routes: let `provision.py` generate the descriptions from `course.yml` (plain HTML, no
dependencies, regenerated whenever your numbers change), or edit the as-authored files in `canvas/`
by hand. The hand-authored files use DesignPLUS markup — `dp-*` classes and Font Awesome icons —
which renders as designed only if your institution licenses that toolkit. Without it the content is
all still there, just plainer. If you are not on DesignPLUS, prefer the generated route.

**`canvas/assignment-0pt-adjustment.html`** — the single most important page in the system, because
it is where a student meets a negative number for the first time. Change: the deliverable table and
its covered total; the entire worked example, whose five rows are computed from one team score
(27.2 of 32) and your floor and ceiling; the instructor's name, twice; the appeal window ("within one
week"); and the learning-outcome line at the bottom. Keep three things whatever else you rewrite:
the opening sentence that most students will receive a 0 and that this is expected, the explicit
statement that the floor is a floor, and the paragraph explaining that a non-submitter still
receives their teammates' ratings.

**`canvas/quiz-peer-evaluation-description.html`** — contains a hard-coded link to the distribution
guide page, with both a course id and a page slug in the URL, plus the arc and part names, the
anonymity paragraph including the pair caveat, and the attempts allowed.

**`canvas/quiz-peer-evaluation-questions.json`** — three questions, named `Q1`…`Q3`, generated from `scripts/ags/survey.py`. Things to know
before you edit them through the API:

- Keep the names exactly `Q1`…`Q3`. Canvas does not persist `position` on questions created or
  updated through the API — it reads back as `None` — so `peer_report.py` keys answers off
  `question_name`. Rename a question and every ballot misparses, silently.
- Send the **full** question payload on every update. A partial update can silently revert
  `question_text`.
- Canvas cannot validate one answer against another. Neither Classic nor New Quizzes can do
  it, and "formula" questions use Canvas-generated variables, not student responses. That is
  why the arithmetic is enforced in the allocator before the student can copy anything out,
  and re-checked by `peer_report.py` afterwards — including the case a single numerical total
  could never catch, where 300 is a legal total but wrong for a two-person team.
- If you write numerical range answers anywhere, they are `answer_range_start` / `answer_range_end`.
  Writing `start` / `end` is accepted and stores 0/0, producing a question that accepts only zero.
- After editing questions, unpublish and republish the quiz to force `points_possible` to recompute.

**`canvas/page-distribution-guide.html`** — the no-JavaScript fallback. It claims the survey will
reject a wrong total; the allocator now does that before the student can copy anything out.

Before your first graded round, check the values that appear in more than one place: floor and
ceiling, allowed team sizes and their totals, the 80–120 justification band, the covered deliverables
and their points, attempts allowed, and the appeal window. A student who finds two different numbers
in your own materials has a real grievance, and it is the one grievance that is entirely avoidable.

## Syllabus language

### The trap

Many syllabi contain a sentence like "all teammates receive the same grade on group assignments."
That sentence is *compatible* with this design, and only for one structural reason: the group
deliverable really does keep one shared grade for the whole team, and individual differentiation
lives in a **separate line item**. Nobody's grade on the group assignment is changed by their
teammates' ratings.

That is a narrow truth, and leaning on it without disclosure is not defensible. What the sentence
does not promise, and what your syllabus must therefore say out loud, is that two teammates end the
term with the same *course total*. If a student's project credit can move because of what their
teammates reported, that has to be in writing before teams form. "It's a separate assignment" is a
correct answer to a technical objection, not to a fairness one.

One genuinely helpful consequence is worth stating in the syllabus: because the adjustment
assignment is worth **0 points**, it does not change any assignment group's points possible. The
weights printed in your syllabus hold exactly as printed. (This is also the load-bearing reason the
assignment must stay at 0 — see [03-gradebook-math.md](03-gradebook-math.md).)

### What has to appear

Existence and timing of the evaluations. The basis (teammate ratings). The mechanism (a multiplier
on the covered deliverables, posted as a separate 0-point item). The range. Anonymity and its limit
on pairs. What happens if a student does not submit. The appeal route and its window. And that a
unanimous low rating may lead to a meeting rather than just a number.

### Suggested wording

Fill in the brackets; the numbers must match your `course.yml`, your CLI flags and your
assignment descriptions.

> **Group work and individual accountability.** Every member of a team receives the **same grade** on
> each group deliverable. Individual contribution is handled separately, through a 0-point gradebook
> item called "[Project] Peer Review Grade Adjustment."
>
> [N] times this term you will complete a short peer evaluation of your team. Each of you
> distributes (team size × 100) points across the team, **including yourself**; 100 means "did their
> fair share." The average of the ratings you receive, divided by 100, is your contribution factor,
> limited to the range **[0.60]–[1.10]**. Your adjustment is (your team's points on the covered
> deliverables × your factor) minus those same points, entered as a positive or negative number on
> the 0-point item. If your team worked evenly your adjustment is 0, which is the expected result for
> most students. A written justification is required for any rating you give below [80] or above
> [120].
>
> Because the adjustment item is worth 0 points, it does not change how much any assignment group is
> worth: the weights above hold exactly as printed. It does mean that two members of the same team
> can finish the course with different totals.
>
> Ratings are anonymous. You will receive your teammates' written comments with names removed, and
> you will never be told who gave which number. **On a two-person team your partner can work out
> your rating from their own result** — that is arithmetic, not a policy choice. [On two-person teams
> the factor range is narrowed to 0.80–1.10. / On two-person teams no adjustment is applied.]
>
> If you do not submit a peer evaluation, your teammates' ratings still apply to you. Not submitting
> removes your own voice from the calculation; it does not exempt you from it, and you also lose the
> completion credit for the evaluation itself.
>
> To dispute an adjustment, email me within [one week] of it being posted, with specifics about tasks
> assigned and tasks completed. Better still, raise contribution problems *during* the project, when
> something can still be done about them. Where every teammate independently reports that someone did
> far less than their share, I will normally meet with that student rather than simply post a number.

If you run a practice round, add one line: "The first evaluation, due [date], is practice. It is
scored for completion only and cannot change anyone's project credit."

## Institutional questions

### FERPA and the identified reports

Each run of `peer_report.py` writes to `scripts/reports/`:

- `<round>_<timestamp>.txt` — for every student, **both** an anonymous copy and an instructor copy.
  The instructor copy carries the student's name and email, their team, their self-rating, the peer
  mean excluding self, every flag, and each teammate's comments **attributed by name**, including the
  "for the instructor only" answers.
- `<round>_<timestamp>.json` — names, emails, teams, factors, means, adjustments and flags.

Treat that directory as an education record containing third-party statements, because that is what
it is. Practical handling:

- `reports/`, `.env`, `backups/` and `probe_output/` are already in `.gitignore`. Verify that before
  your first commit, not after. `course.yml` is not listed — it holds only Canvas object
  ids and deliverable names, no student data, but review it before committing anyway and consider
  adding it.
- Keep the directory on institution-managed storage. Do not let it sync to personal cloud accounts,
  and do not run a round on a shared lab machine.
- Retain the JSON at least through your appeal window — it is the evidence if a grade is challenged —
  and then dispose of it on whatever schedule your institution's records policy sets. That schedule
  is a question for your registrar, not for this document.
- **Only the anonymous copy is posted to Canvas.** `peer_report.py` calls the renderer with
  `anonymous=True` for the submission comment. Keep it that way. Pasting an instructor copy into a
  Canvas comment discloses one student's statements about another, by name, in a place the subject
  can read.
- Anonymity is not confidentiality. On a pair the rating is derivable. On a team of three, a comment
  about a specific task often identifies its author to anyone who was there. Say so to students —
  the shipped quiz text already does for pairs — rather than over-promising.
- Q5 tells students their answer is never shared with teammates. The renderer honours that by
  putting those comments in the instructor copy only. If you rewrite the reporting, re-check it.
- If a student formally requests their record, what they are entitled to see, and whether that
  includes anything that would identify a rater, is a question for your registrar or FERPA officer.
  The "never told who gave which number" promise is a pedagogical commitment this toolkit
  implements; it is not a determination about your institution's disclosure obligations, and no code
  in here can make that determination for you.
- The Canvas token in `.env` acts with your teacher rights on the course. Treat it as a password,
  set an expiry when you create it, and revoke it at the end of term.

### A public GitHub Pages repository is world-readable

Hosting the allocator on GitHub Pages generally means a public repository, and public means the
**entire history** is readable: a file you commit and later delete is still there. Consequences:

- Never commit `reports/`, a roster export, `.env`, or anything else with a student's name in it.
  One accidental commit is not fixed by a later deletion.
- The cleanest arrangement is two repositories: a public one containing only the allocator (the
  single `allocator/index.html`, and nothing else), and a private one for the scripts, the Canvas templates
  and the reports. Serving Pages from a private repository is available on some paid GitHub plans;
  check yours before assuming it.
- The allocator itself is genuinely safe to publish. It has no backend, makes no network requests,
  writes nothing to storage, and loads no external assets; its only outward action is a clipboard
  write. That is what makes the sentence "nothing you type in it is submitted or recorded" true, and
  it stays true only as long as nobody adds a script tag, a font link or an analytics snippet.
  Re-check after any fork.
- `course.yml` as shipped contains one real course's numeric ids and one instructor's email
  shape. None of that is student data, but it is a fingerprint of a specific section. Scrub yours if
  you would rather not publish which course this is.
- The iframe URL is visible to students and the tool has to stay reachable. Rename the repository or
  change the Pages path and the embeds 404 silently — students see an empty box, not an error you
  will hear about. `embed_allocator.py --remove` exists for when you need to pull them back out.
- Some campuses require review before third-party content is embedded in the LMS or before an
  assignment sends student data off-campus. Here nothing leaves the browser, which usually makes the
  conversation short, but have the answer ready rather than discovering the policy mid-term.

## What no configuration can decide for you

The floor. The pair policy. Whether a `UNANIMOUS_LOW` flag becomes a grade or a conversation.
Whether you run the practice round. How much of the arc each adjustment covers. Whether your
syllabus tells students all of this before the first team forms. And whether you are willing to
defend the resulting number to the student it was taken from — which is, in the end, the only test
that matters.

One last mechanical rule before any of it counts: run a full round with `--post` omitted, read the
report end to end, and only then post. And do that smoke test in a **published** course — Canvas
returns 403 when you try to grade a submission in an unpublished one, so negative-score behaviour
cannot be verified until the course is live.
