# How it works: the model and the mechanism

This document explains the pedagogy the toolkit implements, then the machinery that
implements it. Read it before you configure anything. Most of the decisions in the code
are answers to specific classroom or Canvas failures, and the code will look arbitrary
until you know which failure each piece is answering.

You do not need to program to follow this. You do need to make some judgement calls, and
this document tries to be explicit about which ones are yours.

---

## Part 1 — The pedagogical model

The model comes from Doerry and Palmer, *Improving Efficacy of Peer-Evaluation in Team
Project Scenarios* (ASEE 2011), the Design4Practice peer-evaluation schema at Northern
Arizona University. Five ideas do the work.

### Zero-sum allocation, with 100 as the anchor

Each student distributes a fixed budget of **team size × 100 points** across the whole
team, *including themselves*. A two-person team allocates 200, a three-person team 300, a
four-person team 400. The lines must add to exactly that total.

**100 means "did their fair share."** That is the anchor, and it is the number most
students should be typing for most teammates most of the time. Everything above it is
"took on work that was not theirs"; everything below it is "others absorbed work that was
theirs."

The zero-sum constraint is what makes the instrument honest. In an ordinary Likert-style
peer survey ("rate each teammate 1–5"), a rater who wants to avoid conflict gives everyone
a 5, and the instrument returns no information. Here, praising one teammate costs points
that must come out of somebody else — including possibly out of the rater. A rater cannot
be generous to everyone. They can only be generous to *someone*, and only by being less
generous to another named person. Grade inflation becomes arithmetically impossible rather
than merely discouraged.

Including yourself in your own budget matters for the same reason. A student who believes
they carried the team must say so by taking points away from the teammates they think
coasted, which is a claim they have to be willing to write down.

### The ratings must be anonymous to peers

Students will not report honestly about a teammate who will read their name next to the
number. The written feedback the toolkit returns to a student is aggregated with rater
names stripped; the instructor's copy of the same report shows names. There is a test in
`scripts/test_peerreview.py` (`test_reports_render_and_respect_anonymity`) whose only job
is to assert that no rater name, email, or instructor-only comment appears in the
student-facing copy.

Anonymity is a property of team size, not of your good intentions. At three or more
raters, an individual number is genuinely obscured by the averaging. At two, it is not —
see *Teams of two* below.

### Evaluation attaches to a deliverable, not to the term

The paper's term for the alternative failure is **negative carry-over**: when peer
evaluation happens once at the end of a semester, one bad fortnight taints a student's
entire record, and a student who was disengaged in week three and excellent thereafter
gets no credit for the recovery. Worse, a student who has already been written off by
their team has no incentive to recover at all.

So each round covers a specific, bounded set of deliverables — in the origin course, the
three "draft" parts of a project arc, then the two "final" parts, then the same again for
the next arc. A student who was a passenger on the draft and a workhorse on the final
gets a negative adjustment on the first and a positive one on the second. The slate is
genuinely clean each round, and students learn that within one semester, which is the
whole point.

### The peer score must be a multiplier, not a slice of the grade

This is the finding to take most seriously, because it is the one the paper reports
getting wrong first. Their earlier design ("Version 3") counted peer evaluation as its own
line item — a percentage of the course grade in its own right. Their verdict was that this
was **"simply not consequential enough."** Students noticed that a bad peer evaluation
cost them a point or two and no more, and adjusted their behaviour accordingly: which is
to say, they did not adjust it at all.

In the model this toolkit implements, the peer score is instead a **direct multiplier on
the credit for the deliverable the peers were evaluating**. The paper's own worked example:
a deliverable scored 85/100 by the instructor, a student whose mean received rating is 108
receives 91.8, and teammates whose mean is 96 receive 81.6. Same team product, different
individual credit, and the size of the difference scales with how much the deliverable was
worth. That is what makes the instrument consequential — and it is also what obliges you
to build in the safety rails described in Part 4, because a consequential instrument does
real damage when it is wrong.

### Ratings outside 80–120 require a written justification

