# The gradebook math

This is the part of the toolkit that fails silently if you get it wrong. Everything else — the
allocator, the quiz, the parser, the flags — produces a number. This document is about where that
number lands in Canvas, and what it is worth once it gets there.

The short version: the adjustment assignment must be worth **zero points**, it must live in the **same
assignment group** as the deliverables it modifies, and how much it matters is entirely determined by
two things you choose — which deliverables it covers, and where you set the floor. Work through the
arithmetic below with your own weights before you run a live round. It takes twenty minutes and it is
the difference between a mechanism that changes behaviour and one that quietly does nothing.

## 1. What Canvas actually computes

With weighted assignment groups, Canvas does two steps.

**Step one, per group:**

```
group percentage = sum of scores on GRADED submissions in that group
                   -------------------------------------------------
                   sum of points_possible of those same submissions
```

**Step two, the course total:** each group percentage is multiplied by its weight and the results are
added. If the weights of the groups that have graded work add up to less than 100, Canvas scales the
result up to 100; if they add up to more than 100 (a bonus group, for instance) it does not scale down.

Two consequences matter here and are easy to miss:

- **Points_possible of a graded submission is in the denominator whether or not the student earned
  anything.** A zero-point item adds to the numerator and nothing to the denominator. That single
  asymmetry is the whole design.
- **Only graded submissions count.** Mid-semester, group percentages are computed over a partial
  denominator, so a delta posted in week 6 looks larger than the same delta at the end of term. The
  figures in this document are end-of-term steady state.

The origin course, for reference throughout. Group work is 40% of the final grade, split across two
assignment groups (`canvas/examples/assignment-group-weights.json`), and each group holds five graded
team deliverables (`scripts/course.yml`):

| Assignment group | Weight | Deliverables | Points in group |
|---|---:|---|---:|
| Tangible Game | 15% | Parts 1–5 (9, 10, 13, 10, 25) | 67 |
| Graphical (Construct) Game | 25% | Parts 1–5 (11, 25, 20, 10, 20) | 86 |

A team that scores a uniform 85% earns 56.95 of 67 in the Tangible group. That group contributes
0.85 × 15 = **12.75 percentage points** to every team member's final grade. The peer-evaluation quizzes
themselves are not in these groups — they carry 4 completion points each into *Participation and
Attendance* (10%), so that they cannot dilute the deliverable denominator.

## 2. Why the adjustment assignment must be worth 0 points

The intuitive setup is wrong. If you give the adjustment assignment the point value of the deliverable
it modifies — 13 points for the Draft, 25 for the Final — you have just added 38 points to the
denominator of a 67-point group. Here is the same student, who did precisely their share (factor 1.00,
adjustment 0.00), under both setups. This is the measured collapse from the origin course.

| Line item | Wrong: points_possible = deliverable value | | Right: points_possible = 0 | |
|---|---:|---:|---:|---:|
| | **Score** | **Possible** | **Score** | **Possible** |
| Part 1 — Team Document | 7.65 | 9 | 7.65 | 9 |
| Part 2 — Prototype | 8.50 | 10 | 8.50 | 10 |
| Part 3 — Draft | 11.05 | 13 | 11.05 | 13 |
| Part 4 | 8.50 | 10 | 8.50 | 10 |
| Part 5 — Final | 21.25 | 25 | 21.25 | 25 |
| Peer Review Adjustment — Draft | 0.00 | **13** | 0.00 | **0** |
| Peer Review Adjustment — Final | 0.00 | **25** | 0.00 | **0** |
| **Group total** | **56.95** | **105** | **56.95** | **67** |
| **Group percentage** | **54.24%** | | **85.00%** | |
| Contribution to final grade (15%) | 8.14 of 15 | | 12.75 of 15 | |

A student who did nothing wrong loses **4.61 percentage points** of final grade in the Tangible group
alone. Do the same thing in the Graphical group (denominator 86 → 126, 58.02%) and the same innocent
student loses another 6.75. Total: **11.36 percentage points** for having a peer evaluation exist. You
will get grade appeals, and they will be correct.

