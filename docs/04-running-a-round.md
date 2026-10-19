# Running a round

A *round* is one peer evaluation attached to one specific slice of a project: the
covered deliverables. The origin course runs four of them — draft and final for
each of two project arcs — because the model deliberately refuses to average a
whole semester into one number. Everything below is what you do, in order, after
students have submitted a round's evaluation quiz.

The whole operation is one command run twice: once to look, once to write. The
work that matters is what you do between the two runs.

---

## 1. The ordering constraint

**Grade the team deliverables before you run the script.** This is not a
stylistic preference; the adjustment is computed *from* the team's earned score:

```
adjustment = (team_earned x factor) - team_earned
```

`team_earned` is read live from Canvas: the script sums the posted submission
scores on every assignment listed in the round's `covers` map, per team. Three
things follow.

| Situation | What the script does |
|---|---|
| Every covered deliverable graded for every team | Correct adjustments |
| Some covered deliverables graded, others not | Silently computes off a *partial* team score — adjustments come out too small, and the student-facing comment says "Team earned 18 of 32" |
| A team has no posted score on any covered deliverable | The run **stops with `TypeError: unsupported format string passed to NoneType.__format__`** while rendering that student's report |

That crash is ugly but it is a feature: it is impossible to post adjustments for
a team you have not graded. The partial-grading case is the dangerous one,
because nothing warns you except the `teams with a posted grade` line in the
summary and the arithmetic inside each student's comment. Check both.

A team that submitted nothing still needs a number entered — enter `0`. Note the
consequence honestly: a team that earned 0 gets adjustments of 0 for everyone,
because `0 x factor - 0 = 0`. Peer evaluation cannot differentiate inside a team
that earned no credit. If you want the non-contributor on a zero-scoring team to
land somewhere different from their teammates, that is a separate conversation
and a separate gradebook entry, not this mechanism.

### Preconditions checklist

Before the first run of a round:

- [ ] The course is **published**. Canvas returns 403 when you try to grade
      submissions in an unpublished course, so `--post` cannot work and negative
      scores cannot be smoke-tested until you publish.
- [ ] The evaluation quiz is closed (past its `until` date) or you have accepted
      that late ballots will not be in this run. The script reads the *latest
      attempt* per student, so a student who resubmits after your run is only
      picked up if you run again.
- [ ] Team membership is frozen for this round. The script reads group
      membership at run time; a student who moved teams after voting produces
      cross-team ratings that are reported and dropped, not merged.
- [ ] Every covered deliverable is graded for every team (above).
- [ ] The 0-point adjustment assignment exists for this round, is **published**,
      has `points_possible = 0`, and has a **manual** post policy. Manual posting
      is what lets you read what you are about to publish before students see it.
      Set it with the GraphQL `setAssignmentPostPolicy` mutation —
      `assignment[post_manually]` over REST returns success and changes nothing.
- [ ] The round exists in the `ROUNDS` dictionary at the top of
      `scripts/peer_report.py`, with the right quiz id, adjustment assignment id,
      group category id, and `covers` map. The script does **not** read
      `config.yaml`; that file documents intent, `ROUNDS` is what executes. They
      are kept in sync by hand.

---

## 2. Dry run

```
cd scripts
python3 peer_report.py tangible_draft
```

Dry run is the default. Nothing is written to Canvas unless you pass `--post`.
You can run it as many times as you like, before grading, mid-grading, at 2am —
it only reads.

Every run writes two files, dry or not:

```
scripts/reports/tangible_draft_20261012-143507.txt     per-student reports + summary
scripts/reports/tangible_draft_20261012-143507.json    one row per student, machine-readable
```

The terminal shows the summary only. The `.txt` file contains the full
per-student reports *followed by* the same summary. The `.json` is the one to
open in a spreadsheet if you want to sort by factor or diff two rounds; each row
carries `user_id, name, email, team, submitted, n_raters, mean, factor,
team_earned, adjustment, flags`.

Options:

| Flag | Default | What it does |
|---|---|---|
| `--post` | off | Writes grades and comments to Canvas |
| `--pair-policy clamp\|neutralize\|full` | `clamp` | How teams of two are handled (see below) |
| `--floor` | `0.60` | Lower bound on the factor |
| `--ceiling` | `1.10` | Upper bound on the factor |