The band 80–120 is treated as ordinary variation and needs no explanation. Outside it, the
rater must write why, in terms of tasks assigned and tasks completed. This does two
things: it slows down the student who was about to type 40 out of irritation, and it gives
you something concrete to bring to a conversation later. `ags/scoring.validate_ballot` can also demand a reason for *any* ballot that is not all
100s (`require_justification_for_any_nonequal_split`), on the argument that small teams
collude easily. It is off by default and `course.yml` does not expose it: turning it on
means most non-trivial ballots collect a "missing justification" note, which is either
useful pressure or noise you will learn to ignore.

---

## Part 2 — The Canvas implementation

### One shared team grade, plus a separate zero-point adjustment

Group deliverables keep **one shared grade for the whole team**. Everyone on the team sees
the same number on the Part 1 assignment, the Part 2 assignment, and so on, so a syllabus
can honestly promise that all teammates receive the same grade on group work.

Individual differentiation lives in a **separate assignment worth zero points**, one per
round, where the instructor enters a signed delta: `+2.43`, `0`, `-2.97`. Most students
get 0, and the assignment description says so in its first sentence
(`canvas/assignment-0pt-adjustment.html`).

### Why zero points is load-bearing

This is not a stylistic choice; it is arithmetic, and getting it wrong destroys the
mechanism twice over.

Canvas computes an assignment group's percentage as `sum(scores) / sum(points_possible)`
over graded submissions, then multiplies by the group weight. If the adjustment assignment
carries the deliverable's own point value, that value enters the **denominator** as well as
the numerator.

Measured on the origin course: a team sitting at 85% with a factor of exactly 1.00 — a
student who did precisely their share and whose adjustment is therefore 0 — saw its
Tangible group fall from **85.0% to 54.24%**, because the denominator went from 67 to 105.
A student who did nothing wrong lost thirty percentage points on the group for existing.

It simultaneously guts the consequence you were trying to create. With those extra points
in the denominator, a persistent 0.60 factor costs only **1.85 percentage points** of the
final grade — back to Version 3, "not consequential enough."

With `points_possible = 0`, the delta lands in the numerator only and the denominator is
untouched. That is the entire trick, and it is the single most important configuration
detail in the toolkit.

### How much of the arc to cover

The other consequence lever is **which deliverables each round's adjustment covers**.
Measured on the origin course, where the two group project arcs are 40% of the final grade
and the team is at 85%:

| Adjustment covers | Points covered | A persistent 0.60 student loses |
|---|---|---|
| Draft and Final deliverables only | 78 of 153 | 6.76 percentage points of final grade |
| The whole arc | 153 of 153 | 13.41 percentage points of final grade |

Full-arc coverage roughly doubles the consequence at an identical number of assignment
objects in Canvas — the same four adjustment assignments, twice the teeth. Whether you
want that much teeth is your call, and it is a genuine pedagogical decision rather than a
technical one. Decide it before the term starts and put the answer in your syllabus.

### The factor, precisely

For each student:

```
mean    = average of every rating that student RECEIVED
          (including their own self-rating, when include_self_rating is true)
factor  = clamp(mean / 100, floor = 0.60, ceiling = 1.10)
```

and the number posted to the zero-point assignment is

```
adjustment = round(team_points_earned x factor - team_points_earned, 2)
```

where `team_points_earned` is what the team scored on the deliverables this round covers.
Factor above 1.00 gives a positive number, exactly 1.00 gives 0, below 1.00 gives a
negative number.

Worked from the D4P guidelines example that `scripts/test_scoring.py` uses as its
reference case — a three-person team where two members report that the third
under-contributed:

| Student | Ratings received | Mean | Factor |
|---|---|---|---|
| Norbert | 98 (self), 80, 82 | 86.67 | 0.87 |
| Sally | 101, 110, 109 | 106.67 | 1.07 |
| Bob | 101, 110, 109 | 106.67 | 1.07 |

A useful invariant falls out of the zero-sum rule: when every ballot is legal, the team's
means sum to exactly N × 100 (`test_means_conserve_the_zero_sum`). The toolkit keeps means
at full precision internally for that reason and rounds only for display, so the posted
adjustments across a team sum to approximately zero. Only approximately: the clamps and
the two-decimal rounding break exact conservation, which is intended — the floor exists
precisely to stop a full transfer.