It also guts the mechanism it was supposed to deliver. In the broken setup, a persistent 0.60 student
in that Tangible group ends at 41.93% instead of 54.24% — a cost of **1.85 percentage points** of final
grade. In the correct setup the same student, same coverage, ends at 65.72% instead of 85.00%, a cost
of **2.89 points**. The broken version charges everyone 4.61 and the free rider only 1.85 more than
their teammates. That is the failure mode Doerry and Palmer describe as "simply not consequential
enough," reproduced by an accident of arithmetic.

For comparison, the paper's Version 3 — peer evaluation as its own slice of the course grade — has the
same problem by construction. A 5%-weighted peer-evaluation group in which a non-contributor scores 60%
costs them 2.0 percentage points of final grade, whatever the team was worth. The multiplier design
exists to escape that ceiling.

## 3. Where the adjustment assignment has to live

The zero-point trick has a consequence that follows from the same formula: **a group whose graded items
all have points_possible = 0 has a denominator of zero and produces no percentage at all.** If you park
the adjustment assignments in their own tidy "Peer Review" assignment group, Canvas cannot compute a
percentage for that group, the group is skipped, and every delta you post is silently discarded. The
adjustment must sit in the same weighted group as the deliverables whose credit it is moving.

Four settings on that assignment, each of which will break it if wrong:

| Setting | Value | Why |
|---|---|---|
| Points | **0** | Section 2. |
| Display grade as | Points | A percentage or letter display of a 0-point item is meaningless and will confuse students. |
| Grading type | Graded (not "Not Graded") | A *Not Graded* assignment cannot hold a score, so you cannot enter a delta at all. |
| "Do not count this assignment towards the final grade" | **unchecked** | It removes the item from the numerator too. That is the mechanism. |

If the item lives in a module with a completion requirement, use **mark as done**. Nothing is submitted
here, so *must submit* would leave it permanently incomplete. (Empirically, *mark as done* is also the
only requirement type that will complete a not-graded item — but you are not using a not-graded item.)

`canvas/assignment-0pt-adjustment.html` is a real, working description for this assignment, including the
five-row worked example students see. It says out loud that most students will receive a 0 and that this
is the expected result. Keep that framing; it prevents most of the anxious email.

## 4. Choosing coverage: which deliverables the factor multiplies

A round's adjustment is `team points earned on the covered set × (factor − 1)`. Which deliverables are in
the covered set is your decision, and it is the single biggest lever on how much any of this matters. In
the code it is the `covers` list on a round in `scripts/course.yml` — nothing else needs editing.

Two defensible choices, both measured on the origin course for a student at a persistent 0.60 with the
team at 85%:

| Coverage | Covered points | Adjustment assignments needed | Final-grade cost at factor 0.60 |
|---|---:|---:|---:|
| The graded Draft and Final deliverables only | 78 of 153 | 4 | **6.76 points** |
| The whole project arc, all five parts per project | 153 of 153 | 4 | **13.41 points** |

Full-arc coverage roughly doubles the consequence for the same number of objects in the gradebook, which
is why the shipped configuration uses it: `tangible_draft` covers Parts 1–3, `tangible_final` covers Parts
4–5, and likewise for the second project. The narrow version is worth considering if your early
deliverables are individually completed and only assembled as a team, or if the early parts are
credit-for-effort and a multiplier on them would feel arbitrary.

(The model in section 5, applied with a flat 85% on every deliverable, gives 6.85 and 13.60 for these two
rows. The measured figures are slightly lower because the real team's points were not distributed evenly
at exactly 85% across all ten deliverables. Use the model to choose; expect the live number to land
within a few tenths.)

What coverage should *not* do is stretch across the whole term. Evaluation attached to a specific
deliverable is what stops one bad fortnight from following a student to December — the "negative
carry-over" the paper is explicitly trying to avoid. Four independent rounds of two projects each is a
different instrument from one end-of-term judgement, even if the arithmetic looks similar.