Set floor and ceiling once, before the first graded round, and leave them alone.
Changing them between rounds means two cohorts of students were graded by
different rules, and you will have to explain that to whoever asks.

---

## 3. Read the summary

The terminal output has a fixed shape. Here is what each section means and what
it asks of you.

### Header

```
SUMMARY  Tangible Board Game -- Draft
teams with members       : 9
ballots received         : 24 of 27 students
covered deliverables     : Part 1, Part 2, Part 3  (32 pts)
teams with a posted grade: 9 of 9
pair policy              : clamp
```

Read `teams with a posted grade` against `teams with members` every time. If
those two numbers differ, you have an ungraded team and the run either crashed or
is about to produce a nonsense comment. `ballots received` counts quiz
submissions, not valid ballots — a student can submit garbage and still be
counted here.

### Did not submit a ballot

One line per student with no quiz submission. These students still receive their
teammates' ratings and still get an adjustment; not voting removes your voice
from the calculation, it does not exempt you from it. Each also carries the
`did_not_submit_evaluation` flag, and separately loses the completion points on
the quiz itself, which you grade as its own assignment.

Action: none required for the adjustment. This list is your evidence when a
student later asks why they had no say.

### Held / flagged

Every student with at least one flag. This is the section you actually work
through. Flags come in two kinds and they are formatted differently:

- Personal flags (`low_mean_received(83.3)`, `self_over_peer(...)`,
  `UNANIMOUS_LOW: ...`) belong to that student.
- Team flags are prefixed `team:` and are copied onto **every member of the
  team**, so one bad ballot flags all three teammates. Do not read three lines as
  three problems.

| Flag | Meaning | Your move |
|---|---|---|
| `did_not_submit_evaluation` | No ballot from this student | Note it; grade the quiz accordingly |
| `low_mean_received(x)` | Mean received below 85 | Read the written comments before releasing |
| `self_over_peer(self=115, peers=88.0)` | Rated themselves at least 10 above what teammates gave them | Usually a self-awareness gap, not misconduct. Useful in a conversation |
| `flat_ballot_vs_team(own_spread=0, teammates_up_to=30)` | This student submitted a flat 100-across-the-board ballot while teammates reported uneven effort | The signature dysfunction profile. Read the teammates' narratives; this is frequently the non-contributor |
| `UNANIMOUS_LOW: all N teammates rated below 80` | Every teammate independently, without seeing each other's ballots | Conference before releasing. See below |
| `no_ratings_received` | Nobody rated this student, including themselves | Investigate: usually a roster/group mismatch, not apathy |
| `below_quorum: only 1 rating(s)` | Team of 3+, fewer than 2 raters | Factor already bounded to 1.00 ± 0.10 |
| `team_of_2: ratings are NOT anonymous...` | Always present on pairs | Informational; the pair policy already applied |
| `team: invalid_ballot(rater=1234567): ... HOLD FOR INSTRUCTOR REVIEW` | A ballot was rejected and excluded from scoring | Work the hold queue (§5) |
| `team: ballot_problem(rater=1234567): total was 295, not 300; rescaled proportionally` | A small slip was rescaled and *used* | Spot-check that the rescale matches what the student meant |
| `team: all_ratings_exactly_even` | Every ballot on the team was all-100s | Possible even team, possible collusion, possible everyone clicking through. Look at whether the narrative comments say anything |
| `team: no_valid_ballots` | Nothing survived validation on this team | Every factor on that team defaulted to 1.00. Decide whether to accept that or reopen the quiz |

Note the wart: ballot-level team flags identify the rater by **numeric Canvas
user id**, not by name. Look the id up in the `.json` sidecar (`user_id` →
`name`) or in the per-student blocks of the `.txt`.

### Allocation problems (budget / coverage / parsing)

Everything the parser noticed, per student, in plain language:

- `lines total 280, but a team of 3 must distribute exactly 300`
- `no line for dmr7@nau.edu -- every team member must be rated, including yourself`
- `cpo59@nau.edu is not on this team`
- `could not read a 'email = points' pair from: 'I think everyone did fine'`
- `dmr7@nau.edu listed more than once; keeping the last value`
- `stated total 300 does not match the lines, which add to 295  -- check which one is the mistake`
- `stated total 300 is legal but wrong for a team of 4 (needs 400)`