The asymmetric clamp (0.60 floor, 1.10 ceiling) is a policy choice you can change, and its
asymmetry is deliberate. A student can lose up to 40% of the team's credit and gain at most
10%. That reflects a belief that peer evaluation is more reliable at identifying
non-contribution than at identifying heroism, and that a team can inflate a favourite far
more easily than it can conspire to sink someone below the floor.

`apply_factor` also offers `cap_at_points_possible`, which prevents a high factor from
producing an individual score above the deliverable's maximum (11 of 13 × 1.10 = 11.88,
fine; 13 of 13 × 1.10 = 14.3, capped to 13). Note that `scripts/peer_report.py` posts the
uncapped delta computed against the covered total, so a team that scored near full marks
can hand a 1.10 student an adjustment that pushes them slightly above the covered points.
If that offends your gradebook, cap it before posting.

### End to end: from ballot to posted adjustment

1. **The student computes their allocation** in the point allocator
   (`allocator/index.html`), a single-file calculator with no backend. They pick their
   team size, optionally start from a pattern that already totals correctly, enter one row
   per teammate including themselves, and the *Copy* button stays disabled until the
   points total exactly team size × 100, every address matches your institution's email
   form, and no address is listed twice. Nothing is submitted, stored, or transmitted; it is a
   calculator. It is hosted outside Canvas and embedded in an `<iframe>` because Canvas
   serves uploaded HTML with `script-src 'none'`, so JavaScript in a Canvas-hosted file
   never runs.
2. **The student pastes the block into a Canvas survey** of three questions
   (`canvas/quiz-peer-evaluation-questions.json`): the allocation itself as `email = points`
   lines, then what each teammate did well, what each could do better, the justification
   for any rating outside 80–120, a private note to the instructor, and finally a numerical
   self-check where they type their own total. That last question accepts only 200, 300, or
   400 — Canvas quizzes cannot validate one question against another, and a numerical
   question with several exact answers is the only native cross-checking available. Two
   attempts are allowed so a wrong total is fixable by the student.
3. **You run the round.** `python3 scripts/peer_report.py <round>` pulls the roster, the
   teams for that arc, the shared team score on the covered deliverables, and every
   submitted ballot.
4. **Identity reconciliation.** Students mistype addresses. The parser tolerates `=`, `:`,
   `-`, dashes, tabs and wide gaps as separators, accepts a bare institutional username
   without the domain, repairs the common domain typos, resolves a partial id that is a unique prefix
   of exactly one roster address, and otherwise accepts a nearest match within Levenshtein
   distance 2. Anything it cannot resolve confidently is reported, not guessed. An address
   belonging to a real student on a *different* team is never merged — it is listed for you
   under "Cross-team address (NOT merged)."
5. **Validation and scoring**, per the rails in Part 4.
6. **Two reports per student** are written to a file: an anonymous copy showing their mean,
   rater count, factor, the arithmetic, and the aggregated written feedback with names
   stripped; and an instructor copy adding names, their self-rating, the self-versus-peer
   gap, their justification, and every flag.
7. **Nothing reaches Canvas** unless you add `--post`. The dry run is the default. With
   `--post`, each student's adjustment is written to the zero-point assignment along with
   their anonymous report as a submission comment.
8. **You review, then release.** The adjustment assignment should use a manual post policy
   so grades and comments sit unreleased until you have read the flags. Set that policy
   with the GraphQL `setAssignmentPostPolicy` mutation — `assignment[post_manually]` over
   REST returns success and silently does nothing.

---

## Part 3 — The signature dysfunction profile

The paper describes a specific pattern that recurs in dysfunctional teams, and it is worth
learning to recognise because it is the case where a naive average misleads you.

**The contributors spread their points to reflect uneven effort. The non-performer submits
a flat 100-across-the-board ballot.** The non-performer is not confused; a flat ballot is
the rational move when you know you under-contributed. It signals "nothing to see here,"
costs nothing, and — if the instrument only looks at averages — quietly dilutes the
signal, because the non-performer's own 100 is one of the ratings averaged into their mean.

