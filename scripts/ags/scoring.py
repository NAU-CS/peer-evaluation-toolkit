"""Zero-sum peer-evaluation scoring (Doerry & Palmer, ASEE 2011, Version 4).

Pure functions -- no Canvas, no I/O -- so the grade math is unit-testable.

Vocabulary:
  rating   an integer number of points one student assigns to one teammate
  ballot   one rater's complete distribution of N*100 points across the team
  factor   clamp(mean of ratings a student RECEIVED / 100, floor, ceiling)
"""
from dataclasses import dataclass, field


@dataclass
class Ballot:
    rater_id: int
    ratings: dict
    justification: str = ""
    valid: bool = True
    problems: list = field(default_factory=list)
    normalized_from: dict = None


@dataclass
class MemberResult:
    user_id: int
    mean_received: float
    factor: float
    n_raters: int
    self_rating: int = None
    peer_mean_excl_self: float = None
    submitted_ballot: bool = False
    flags: list = field(default_factory=list)


def _redistribute(scaled, target):
    """Round a scaled distribution to integers summing exactly to target."""
    floors = {k: int(v) for k, v in scaled.items()}
    residual = target - sum(floors.values())
    order = sorted(scaled, key=lambda k: (-(scaled[k] - floors[k]), k))
    for k in order[:residual]:
        floors[k] += 1
    return floors


def validate_ballot(rater_id, ratings, members, justification="",
                    justify_below=80, justify_above=120,
                    require_justification_for_any_nonequal_split=False,
                    max_rescale_pct=10.0):
    """Check one ballot against the zero-sum rules; rescale a bad sum if we can."""
    b = Ballot(rater_id=rater_id, ratings=dict(ratings), justification=justification or "")
    n = len(members)
    target = n * 100

    missing = [m for m in members if m not in b.ratings or b.ratings[m] is None]
    extra = [k for k in b.ratings if k not in members]
    if missing:
        b.valid = False
        b.problems.append(f"did not rate {len(missing)} team member(s)")
        return b
    if extra:
        for k in extra:
            b.ratings.pop(k)
        b.problems.append("ignored ratings for non-members")

    for m, v in b.ratings.items():
        if float(v) != int(v):
            b.problems.append("non-integer rating rounded")
        if v < 0 or v > 200:
            b.valid = False
            b.problems.append(f"rating {v} outside 0-200")
    b.ratings = {m: int(round(float(v))) for m, v in b.ratings.items()}
    if not b.valid:
        return b

    total = sum(b.ratings.values())
    if total != target:
        if total <= 0:
            b.valid = False
            b.problems.append("ratings total zero")
            return b
        # A ballot that is wildly off target was not a slip -- the student misread the
        # instructions. Proportional rescaling of such a ballot manufactures extreme
        # factors from data the student never intended, so hold it for a human instead.
        off_pct = abs(total - target) / target * 100.0
        if off_pct > max_rescale_pct:
            b.valid = False
            b.problems.append(
                f"total {total} is {off_pct:.0f}% off the required {target}; "
                f"too far off to rescale safely -- HOLD FOR INSTRUCTOR REVIEW")
            return b
        b.normalized_from = dict(b.ratings)
        scaled = {m: v * target / total for m, v in b.ratings.items()}
        b.ratings = _redistribute(scaled, target)
        b.problems.append(f"total was {total}, not {target}; rescaled proportionally")
        # range must hold AFTER rescaling too -- rescaling can push a value out of bounds
        out = {m: v for m, v in b.ratings.items() if v < 0 or v > 200}
        if out:
            b.valid = False
            b.problems.append(f"rescaling pushed {out} outside 0-200 -- HOLD FOR INSTRUCTOR REVIEW")
            return b

    extreme = [m for m, v in b.ratings.items() if v < justify_below or v > justify_above]
    nonequal = any(v != 100 for v in b.ratings.values())
    needs_reason = extreme or (require_justification_for_any_nonequal_split and nonequal)
    if needs_reason and len(b.justification.strip()) < 20:
        b.problems.append("missing required justification")

    return b