## 5. Setting the floor for your course

`factor = clamp(mean of ratings received / 100, floor, ceiling)`, default floor 0.60 and ceiling 1.10
(`scoring.py`, `score_team`). The floor is not a moral statement, it is a cap on how much of the final
grade one round of peer evaluation is allowed to move. Compute what yours costs before you defend it.

For each assignment group `g` that contains peer-evaluated group work:

```
w   = the group's weight, in final-grade percentage points
P   = total points_possible of all graded items in the group, by end of term
C   = points_possible of the deliverables the adjustment covers, within that group
t   = a typical team percentage on that group (use last term's median, not 100%)

exposure K = sum over groups of ( w x t x C / P )
final-grade cost of a floor f = K x (1 - f)
```

With full-arc coverage `C = P`, so this collapses to `K = (total weight of group work) × t`. For the
origin course, 40% × 0.85 = **34.0**. Every floor choice then reads straight off one multiplication:

| Floor | Worst-case final-grade loss | An otherwise-85% student ends at |
|---:|---:|---:|
| 0.90 | 3.40 | 81.6 |
| 0.80 | 6.80 | 78.2 |
| 0.70 | 10.20 | 74.8 |
| 0.60 | 13.60 | 71.4 |
| 0.50 | 17.00 | 68.0 |
| none (0.00) | 34.00 | 51.0 |

Two things to weigh. A defensible floor moves a persistent non-contributor at least one full letter grade
on a ten-point scale — that is the "consequential enough" test, and on this course 0.60 clears it with
room to spare while 0.90 does not. But the same number has to survive a hearing with a dean when the
student says three nineteen-year-olds decided it, so a floor that can move someone two or three letters
in a single round is a liability. 0.60 with full-arc coverage sits at one and a half letters. If your
group work is 60% of the grade rather than 40%, K is 51 and a 0.60 floor costs 20.4 points — you probably
want a higher floor, not the default.

Note that exposure scales with team performance: a team at 60% has K = 24 on the origin course, so the
same floor costs their free rider less in absolute terms. The mechanism is proportional to the credit
being redistributed, which is the intent, but it does mean the strongest teams police themselves hardest.

The ceiling works the same way in the other direction: the most a factor of 1.10 can add is
`0.10 × K` = 3.4 points on this course.

## 6. Positive adjustments and group percentages above 100%

A positive delta on a zero-point item can push a group percentage over 100%. The maximum is
`(ceiling − 1) × C / P`; with full-arc coverage and a team at full marks, a 1.10 factor puts the group at
110% and adds up to 4 percentage points to a final grade. Canvas handles this without complaint.

Your options, in the order I would consider them:

1. **Accept it.** The zero-sum model is symmetric on purpose: the student who carried the team is exactly
   as visible as the one who did not. If your course already permits above-100% totals (the origin course
   has a 2% bonus group), this is nothing new.