The toolkit looks for the profile two ways, and needs both because each one misses cases
the other catches.

**`self_over_peer`** fires when a student's self-rating exceeds the mean of what their
peers gave them by 10 or more. In the Norbert example, Norbert rated himself 98 while his
teammates gave him 80 and 82 — a gap of 17. The threshold is configurable and was
tightened from the paper's 15 to 10 in the origin course, because a three-person team
compresses the gap.

**`flat_ballot_vs_team`** fires when a student's own ballot has a spread of exactly zero
while some teammate's ballot has a spread of 8 or more. It exists because on a team of
three the self-versus-peer gap is often too small to fire on its own. The regression test
`test_flat_ballot_against_disagreeing_team_is_flagged` is exactly this case: two
contributors submit ballots spreading 15 and 23 points, the third submits a perfectly flat
100/100/100, and only the third is flagged. Its companion test asserts that a genuinely
balanced team, where *everyone* submits a flat ballot, trips nothing — the flag is about
disagreement, not about flatness.

A third flag, `all_ratings_exactly_even`, fires at the team level when every valid ballot
on a team is entirely 100s. That is either an honestly even team or a collusion agreement,
and the toolkit cannot tell the difference. You can, usually, by looking at whether the
written feedback is specific.

---

## Part 4 — The safety rails, and the failure each one answers

Every rail below is enforced in `scripts/ags/scoring.py` and covered by tests. None of them
are hypothetical; each is a bug that reached a real ballot before it was caught.

| Rail | What it does | The failure it answers |
|---|---|---|
| **Clamp** | `factor = clamp(mean/100, 0.60, 1.10)` | An unclamped multiplier lets one furious rater or one adoring team set a student's credit without limit. |
| **Hold, do not rescale, a wildly wrong total** | A ballot more than 10% off the required total is marked invalid and held for human review. Smaller slips are rescaled proportionally. | A student on a three-person team typed `{100, 0, 0}` — a third of the required budget. Proportional rescaling turned it into `{300, 0, 0}`, which passed every check, put the rater at the ceiling and both honest teammates at the floor. A ballot that far off is not a slip; it is a misread instruction, and rescaling manufactures extreme data the student never intended. |
| **Re-check the range after rescaling** | The 0–200 bounds are verified again on the rescaled values, and the ballot is held if rescaling pushed anything out of bounds. | Rescaling is multiplication. A ballot that was in range before can leave it afterwards, and the original check had already passed by then. |
| **Coverage check** | Every team member must appear exactly once, and nobody else. Missing anyone invalidates the ballot; non-members are dropped with a note. | Summing to N × 100 is necessary but not sufficient. A student who omits themselves and inflates two teammates hits the target exactly. Verified by `test_omitting_yourself_is_caught_even_when_the_sum_is_right`. |
| **Quorum bound** | On a team of three or more with fewer than two ratings received, the factor is bounded to 1.00 ± 0.10. | One person's ballot should not set someone's whole factor. A single ballot of `{140, 80, 80}` would otherwise deliver a 0.80 factor on one opinion; bounded, it delivers 0.90 and a `below_quorum` flag. |
| **Teams of two policy** | Default `clamp` narrows the range to 0.80–1.10. `neutralize` forces 1.00. `full` applies the normal clamp. | See below. |
| **`UNANIMOUS_LOW`** | Flags any student every one of whose teammates independently rated below 80, with the instruction to confer before releasing. | At that point the issue is not a few points, and the paper's guidance is intervention rather than a number. The floor still holds — a unanimous 55 gives 0.60, not 0.55 — but a factor alone is the wrong response. |
| **Practice round** | `practice=True` forces every factor to 1.00. | Students need one round to learn the format on something that cannot hurt them, and you need one round to find out that your roster emails are wrong. |
| **Dry run by default** | `peer_report.py` writes nothing to Canvas without `--post`. | Grades are hard to unpost and impossible to unsee. |
| **No valid ballots** | Every factor defaults to 1.00 and the team is flagged. | Silence must not be scored as failure. |