def score_team(members, ballots, floor=0.60, ceiling=1.10,
               include_self_rating=True, practice=False,
               low_mean_received=85, self_minus_peer_gap=10,
               flag_all_even=True, flat_ballot_spread=8,
               min_raters=2, single_ballot_cap=0.10, pair_policy="clamp",
               pair_floor=0.80, pair_ceiling=1.10, unanimous_low=80):
    """Turn a team's ballots into a factor per member, plus instructor flags."""
    valid = [b for b in ballots if b.valid]
    submitted = {b.rater_id for b in ballots}
    results = {}

    # Section 3.4's signature dysfunction profile: contributors spread their
    # points to reflect uneven effort while the non-performer submits a flat
    # 100-across-the-board ballot. Detect it per rater, not just team-wide --
    # in a team of 3 the self-minus-peer gap alone is often too small to fire.
    spreads = {b.rater_id: (max(b.ratings.values()) - min(b.ratings.values()))
               for b in valid}

    for m in members:
        received = [(b.rater_id, b.ratings[m]) for b in valid if m in b.ratings]
        if not include_self_rating:
            received = [(r, v) for r, v in received if r != m]

        self_rating = next((v for r, v in received if r == m), None)
        peers = [v for r, v in received if r != m]
        peer_mean = sum(peers) / len(peers) if peers else None
        mean = (sum(v for _, v in received) / len(received)) if received else 100.0

        factor = 1.0 if practice else min(max(mean / 100.0, floor), ceiling)

        # Teams of two are a special case: there is no averaging, and each member can
        # invert the other's ballot exactly from their own posted result. Accountability
        # still matters most here, though, so the default narrows the range rather than
        # removing it. "neutralize" forces 1.00; "full" applies the normal clamp.
        if len(members) == 2 and not practice:
            if pair_policy == "neutralize":
                factor = 1.0
            elif pair_policy == "clamp":
                factor = min(max(factor, pair_floor), pair_ceiling)
        # Below quorum, one voice would set someone's whole factor. Bound how far it can move.
        elif len(members) >= 3 and len(received) < min_raters and not practice:
            factor = min(max(factor, 1.0 - single_ballot_cap), 1.0 + single_ballot_cap)

        # mean_received / peer_mean stay at full precision: the sum of the means
        # across a team is exactly N*100 when every ballot is legal, and that
        # invariant is worth preserving for reconciliation. Round at display time.
        res = MemberResult(
            user_id=m, mean_received=mean, factor=round(factor, 4),
            n_raters=len(received), self_rating=self_rating,
            peer_mean_excl_self=peer_mean, submitted_ballot=m in submitted,
        )

        if not res.submitted_ballot:
            res.flags.append("did_not_submit_evaluation")
        if len(members) == 2:
            res.flags.append(
                f"team_of_2: ratings are NOT anonymous, no averaging; policy={pair_policy}"
                + (f" (range {pair_floor:.2f}-{pair_ceiling:.2f})" if pair_policy == "clamp" else ""))
        elif len(members) >= 3 and len(received) < min_raters:
            res.flags.append(
                f"below_quorum: only {len(received)} rating(s); factor bounded to "
                f"1.00 +/- {single_ballot_cap:.2f}")
        if received and mean < low_mean_received:
            res.flags.append(f"low_mean_received({mean:.1f})")
        if self_rating is not None and peer_mean is not None \
                and (self_rating - peer_mean) >= self_minus_peer_gap:
            res.flags.append(f"self_over_peer(self={self_rating}, peers={peer_mean:.1f})")
        if not received:
            res.flags.append("no_ratings_received")
        # Every teammate independently rating someone below the threshold is the paper's
        # cue for instructor intervention, not just a smaller number.
        if peers and len(peers) >= 2 and all(v < unanimous_low for v in peers):
            res.flags.append(
                f"UNANIMOUS_LOW: all {len(peers)} teammates rated below {unanimous_low} "
                f"(max {max(peers)}) -- conference with the student before releasing")
        if m in spreads and spreads[m] == 0:
            others = [v for r, v in spreads.items() if r != m]
            if others and max(others) >= flat_ballot_spread:
                res.flags.append(
                    f"flat_ballot_vs_team(own_spread=0, teammates_up_to={max(others)})")
        results[m] = res

    team_flags = []
    for b in ballots:
        if not b.valid:
            team_flags.append(f"invalid_ballot(rater={b.rater_id}): {'; '.join(b.problems)}")
        elif b.problems:
            team_flags.append(f"ballot_problem(rater={b.rater_id}): {'; '.join(b.problems)}")
    if len(members) < 3:
        team_flags.append(f"team_size_{len(members)}: ratings are NOT anonymous at this size")
    if flag_all_even and valid and all(
            all(v == 100 for v in b.ratings.values()) for b in valid):
        team_flags.append("all_ratings_exactly_even (possible collusion or throwaway)")
    if not valid:
        team_flags.append("no_valid_ballots: all factors defaulted to 1.00")

    return results, team_flags


def apply_factor(team_score, points_possible, factor,
                 cap_at_points_possible=True, decimals=2):
    """Team deliverable score x factor -> individual score."""
    if team_score is None:
        return None
    raw = team_score * factor
    if cap_at_points_possible and points_possible is not None:
        raw = min(raw, points_possible)
    return round(raw, decimals)