2. **Cap the individual total at the deliverable's points possible.** `apply_factor(...,
   cap_at_points_possible=True)` implements this and is tested — `apply_factor(13, 13, 1.10)` returns
   13.0, not 14.3. **Be aware that `peer_report.py` does not currently call it.** The posted number is
   `round(earned × factor − earned, 2)`, uncapped, and the `grading.cap_at_points_possible` key in
   `course.yml` is not read by the CLI. Wiring the cap in is a small code change; if you need it,
   make the change and re-run the tests rather than assuming the config key does something.
3. **Set the ceiling to 1.00.** The mechanism becomes purely subtractive. This is defensible and
   administratively simpler, but be honest with students about it: it tells the person who carried the
   team that their effort earns nothing, which is the complaint that starts most of these conversations.

Do not solve an above-100% group by giving the adjustment assignment points. See section 2.

## 7. Manual posting

Adjustments must be hidden until the entire round is reconciled. Release them piecemeal and students
compare notes and reconstruct who rated whom — the arithmetic is not hard in a team of three, and in a
team of two it is trivial by construction.

- Set the adjustment assignment's grade posting policy to **Manually**. Do this in the gradebook column
  menu, or with the GraphQL `setAssignmentPostPolicy` mutation. The REST field `assignment[post_manually]`
  is silently ignored: the request returns success and the value does not change. Verify it before you
  post anything.
- A manual policy hides the submission comment as well as the score, which matters because the whole peer
  report is delivered as that comment.
- `python3 peer_report.py <round>` is a dry run and writes nothing to Canvas. `--post` writes every
  grade and comment at once, including the `0.00` entries, so every student receives their report. Then
  release the column in one action (**Post grades → Everyone**) and announce it.
- With a manual policy the student's visible course total excludes hidden scores, so their number moves at
  release. That is another reason to release the whole column at once rather than as you review.
- Canvas refuses to grade submissions in an unpublished course (403). You cannot smoke-test negative
  scores in a draft shell. Test in a published sandbox course with a test student before your first live
  round — including one negative delta, one zero, and one positive, and check the group percentage after
  each.

## 8. When a student disputes an adjustment

The student already has the arithmetic: the comment posted by `render_report` shows how many ratings they
received, the mean, the factor (marked `[clamped]` when the floor or ceiling bound), the multiplication,
and the anonymised strengths and improvement comments. Start by reading it back to them, because roughly
half of these conversations end there.

What to say, in substance: this number is not my assessment of you and it is not a punishment. It is the
average of what your teammates independently reported about the distribution of work, applied to credit
the team earned together. The team grade did not change; everyone still has the same score on the
deliverable, exactly as the syllabus says.

What you will disclose: the number of ratings, the mean, the floor and ceiling, whether the clamp bound,
and the aggregated comments. What you will not disclose, ever: who gave which number. In a team of two,
tell them plainly that their partner can derive their rating from their own posted result — that is
arithmetic, not a policy choice, and it is why `score_team` flags every pair and narrows the range to
0.80–1.10 by default.

Grounds that actually change an adjustment:

- a factual error — wrong team membership, wrong team score, a student who joined or left mid-round
- a ballot that should have been held and was not: a total off target, a member omitted, a rating out of
  range. The validator catches these, but check the round's report file rather than assuming
- evidence of a bad-faith ballot, usually retaliation. The `flat_ballot_vs_team` and `self_over_peer` flags
  are where this surfaces; a ballot you would not defend should be excluded and the round rescored
- documented circumstances you would have accommodated had you known at the time

Not grounds: disagreeing with teammates' perception of who did what, in the absence of any of the above.
That is the measurement working.

Two practical habits make disputes survivable. First, every run writes a timestamped report and JSON to
`scripts/reports/`; keep them, because they are your record of exactly what was computed from exactly
what input, and the CLI is deterministic and re-runnable. Second, when the `UNANIMOUS_LOW` flag fires —
every teammate independently rated someone below 80 — have the conversation *before* releasing the grade.
At that point the issue is not a few points, and a scheduled conversation is a far better instrument than
a surprise negative number.

## 9. What this document cannot decide for you

- The floor, the ceiling, and the coverage set are course-design judgements. The arithmetic above tells
  you what each choice costs; it does not tell you what your programme considers proportionate.
- Every number here is end-of-term steady state. Mid-semester percentages run on a partial denominator
  and Canvas rescales when the graded groups' weights sum below 100, so early deltas look bigger than
  they finish.
- The measured origin-course figures (54.24%, 6.76, 13.41) come from one course with one weighting
  scheme. Reproduce them for your own course with your own weights before you rely on them, and verify in
  a published sandbox with a test student.
- Nothing in the toolkit prevents you from posting an adjustment that is arithmetically correct and
  pedagogically wrong. The flags exist to slow you down at exactly those moments; read the report before
  you pass `--post`.
