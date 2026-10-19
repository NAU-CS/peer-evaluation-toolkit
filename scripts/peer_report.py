#!/usr/bin/env python3
"""Run a peer-evaluation round: pull ballots from Canvas, reconcile, score, report, post.

    python3 peer_report.py tangible_draft                 # dry run, writes a report file
    python3 peer_report.py tangible_draft --post          # also posts adjustments + comments
    python3 peer_report.py tangible_draft --pair-policy neutralize

Dry run by default. Nothing is written to Canvas unless --post is given.
"""
import argparse, datetime as dt, json, os, pathlib, re, sys
from dotenv import load_dotenv

HERE = pathlib.Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))
from ags.canvas import Canvas                                    # noqa: E402
from ags.scoring import Ballot, validate_ballot, score_team, apply_factor  # noqa: E402
from ags.config import load as load_config, ConfigError            # noqa: E402
from ags.survey import POSITION as SURVEY                          # noqa: E402
from ags import peerreview                                         # noqa: E402
from ags.peerreview import (StudentRecord, PeerComment, correct_email,   # noqa: E402
                            normalize_email, meaningful, render_report,
                            parse_block, check_budget, html_to_text, SEP, SUB)

# Course wiring (ids, rounds, thresholds) lives in course.yml -- see ags/config.py.
# Nothing course-specific is hardcoded here, so this file is identical for every adopter.
# Survey question positions come from ags/survey.py, the one definition shared with
# provision.py, so the builder and the reader cannot drift apart again.
Q_BLOCK = SURVEY["block"]
Q_JUSTIFY = SURVEY["justification"]
Q_INSTRUCTOR = SURVEY["instructor"]


def answer_map(c, cid, quiz_id):
    """user_id -> {question_index: answer_text} from each student's latest attempt.

    Two Canvas quirks drive this implementation:

    * Answers do NOT live on /quizzes/:id/submissions. That endpoint accepts
      `include[]=submission_history` and silently ignores it -- the rows come
      back with no submission_data at all. The answers are only reachable
      through the Submissions API on the quiz's backing *assignment*.
    * Questions are keyed off question_name ("Q1".."Q20"), not `position`:
      Canvas does not persist `position` on questions created or updated
      through the API, so it reads back as None.
    """
    qs = {}
    for q in c.paginate(f"courses/{cid}/quizzes/{quiz_id}/questions"):
        m = re.fullmatch(r"Q(\d+)", (q.get("question_name") or "").strip())
        qs[q["id"]] = int(m.group(1)) if m else q.get("position")

    aid = c.get(f"courses/{cid}/quizzes/{quiz_id}").get("assignment_id")
    if not aid:
        raise SystemExit(f"quiz {quiz_id} has no backing assignment; cannot read answers")

    out = {}
    for sub in c.paginate(f"courses/{cid}/assignments/{aid}/submissions",
                          **{"include[]": "submission_history"}):
        hist = [h for h in (sub.get("submission_history") or [])
                if h.get("submission_data")]
        if not hist:
            continue
        latest = max(hist, key=lambda h: h.get("attempt") or 0)
        vals = {}
        for d in latest.get("submission_data") or []:
            pos = qs.get(d.get("question_id"))
            if pos is None:
                continue   # question outside the authored Q1..Q20 set
            v = d.get("text")
            if v in (None, ""):
                v = d.get("answer")
            vals[pos] = html_to_text(v)
        if vals:
            out[sub["user_id"]] = vals
    return out