Two behaviours that are deliberately *not* hard stops, so you know what you are getting:

- A **missing justification** for an extreme rating is recorded as a problem on the ballot
  but does not invalidate it. Canvas cannot enforce "write something here if a number over
  there is below 80," so this is a review item for you, not a gate.
- A student who **never submitted a ballot** still receives their teammates' ratings and
  still gets an adjustment, plus a `did_not_submit_evaluation` flag. Not submitting removes
  your voice from the calculation; it does not exempt you from it. That is a policy choice,
  it is stated plainly in the assignment description students read, and you should decide
  whether you agree with it before you adopt it.

### Teams of two, concretely

A two-person team breaks the anonymity premise, and no amount of configuration fixes it.
There is no averaging: your partner's rating of you *is* your mean, minus your own
self-rating. The recovery is one line of arithmetic — `2 × mean − self_rating` — and
`test_pair_ratings_are_trivially_derivable` asserts that it returns the partner's private
number exactly. Every student on a two-person team can therefore work out precisely what
their partner said about them from their own posted result.

The toolkit's response is to be honest rather than clever. Both members are always flagged
with `team_of_2: ratings are NOT anonymous`, the team gets a `team_size_2` flag, and the
adjustment assignment description tells students this outright: *"If your team has two
people, be aware your partner can work out your rating from their own result — that is
arithmetic, not a policy choice."*

Then you choose a policy, per round, with `--pair-policy`:

| Policy | Factor range on a pair | When to use it |
|---|---|---|
| `clamp` (default) | 0.80 – 1.10 | Pairs are expected in your course and accountability still matters, but you want retaliation to be able to cost less. |
| `neutralize` | forced to 1.00 | You would rather have no differentiation than non-anonymous differentiation. The written feedback still reaches both students. |
| `full` | 0.60 – 1.10 | You have a specific reason to treat a pair like any other team. |

The genuinely better fix is upstream: set a minimum team size of three and re-form teams
when attrition strands someone. The pair policies exist because attrition happens in week
nine and re-forming is not always possible.

---

## Part 5 — What this model does not do

Be clear about these with yourself, and with your students.

**It measures reported effort, not quality of work.** The team's grade on the deliverable
measures quality; that is your rubric's job. The factor redistributes that grade according
to who your students say did the work. A team that reports evenly on a bad project still
gets a bad grade, evenly.

**It measures what students are willing to report, which is not the same as what
happened.** Friendship inflates. Fear of retaliation deflates. Students differ culturally
and individually in how they rate themselves, and a student who habitually under-rates
themselves is penalised by an instrument that averages in their self-rating. Anonymity and
the zero-sum budget make honest reporting easier and dishonest reporting costlier; they do
not make it true.

**It is not a substitute for intervening during the project.** This is the important one.
Every flag in this system arrives at grading time, when the project is finished and nothing
can be fixed. If a student learns in week eleven that their team reported them at 0.60,
the system has documented a failure rather than prevented one. Run a practice round early
and a mid-arc round while there is still project left, read the flags the day they appear,
and treat `UNANIMOUS_LOW` and `flat_ballot_vs_team` as prompts for a conversation, not as
outputs. The assignment description tells students the same thing: raise contribution
problems during the project, when something can be done about them.

**It cannot distinguish collusion from harmony.** An all-100s team is either working well
or has agreed to say it is. Only the written feedback and your own knowledge of the team
separate them.

**The thresholds are judgement, not findings.** The floor of 0.60, the ceiling of 1.10, the
80–120 justification band, the 10-point self-versus-peer gap, the 10% rescale tolerance:
each is a defensible default from one course's experience, and each is yours to change. The
tests will tell you if you break the arithmetic. They cannot tell you if you have chosen
badly for your students.

**It does not decide the appeal.** A student who thinks an adjustment is wrong needs a
human, a deadline, and a rule about what evidence counts. The origin course gives one week
and asks for specifics about tasks assigned and completed. Write your own version into your
syllabus before the first round posts.