Canvas cannot validate one question against another, so the arithmetic is enforced
by the allocator before the student copies anything out, and re-checked here. What
`peer_report.py` adds is the check Canvas never could: that the lines total
200/300/400; the script is what compares the student's stated total against what
their lines actually add to. A mismatch tells you which of the two the student
got wrong — often the lines are right and the arithmetic was sloppy, which is
harmless, and sometimes it is the reverse, which is not.

An entry here is *not* by itself a hold. Small sum errors get rescaled and used;
coverage failures and large sum errors are what get held. Cross-reference with
the Held / flagged block to see which is which.

### Auto-corrected emails / Cross-team address / Unresolvable addresses

Email reconciliation, in three severities:

- **Auto-corrected** — the typed address was repaired: a bare id got `@nau.edu`
  appended, `@nau.ed` was fixed, a unique prefix was expanded, or a typo within
  Levenshtein distance 2 was snapped to a roster address. These were used. Skim
  them; a correction that snapped to the *wrong* teammate is the one thing here
  that can silently misassign points, and it is rare but not impossible on a team
  whose members have similar ids.
- **Cross-team address (NOT merged)** — the typed address resolves to a real
  student on a *different* team. The rating is dropped, never merged. If that
  student was rating a teammate and fat-fingered it into someone else's id, the
  ballot loses coverage and gets held. Read these carefully.
- **Unresolvable addresses** — no roster match within threshold. The rating is
  dropped.

These three lines are formatted a little awkwardly (you will see a trailing
`-> ()` or `()` where a field was left empty). The information is all in the note
text.

### Roster emails not in `letters+digits@nau.edu` form