def num(v):
    if v is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(v).replace(",", ""))
    return float(m.group(0)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("round", help="a key from the `rounds:` table in course.yml")
    ap.add_argument("--config", help="path to course.yml (default: auto-detect)")
    ap.add_argument("--post", action="store_true", help="write grades and comments to Canvas")
    ap.add_argument("--pair-policy", default=None, choices=("clamp", "neutralize", "full"),
                    help="override teams.pair_policy from course.yml")
    ap.add_argument("--floor", type=float, default=None, help="override scoring.floor")
    ap.add_argument("--ceiling", type=float, default=None, help="override scoring.ceiling")
    args = ap.parse_args()
    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        raise SystemExit(f"config: {e}")
    except CanvasError as e:
        raise SystemExit(f"Canvas: {e}")
    if args.round not in cfg.rounds:
        raise SystemExit(f"no round {args.round!r} in {cfg.path}.\n"
                         f"  defined: {', '.join(sorted(cfg.rounds))}")
    # Email parsing and repair follow the institution in course.yml.
    peerreview.configure(cfg.email.get("domain"))
    R = cfg.rounds[args.round]
    CID = cfg.course_id
    c = Canvas(base_url=cfg.base_url)
    # CLI flags win over the config file; the config supplies everything else.
    sk = cfg.score_kwargs()
    if args.floor is not None:
        sk["floor"] = args.floor
    if args.ceiling is not None:
        sk["ceiling"] = args.ceiling
    if args.pair_policy is not None:
        sk["pair_policy"] = args.pair_policy

    # ---- roster, keyed by email
    users = {u["id"]: u for u in c.paginate(f"courses/{CID}/users",
                                            **{"enrollment_type[]": "student",
                                               "include[]": "email"})}
    by_email, bad_email = {}, []
    for uid, u in users.items():
        e = normalize_email(u.get("email") or u.get("login_id") or "")
        if e:
            by_email[e] = uid
        if e and not peerreview.EMAIL_RE.match(e):
            bad_email.append((u.get("sortable_name"), e))
    known = set(by_email)

    # ---- teams for this arc
    teams = {}
    for g in c.paginate(f"group_categories/{R.group_category_id}/groups"):
        mem = [m["id"] for m in c.paginate(f"groups/{g['id']}/users")]
        if mem:
            teams[g["id"]] = dict(name=g["name"], members=mem)
    team_of = {uid: gid for gid, t in teams.items() for uid in t["members"]}

    # ---- team score on the covered deliverables (shared group grade)
    team_score, covered_total = {}, 0
    for aid in R.covered_ids:
        a = c.get(f"courses/{CID}/assignments/{aid}")
        covered_total += a.get("points_possible") or 0
        for s in c.paginate(f"courses/{CID}/assignments/{aid}/submissions"):
            gid = team_of.get(s["user_id"])
            if gid is None or s.get("score") is None:
                continue
            team_score.setdefault(gid, {})[aid] = s["score"]
    team_earned = {gid: sum(v.values()) for gid, v in team_score.items()}

    # ---- ballots
    answers = answer_map(c, CID, R.require("survey_quiz_id"))
    recs, corrections, cross_team, unresolved = {}, [], [], []
    for uid, u in users.items():
        e = normalize_email(u.get("email") or u.get("login_id") or "")
        recs[uid] = StudentRecord(email=e, name=u.get("sortable_name") or u.get("name") or "",
                                  user_id=uid,
                                  team=teams.get(team_of.get(uid), {}).get("name", ""))
    raw_ballots, budget_notes = {}, {}
    for uid, a in answers.items():
        rec = recs.get(uid)
        if rec is None:
            continue
        rec.submitted = True
        rec.justification = a.get(Q_JUSTIFY, "")
        rec.self_improvements = a.get(Q_INSTRUCTOR, "")
        mates = teams.get(team_of.get(uid), {}).get("members", [uid])
        mate_emails = [recs[m].email for m in mates if recs.get(m) and recs[m].email]

        ratings, strengths, improves, notes = parse_block(a.get(Q_BLOCK, ""), known)
        chk = check_budget(ratings, members=mate_emails)
        probs = list(chk["problems"])
        budget_notes[uid] = notes + probs
        for nte in notes:
            if nte.startswith("corrected "):
                corrections.append((rec.name, nte, "", ""))
            elif nte.startswith("unknown address"):
                unresolved.append((rec.name, nte, ""))


        entries = {}
        for email, pts in ratings.items():
            tid = by_email.get(email)
            if tid is None:
                continue
            if tid != uid and team_of.get(tid) != team_of.get(uid):
                cross_team.append((rec.name, email, recs[tid].name))
                continue
            entries[tid] = (pts, strengths.get(email, ""), improves.get(email, ""), "")
        if uid in entries:
            rec.self_points = entries[uid][0]
        raw_ballots[uid] = entries

    # ---- score each team
    lines, rows = [], []
    for gid, t in sorted(teams.items(), key=lambda kv: kv[1]["name"]):
        mem = t["members"]
        ballots = []
        for rater in mem:
            if rater not in raw_ballots:
                continue
            ratings = {m: raw_ballots[rater].get(m, (None,))[0] for m in mem}
            if any(v is None for v in ratings.values()):
                # Incomplete coverage: the ballot cannot be scored, but the student
                # DID submit one. Record it as an invalid ballot rather than skipping,
                # so they are not reported as a non-submitter -- completion credit and
                # the "did not submit" follow-up list both key off that distinction.
                uncovered = [m for m in mem if ratings.get(m) is None]
                recs[rater].problems.append(
                    "allocation did not cover every team member; ballot excluded "
                    "from scoring (submitted, but not counted)")
                ballots.append(Ballot(
                    rater_id=rater, ratings={}, valid=False,
                    justification=recs[rater].justification,
                    problems=[f"incomplete allocation: no rating for "
                              f"{', '.join((users.get(u, {}).get('email') or users.get(u, {}).get('name') or u) for u in uncovered)}"]
                    + budget_notes.get(rater, [])))
                continue
            b = validate_ballot(rater, ratings, mem,
                                justification=recs[rater].justification,
                                **cfg.ballot_kwargs())
            b.problems.extend(budget_notes.get(rater, []))
            ballots.append(b)
        res, tflags = score_team(mem, ballots, **sk)
        earned = team_earned.get(gid)
        for m in mem:
            r, rec = res[m], recs[m]
            rec.factor, rec.mean_received = r.factor, r.mean_received
            rec.n_ratings_counted = r.n_raters
            rec.self_counted = any(b.rater_id == m and b.valid and m in b.ratings
                                   for b in ballots)
            rec.flags = r.flags + [f"team: {f}" for f in tflags]
            valid_raters = {b.rater_id for b in ballots if b.valid}
            for rater in mem:
                if (rater in valid_raters and rater in raw_ballots
                        and m in raw_ballots[rater] and rater != m):
                    pts, st, im, ot = raw_ballots[rater][m]
                    rec.received.append(PeerComment(recs[rater].email, recs[rater].name,
                                                    st, im, ot, pts))
            rec.adjustment = (None if earned is None else
                              round(earned * r.factor - earned, 2))
            lines.append(render_report(rec, R.arc, R.phase, earned or 0,
                                       covered_total, anonymous=True))
            lines.append(render_report(rec, R.arc, R.phase, earned or 0,
                                       covered_total, anonymous=False))
            rows.append(dict(user_id=m, name=rec.name, email=rec.email, team=t["name"],
                             submitted=rec.submitted, n_raters=r.n_raters,
                             mean=round(r.mean_received, 2), factor=r.factor,
                             team_earned=earned, adjustment=rec.adjustment,
                             flags=rec.flags))

    # ---- summary
    S = [SEP, f"SUMMARY  {R.title}", SEP,
         f"teams with members       : {len(teams)}",
         f"ballots received         : {len(answers)} of {len(users)} students",
         f"covered deliverables     : {', '.join(x['name'] for x in R.covers)}"
         f"  ({covered_total:g} pts)",
         f"teams with a posted grade: {len(team_earned)} of {len(teams)}",
         f"pair policy              : {sk['pair_policy']}", ""]
    def block(title, items, fmt):
        S.append(f"{title}: {len(items)}")
        S.extend("  - " + fmt(i) for i in items)
        S.append("")
    block("Did not submit a ballot", [r for r in rows if not r["submitted"]],
          lambda r: f"{r['name']} <{r['email']}> team {r['team']}")
    block("Held / flagged", [r for r in rows if r["flags"]],
          lambda r: f"{r['name']}: {'; '.join(r['flags'])}")
    block("Allocation problems (budget / coverage / parsing)",
          [(recs[u].name, n) for u, ns in budget_notes.items() for n in ns],
          lambda x: f"{x[0]}: {x[1]}")
    block("Auto-corrected emails", corrections, lambda x: f"{x[0]} typed {x[1]} -> {x[2]} ({x[3]})")
    block("Cross-team address (NOT merged)", cross_team,
          lambda x: f"{x[0]} typed {x[1]}, which belongs to {x[2]} on another team")
    block("Unresolvable addresses", unresolved, lambda x: f"{x[0]} typed {x[1]} ({x[2]})")
    block("Roster emails not in NAU letters+digits@nau.edu form", bad_email,
          lambda x: f"{x[0]}: {x[1]}")
    S.append("ADJUSTMENTS TO POST")
    S.append(f"  {'student':<28}{'team':<16}{'factor':>7}{'adjust':>9}")
    for r in sorted(rows, key=lambda x: x["name"]):
        adj = "n/a" if r["adjustment"] is None else f"{r['adjustment']:+.2f}"
        S.append(f"  {r['name'][:28]:<28}{r['team'][:16]:<16}"
                 f"{(r['factor'] or 0):>7.2f}{adj:>9}")

    out = "\n".join(lines + [""] + S)
    rep = HERE / "reports"; rep.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    f = rep / f"{args.round}_{stamp}.txt"
    f.write_text(out)
    (rep / f"{args.round}_{stamp}.json").write_text(json.dumps(rows, indent=2, default=str))
    print("\n".join(S))
    print(f"\nfull report (anonymous + identified per student): {f}")

    if not args.post:
        print("\nDRY RUN -- nothing written to Canvas. Re-run with --post to apply.")
        return
    adj_id = R.require("adjustment_assignment_id")
    posted = 0
    for r in rows:
        if r["adjustment"] is None:
            continue
        rec = recs[r["user_id"]]
        comment = render_report(rec, R.arc, R.phase, r["team_earned"] or 0,
                                covered_total, anonymous=True)
        c.request("PUT", f"courses/{CID}/assignments/{adj_id}/submissions/{r['user_id']}",
                  data={"submission[posted_grade]": r["adjustment"],
                        "comment[text_comment]": comment})
        posted += 1
    print(f"\nposted {posted} adjustments to assignment {R.adjustment_assignment_id} "
          f"(manual post policy -- release them in the gradebook when ready)")


if __name__ == "__main__":
    try:
        main()
    except ConfigError as e:
        raise SystemExit(f"config: {e}")
