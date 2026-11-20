# What to change before you run this again

Everything here comes from two live rounds in IMG-186 (Fall 2026): a 32-point
Tangible Board Game draft with 9 teams, and a 56-point Construct Game draft with
10 teams. 43 valid ballots in total. Nothing below is speculative — each item is
something that actually went wrong, or a promise the code did not keep.

Ordered by how much damage it does if you leave it alone.

---

## Student-facing

### 1. Tell students what happens when almost nobody rates them

**What went wrong.** A student received exactly one peer rating — a 50 — and the
code handed him a factor of 0.75 and an adjustment of **−13.25** on a 56-point
set. One teammate's opinion, unmoderated, worth a quarter of a letter grade on
half the project.

The assignment description already promised this could not happen: *"A single
harsh rating cannot sink you."* The quorum guard meant to deliver that promise
was counting the student's own self-rating as a rater, so a single peer cleared
a threshold of two. That is fixed in code (`ags/scoring.py`), and the student's
adjustment became −5.30.

**What to add to the description.** The guard exists; students should know it
does:

> If fewer than two teammates rate you, your factor is held within 0.10 of 1.00.
> One person's opinion does not decide your grade.

Say it where the floor and ceiling are explained, in the same breath.

### 2. Say that sharply contradictory ratings are not averaged

**What went wrong.** On one team, a student was rated **60** by one teammate
("has not done any work on the project thus far") and **150** by another, who
wrote plainly that he was inflating her *to cancel out the first rating*. The
mean of those two numbers is not a measurement of anything. The code averaged
them anyway and produced the largest positive adjustment in the round.

Ratings now land in front of the instructor instead of in the gradebook when one
teammate places someone clearly below a fair share and another clearly above.
The thresholds reuse the 80/120 band the survey already publishes.

**What to add:**

> If your teammates disagree sharply about you — one says well below a fair
> share, another says well above — no number is posted automatically. Dr. Duval
> reads the ballots and decides.

This is worth saying out loud for a second reason: it removes the incentive to
inflate. A student who knows that cancelling out a teammate's rating will
*stop* the adjustment rather than reverse it has no reason to try.

### 3. Tell students that counter-inflating destroys the signal

**What went wrong.** The student who rated his teammate 150 explained exactly
why: *"I'm counteracting [teammate]'s underscoring of [teammate]… all extra
points are going to [teammate] to counteract."* His instinct — protect a teammate having a hard
time — was decent. The effect was not: it pushed her to the ceiling, dragged
*him* to the round's largest penalty (−7.20, because his own allocation left
himself at 80), and made the team's data unusable for everyone on it.

Nothing in the student-facing text told him that would happen.

**What to add, near the budget rule:**

> Rate what you actually saw. If you think a teammate is being judged unfairly,
> do not try to cancel it out with a high number — that distorts everyone's
> result including theirs, and it costs you points, because every point you add
> to one person comes out of your own. Use the last question instead: it goes
> only to Dr. Duval, and it is the right place for context.

### 4. Fix the stale sentence about the survey rejecting your total

The Point Distribution Guide still says:

> The survey also asks you to type the total. If your total is not 200, 300 or
> 400 the survey will reject it on the spot — that is your safety net.

There is no such question any more. The numerical checksum was removed when the
allocator took over enforcement, and the guide was not updated. A student who
relies on that safety net does not have one.

### 5. Say what happens when a ballot does not balance

**What went wrong.** Four students across the two rounds submitted ballots that
could not be counted, every one of them because they left a teammate out. One
typed *"[teammate's name] (I don't know his email)"* into the allocation. They were
reported as having *not submitted* — in writing, to their face — until that was
fixed.

The report now names the teammate they omitted and tells them to use the
calculator. The description should set the expectation up front:

> Your ballot has to include a line for every teammate, including yourself, and
> the lines must total your team size × 100. If it does not balance we cannot
> use it — you still get the completion credit, but your ratings will not count
> toward anyone's grade. The calculator will not let you finish until it
> balances, so use it.

### 6. Decide what you want to say about team totals

**The honest situation.** The description gives students a per-student formula:
`(team points earned × factor) − team points earned`. It does not promise that a
team's adjustments sum to zero, and in two rounds they usually did — but not
always. Where someone's mean exceeded 110, their gain was capped at the ceiling
while their teammates' losses ran free, so two teams netted **−7.20** and
**−7.95**. Those teams lost points collectively.

This was left alone deliberately: forcing the team sum to zero would mean a
student's posted number no longer matches the formula they were given, and a
student who checks the arithmetic should find it correct.

So this is a writing decision, not a coding one. Either:

- say plainly that the clamp is one-sided and a team can net negative, or
- make the clamp symmetric (e.g. 0.80–1.20), which costs you severity at the
  bottom, or
- promise team-zero-sum in the description *and then* implement the
  redistribution, in that order.

Do not implement it without changing the description first.

---

## Codebase

### 7. `cap_at_points_possible` is config that does nothing

`course.yml` carries `grading.cap_at_points_possible: true`. `apply_factor()`
implements it and is tested. `peer_report.py` never calls it — it computes
`earned × factor − earned` directly, uncapped. A live adjustment of +5.40 on a
team that earned 54 of 56 takes the covered total to 59.4.

Either wire it up (and change the description, which states the uncapped
formula), or delete the key so it stops looking like a working setting.

### 8. The allocator should warn before a student does something costly

The calculator enforces the budget, which is what stopped most bad ballots. It
does not warn about the two things that actually distorted results:

- **A self-rating at or near the maximum.** One student allocated herself 160 of
  400 and gave each teammate 80. A soft warning ("you have given yourself
  significantly more than a fair share — is that what you mean?") costs nothing
  and would make a student think twice.
- **A rating outside 80–120.** The survey requires justification for these, but
  the student does not find that out until a later question. Say it at the
  moment they type the number.

### 9. `provision.py apply` cannot update what already exists

It skips any assignment or quiz whose title already matches. That is right for
not clobbering a live round, but it means a wording fix to the survey has to be
made by hand in four places. An `--update-text` mode that rewrites question
bodies from `ags/survey.py` without touching anything else would make item 1–5
above a one-command change next year.

### 10. Validate the round before it runs, not after

Both rounds were nearly run against incomplete data: the first with an ungraded
deliverable that would have halved every adjustment, the second against a group
set that had 40 groups and no members in them a month earlier. Both were caught
by hand.

`peer_report.py` should refuse to `--post` when a covered deliverable is
ungraded for anyone on a team, and warn loudly when a team has no members or no
ballots. The checks exist as ad-hoc scripts in the session history; they belong
in the tool.

### 11. Two copies of this code exist and have diverged

`~/Developer/AccountableGradingSystem` is the original working copy;
`~/Developer/img186-allocator` is this repository, and is what now runs the
rounds. The first does not have `ags/config.py` and never got the config
refactor. Keeping both invites editing the wrong one — which happened at least
once. Delete or archive the original.

### 12. Teams of two need a decision, not a default

Three Construct teams had two people. At that size there is no averaging and
each partner can derive the other's rating from their own posted result. The
`pair_policy=clamp` default narrows the range to 0.80–1.10, which is a
reasonable compromise, but it is a compromise, and the one team of two that
produced a full set of ballots rated each other 100/100 anyway.

Consider whether teams of two should be evaluated at all, or whether the right
answer is to not let teams get that small — which is a roster-management
problem, not a scoring one.