A roster hygiene check, hardcoded to `nau.edu` in `ags/peerreview.py`. **At any
other institution this will list your entire roster.** Change the `NAU_EMAIL`
regex to your own address form before your first round, or the block becomes
noise you learn to ignore — which is exactly when it would have caught a real
problem. Note that the bare-id shortcut ("students may type `abc123` without the
domain") also appends `@nau.edu`, so it needs the same edit.

### ADJUSTMENTS TO POST

The payload, one line per student:

```
ADJUSTMENTS TO POST
  student                     team             factor   adjust
  Alvarez, Bea                Team 3             1.09    +2.43
  Okonkwo, Chi                Team 3             1.02    +0.54
  Rao, Dev                    Team 3             0.89    -2.97
```

Two sanity checks on this table:

1. **Per team, the adjustments should net to about zero.** When every ballot on a
   team is legal, the means received sum to exactly N x 100, so the factors sum to
   N and the deltas cancel. `+2.43 +0.54 -2.97 = 0.00` above. A team that does
   *not* net to zero had something bind: a clamp at the floor or ceiling, a
   quorum bound, or an excluded ballot. That is intended, but you should be able
   to name which one for each team that fails the check.
2. **Most rows should read `1.00` and `+0.00`.** If most of your class is being
   adjusted, either you have a real cohort problem or students misunderstood the
   instrument. Either way, it is worth finding out before you post.

---

## 4. The report pair: anonymous and identified

For every student, the `.txt` file contains **two** blocks back to back.

**The anonymous copy** is what students see. It is what gets posted as the
submission comment on the adjustment assignment. It carries the student's own
name (it is on their own submission), the number of ratings received, the mean,
the factor, the arithmetic, the posted adjustment, and the teammates' written
strengths and improvements **with the raters' names stripped**.

```
============================================================
PEER REVIEW REPORT
Tangible Board Game -- Draft
Student: Alvarez, Bea
------------------------------------------------------------
Ratings received: 1 (including your own self-rating)
Mean rating      : 109.0
Factor           : 1.09
------------------------------------------------------------
Team earned 27 of 32 on the covered deliverables.
27 x 1.09 = 29.43
ADJUSTMENT POSTED: +2.43
------------------------------------------------------------
WHAT YOUR TEAMMATES SAID YOU DID WELL:
  - built the whole card deck
------------------------------------------------------------
AREAS FOR IMPROVEMENT:
  (none)
============================================================
```

**The identified copy** is headed `(INSTRUCTOR COPY -- NAMES SHOWN)` and is never
sent anywhere. It adds: the student's email and team name, `[Rater Name]` in
front of every comment, the instructor-only "other comments" channel (Q5,
explicitly promised never to be shared with teammates), whether the student
submitted their own ballot, their self-rating, the peer mean excluding self and
the gap between them, their self-assessment text, their justification text, and
the FLAGS and BALLOT PROBLEMS lists.

Everything a student is entitled to see is in the anonymous copy. Everything you
need in order to make a judgement is in the identified copy. Keep the `.txt` and
`.json` files where students cannot reach them; they de-anonymize the round
completely. They are written to `scripts/reports/`, which should be gitignored —
confirm that before your first real round.

Two counting quirks that will otherwise confuse you:

- The comment's `Ratings received:` line counts **teammates**; the summary table
  and the JSON `n_raters` include the student's **own self-rating**. So a student
  on a team of 3 who voted, in a round where one teammate did not vote, shows
  `n_raters: 2` in the JSON and `Ratings received: 1` in their comment. Both are
  right about different things. The mean is computed over ratings *including*
  self, matching the paper.
- `examples/worked-round.md` shows the "you did not submit an evaluation" variant
  of that line for two students who did in fact submit. The current code prints
  `(including your own self-rating)` for anyone whose own self-rating is in the
  mean. Trust the code; that example transcript predates the current wording.

---

## 5. The hold queue and the flags

Nothing in this toolkit resolves a hold for you. The script's contract is that it
never invents data: a ballot it cannot trust is excluded and reported, never
quietly repaired.

### A held ballot

A ballot is held — marked invalid, excluded from scoring, reported — when:

- it does not rate every team member exactly once (including the rater
  themselves), or
- it is **more than 10% off** the required N x 100 total, or
- any rating is outside 0–200, or
- rescaling a small slip would push a rating outside 0–200, or
- the ratings total zero.

The 10% rule is the important one. A ballot 5 points off on a 300-point budget
was a slip and gets rescaled proportionally, with the rescale reported and the
range re-checked afterwards. A ballot reading `{100, 0, 0}` on a team of three is
not a slip — the student misread the instrument. Rescaling that to `{300, 0, 0}`
would put the rater at the ceiling and both honest teammates at the floor, from
data the student never intended. So it is held. (This is a real regression, fixed
and locked down by tests; if you change `max_rescale_pct`, read
`test_scoring.py::TestSafetyRails` first.)

**What a hold costs:** the team is scored from the surviving ballots. On a team
of three where one of three ballots is held, the other two still meet quorum and
the full factor range applies to everyone. On a team of three where two are held,
the survivors trip `below_quorum` and every factor on that team is bounded to
1.00 ± 0.10 automatically.

**How to handle one, in order of preference:**

1. **Ask the student to resubmit.** The evaluation quiz is configured with two
   attempts precisely so a bad total is fixable by the student. Email them what
   the report says — the problem text is already written in plain language — give
   them a deadline, then re-run the round. This is the only route that gets their
   voice back into the calculation.
2. **Accept the exclusion.** Re-run nothing; the factors already computed from the
   surviving ballots are legitimate. Tell the student their ballot did not count
   and why. Their own factor is unaffected by their ballot being held except that
   their self-rating no longer appears in their own mean.
3. **Override in the gradebook.** After posting, type a different number into the
   adjustment cell yourself. Use this when you have information the ballots do
   not have. If you do it, edit or add a comment: the automatically posted comment
   shows arithmetic that no longer matches the number in the cell.

There is no path where you edit the student's essay answer. The toolkit reads
Canvas quiz submissions; it does not rewrite them.

### A non-submitter

Nothing to resolve. They receive ratings, get an adjustment, carry the
`did_not_submit_evaluation` flag, and lose the quiz's own completion points.
Their comment will read `(you did not submit an evaluation, so your own rating is
not among them)`, which is the mechanism explaining itself. This is worth saying
out loud in class before the first graded round: the students most likely to skip
the evaluation are the ones whose factor most needs their own voice in it.

### A team where nobody submitted

The team flag reads `no_valid_ballots: all factors defaulted to 1.00`, and every
member's adjustment is `+0.00`. That is a defensible default — absent evidence,
no differentiation — but it is also a total loss of information about a team that
may well have had problems. Options: reopen the quiz for that team with a
deadline and re-run; or accept the zeros and note that the team declined the
opportunity. Do not hand-invent factors for a team that gave you no data.

### A `UNANIMOUS_LOW` flag

Every teammate, independently, without seeing each other's ballots, rated this
student below 80. The factor has almost certainly hit the 0.60 floor. The flag
exists because at that point the correct response is a conversation, not a
number.

Practically: hold the whole round back from release until you have talked to the
student, or release everyone else and leave that one submission unposted (the
adjustment column posts per-submission, so you can post selectively). Read the
identified copy first — the narrative comments and the Q5 instructor-only channel
usually explain the situation more precisely than the numbers do — and read the
student's own self-assessment before the meeting. The floor is doing real work
here: even a unanimous 50 stops at 0.60, which on a 40%-weighted project arc is a
large but survivable hit, and that is deliberate.

### Teams of two

Pairs are structurally different and the flag says so on every single pair,
always: **ratings on a team of two are not anonymous**. Each partner can derive
the other's ballot exactly from their own posted result. That is arithmetic, not
a policy failure, and the student-facing assignment description says so plainly.

Choose one policy for the whole term with `--pair-policy`:

| Policy | Factor range on a pair | When to choose it |
|---|---|---|
| `clamp` (default) | 0.80 – 1.10 | Pairs are expected in your course and accountability still matters. Narrows the damage a single retaliatory ballot can do without removing consequence |
| `neutralize` | forced to 1.00 | You judge that non-anonymous mutual rating is not usable evidence at all |
| `full` | 0.60 – 1.10 | Pairs are rare exceptions and you want them treated identically to everyone else |

Whatever you choose, use the same flag on every round and say which one you chose
in the syllabus.

### Below quorum

Fewer than two raters on a team of three or more. The factor is bounded to
1.00 ± 0.10 automatically, because one voice should not set another student's
whole grade. Nothing to do, but it is your cue that the round is thin on that
team, and it interacts with holds: exclusions can push a team below quorum.

---

## 6. Post

When the hold queue is worked and you are prepared to defend every line of the
ADJUSTMENTS TO POST table:

```
python3 peer_report.py tangible_draft --post
```

This writes, for each student, both the grade and the anonymous comment in a
single Canvas call, and prints how many it posted. Because the adjustment
assignment has a manual post policy, students see neither the score nor the
comment yet.

Two things to know:

- **`--post` is idempotent for the grade and additive for the comment.** Re-run
  it and the score is overwritten with the same value, but a *second copy* of the
  comment is appended. If you re-run, delete the duplicate comments by hand or
  accept that students see the report twice.
- **The `--pair-policy`, `--floor`, and `--ceiling` you pass to `--post` must
  match the ones you passed to the dry run you actually read.** The flags change
  the numbers; the script does not remember what you looked at.

Keep the `.txt` and `.json` from the run you posted. They are your record of what
was posted and why, and the identified copy is what you will want in hand if a
student appeals.

---

## 7. Review, then release

1. Open the gradebook and find the adjustment column. Confirm it shows
   `0` points possible and that the hidden-grades indicator is on.
2. Spot-check three cells against the ADJUSTMENTS TO POST table: one positive,
   one exactly zero, one negative. Negative scores in Canvas are legitimate but
   are the thing most worth seeing with your own eyes once — and they cannot be
   tested at all in an unpublished course.
3. Check one student's *total*. A student on a team at 85% with a factor of
   exactly 1.00 and an adjustment of 0 must see **no change at all** to their
   assignment group percentage. If their group percentage moved, the adjustment
   assignment is not actually worth 0 points, and you should stop and fix that
   before releasing anything. This is the single most valuable check in the whole
   runbook.
4. Post the column: the adjustment column's menu → **Post grades**. You can post
   for everyone, or leave individual submissions unposted (the
   `UNANIMOUS_LOW` case).
5. Tell students the round is released, in an announcement, with the appeal
   window you promised. The origin course uses one week, with the instruction to
   bring specifics about tasks assigned and completed.

One honest artifact to expect: because the delta lands on a 0-point item, it is
not capped at the deliverable's points possible. A team that earned 32/32 with a
student at factor 1.10 produces `+3.20`, so that student's effective project
credit is 35.2 out of 32 and their group percentage exceeds 100%. Canvas is fine
with this; some students will ask about it. The alternative — capping — would mean
a student who did more than their share on a perfect deliverable receives nothing
for it, which is worse.

---

## 8. Worked walkthrough

From `examples/worked-round.md`. A team of three on the Tangible draft, covered
deliverables worth 32 points, team grade posted as 27. Bea and Chi submitted
ballots; Dev never did. The typed input was deliberately messy.

**What Bea typed:**

```
abc12@nau.edu = 110
cpo59@nau.edu = 100
dmr7@nau.edu = 90
```

Clean: three lines, one per member including herself, totalling exactly 300.

**What Chi typed:**

```
abc12@nau.edu: 108
cpo59 = 104
dmr7@nau.edu - 88
```

Three different separators (`:`, `=`, `-`) and a bare NAU id with no domain. The
parser accepts all of it: `cpo59` normalizes to `cpo59@nau.edu`, which matches
the roster exactly, and the total is 300. The summary reports the repair under
Auto-corrected emails; nothing is held.

**What the script computes:**

| Student | Ratings received | Mean | Factor | Adjustment |
|---|---|---|---|---|
| Alvarez, Bea | 2 (self 110 + Chi 108) | 109.0 | 1.09 | **+2.43** |
| Okonkwo, Chi | 2 (Bea 100 + self 104) | 102.0 | 1.02 | **+0.54** |
| Rao, Dev | 2 (Bea 90 + Chi 88) | 89.0 | 0.89 | **-2.97** |

The team grade stays 27/32 for all three — the shared grade is untouched, exactly
as the syllabus promises. The three adjustments sum to 0.00, which is the
zero-sum invariant holding: no clamp bound, no ballot excluded, quorum met.

**The only flag:** `Rao, Dev: did_not_submit_evaluation`.

**What this round asks of you:** almost nothing. There is no hold, no
`UNANIMOUS_LOW`, no cross-team address. Dev's 0.89 comes from two independent
teammates who both put him slightly below his share and both wrote something
specific about why ("missed the second build session", "went quiet after the
prototype"). That is the instrument working as designed: a modest, evidenced,
defensible 3-point consequence, delivered with the reasons attached. You read the
summary, confirm the sum-to-zero, run `--post`, spot-check Dev's negative cell,
and release.

Note what Dev's comment will *say*: `Ratings received: 2 (you did not submit an
evaluation, so your own rating is not among them)`. He is told, in the same
comment that delivers the -2.97, that he had a vote and did not use it.

---

## 9. Cadence and what stays your judgement

Run each round as soon as the covered deliverables are graded, not at the end of
term. The model's whole claim is that evaluation attached to a specific
deliverable avoids the negative carry-over of a single end-of-term judgement, and
that only holds if students get the feedback while the next deliverable is still
in front of them. A round released three weeks late is a grade change, not
feedback.

Budget roughly 20 minutes for a clean round of nine teams and an hour for one
with two holds and a conference to schedule.

What the toolkit will never decide for you:

- Whether a held ballot gets a resubmission window, and how long.
- Whether an `all_ratings_exactly_even` team was even or was colluding.
- What to do about the student the flat-ballot flag has correctly identified.
- Whether a `UNANIMOUS_LOW` becomes a floor factor, an academic-integrity
  conversation, a team restructure, or a withdrawal discussion.
- Whether your pair policy is `clamp` or `neutralize`.
- Whether a team that earned 0 should be differentiated by other means.

The script's job is to make the arithmetic honest, reproducible, and inspectable,
and to refuse to guess. Everything above the arithmetic is teaching.

---

## Command reference

```
cd scripts

# look, change nothing
python3 peer_report.py tangible_draft

# same, with a different pair policy
python3 peer_report.py tangible_draft --pair-policy neutralize

# write grades + comments to Canvas (still hidden from students)
python3 peer_report.py tangible_draft --post

# confirm the grade math before you trust a round: 83 tests, no Canvas needed
python3 -m unittest test_scoring test_peerreview -v
```

Round keys come from the `ROUNDS` dictionary in `scripts/peer_report.py`; the
script rejects anything else with a usage error listing the valid ones.
Credentials come from `scripts/.env` (`CANVAS_BASE_URL`, `CANVAS_TOKEN`) — see
`.env.example`. The Canvas token is scrubbed out of every error message the
client raises, so report output and tracebacks are safe to paste to a colleague.
