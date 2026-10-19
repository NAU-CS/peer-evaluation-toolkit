#!/usr/bin/env python3
"""Build the Canvas objects for one peer-evaluation round set, in YOUR course.

    python3 provision.py plan          # show what would be created, touch nothing
    python3 provision.py apply         # create it
    python3 provision.py verify        # re-read Canvas and check every object

Reads course.yml (start from course.example.yml). Creates, per round:
  * a 0-point "Peer Review Aggregate Grade Adjustment" assignment in the project's
    assignment group, with manual posting
  * a graded_survey peer evaluation built from ags/survey.py, the layout peer_report.py reads
  * module placement with a completion requirement

Idempotent: an object whose name already exists is reported and skipped, so a failed
run can be repeated safely.
"""
import argparse, json, os, pathlib, sys
import requests, yaml
from dotenv import load_dotenv

HERE = pathlib.Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))
from ags.canvas import Canvas, CanvasError
from ags.config import load as load_config, ConfigError
from ags import survey  # noqa: E402

# A record of what was created, for your reference. course.yml is the source of
# truth that the other scripts read; nothing depends on this file.
STATE = HERE / "provision.state.json"

def adj_text(r, cfg):
    covered = r.covered_points
    rows = "".join(f'<tr><td>{d["name"]}</td><td style="text-align:center;">{d["points"]}</td></tr>'
                   for d in r.covers)
    e = round(covered * 0.85, 2)
    lo = cfg.scoring.get("floor", 0.60)
    hi = cfg.scoring.get("ceiling", 1.10)

    def row(desc, mean, f):
        adj = round(e * f - e, 2)
        cell = "0" if abs(adj) < 0.005 else f"{'+' if adj > 0 else '&minus;'}{abs(adj):.2f}"
        return (f'<tr><td>{desc}</td><td style="text-align:center;">{mean}</td>'
                f'<td style="text-align:center;">{f:.2f}</td>'
                f'<td style="text-align:center;"><strong>{cell}</strong></td></tr>')
    return (f"<h2>Peer Review Grade Adjustment</h2>"
            f"<p><strong>Most students will receive a 0 here, and that is the expected result.</strong> "
            f"This assignment is worth <strong>0 points</strong>. It exists so credit on the "
            f"{r.arc} {r.phase.lower()} deliverables can move up or down for the students whose "
            f"teammates report they did substantially more, or less, than their share. If your team "
            f"worked evenly, your score here is 0 and nothing changes.</p>"
            f"<h3>What this adjusts</h3>"
            f"<p>Your team receives <strong>one shared grade</strong> on each group deliverable &mdash; "
            f"everyone gets the same number. This is the only place individual contribution changes "
            f"anything.</p>"
            f'<table><tbody><tr><th>Deliverable</th><th style="text-align:center;">Points</th></tr>'
            f'{rows}<tr><td><strong>Total covered</strong></td>'
            f'<td style="text-align:center;"><strong>{covered}</strong></td></tr></tbody></table>'
            f"<h3>How the number is calculated</h3><ol>"
            f"<li>Each teammate distributed N &times; 100 points across the team including themselves. "
            f"100 means &ldquo;did their fair share.&rdquo;</li>"
            f"<li>We average <em>every</em> rating you received, including your own self-rating.</li>"
            f"<li>Your <strong>factor</strong> is that mean / 100, limited to "
            f"<strong>{lo:.2f}&ndash;{hi:.2f}</strong>.</li>"
            f"<li>Your adjustment is <code>(team points earned &times; factor) &minus; team points "
            f"earned</code>.</li></ol>"
            f"<p><strong>Factor above 1.00 &rarr; positive points. Exactly 1.00 &rarr; zero. "
            f"Below 1.00 &rarr; negative points.</strong></p>"
            f"<h3>Worked example</h3><p>Suppose your team earned <strong>{e:g} of {covered:g}</strong>.</p>"
            f'<table><tbody><tr><th>What your teammates reported</th>'
            f'<th style="text-align:center;">Mean</th><th style="text-align:center;">Factor</th>'
            f'<th style="text-align:center;">Entered as your grade</th></tr>'
            + row("You carried extra load", "109.0", min(1.09, hi))
            + row("Even team (the usual case)", "100.0", 1.00)
            + row("You contributed noticeably less", "86.7", max(0.87, lo))
            + row("<strong>Every teammate rated you very low</strong>", "55.0", lo)
            + f'</tbody></table>'
            f"<p>The bottom row is the floor: the factor stops at {lo:.2f} no matter how low ratings go. "
            f"A unanimous low rating brings a conversation, not just a number.</p>"
            f"<h3>What you will see</h3><ul>"
            f"<li>A comment showing your mean, how many teammates rated you, your factor, and the "
            f"arithmetic.</li>"
            f"<li>Anonymous aggregated feedback from your teammates.</li>"
            f"<li><strong>You will never be told who gave which number.</strong> On a two-person team "
            f"your partner can derive your rating from their own result &mdash; that is arithmetic, "
            f"not a policy choice.</li></ul>"
            f"<h3>If you did not submit a peer evaluation</h3>"
            f"<p>You still receive your teammates&rsquo; ratings and the adjustment still applies. Not "
            f"submitting removes your voice from the calculation; it does not exempt you from it.</p>")


def graphql_manual_post(aid):
    r = requests.post(os.environ["CANVAS_BASE_URL"].rstrip("/") + "/api/graphql",
                      json={"query": "mutation($id:ID!){setAssignmentPostPolicy(input:"
                                     "{assignmentId:$id, postManually:true})"
                                     "{postPolicy{postManually} errors{message}}}",
                            "variables": {"id": str(aid)}},
                      headers={"Authorization": f"Bearer {os.environ['CANVAS_TOKEN']}"}, timeout=30)
    return r.status_code == 200 and "errors\":null" in r.text.replace(" ", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("plan", "apply", "verify"))
    ap.add_argument("--config", help="path to course.yml (default: auto-detect)")
    a = ap.parse_args()
    try:
        cfg = load_config(a.config)
    except ConfigError as e:
        raise SystemExit(f"config: {e}")
    except CanvasError as e:
        raise SystemExit(f"Canvas: {e}")
    CID = cfg.course_id
    PROV = cfg.provisioning
    missing = ([k for k in ("participation_group_id", "completion_points") if not PROV.get(k)]
               if a.action in ("plan", "apply") else [])
    if missing:
        raise SystemExit(
            f"provisioning.{' and provisioning.'.join(missing)} must be set in {cfg.path}\n"
            "  provision.py creates the survey in your participation group and gives it a\n"
            "  small completion credit. See the `provisioning:` block in course.example.yml.")
    # `plan` is a pure dry run: it must work before an adopter has set up a token.
    c = None
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    existing_a, existing_q, mods = {}, {}, {}
    if a.action != "plan":
        c = Canvas(base_url=cfg.base_url)
        existing_a = {x["name"]: x for x in c.paginate(f"courses/{CID}/assignments")}
        existing_q = {x["title"]: x for x in c.paginate(f"courses/{CID}/quizzes")}
        mods = {m["name"]: m["id"] for m in c.paginate(f"courses/{CID}/modules")}

    if a.action == "verify":
        bad = 0
        want = [q.canvas_name for q in survey.QUESTIONS]
        for key, r in cfg.rounds.items():
            qid, aid = r.survey_quiz_id, r.adjustment_assignment_id
            print(f"\n{key}")
            if not qid or not aid:
                print("   FAIL  ids present in course.yml (run `provision.py apply`)")
                bad += 1
                continue
            adj = c.get(f"courses/{CID}/assignments/{aid}")
            q = c.get(f"courses/{CID}/quizzes/{qid}")
            qs = list(c.paginate(f"courses/{CID}/quizzes/{qid}/questions"))
            names = [x.get("question_name") for x in qs]
            checks = {
                "adjustment is 0 points": adj.get("points_possible") == 0,
                # Without this the adjustment is visible before you have reviewed the
                # flags, and a negative number lands on a student with no conversation.
                "adjustment posts manually": adj.get("post_manually") is True,
                f"survey has {len(want)} questions": len(qs) == len(want),
                f"questions named {', '.join(want)}": sorted(filter(None, names)) == sorted(want),
                "survey is a graded survey": q.get("quiz_type") == "graded_survey",
                "survey published": q.get("published") is True,
            }
            for k, v in checks.items():
                print(f"   {'PASS' if v else 'FAIL'}  {k}")
                bad += (not v)
        print(f"\n{'all checks passed' if not bad else f'{bad} check(s) FAILED'}")
        return 1 if bad else 0

    for key, r in cfg.rounds.items():
        adj_name = f"{r.arc} Peer Review Aggregate Grade Adjustment ({r.phase})"
        quiz_name = f"Peer Evaluation: {r.arc} ({r.phase})"
        covered = r.covered_points
        print(f"\n=== {r.arc} / {r.phase} — covers {covered} pts across "
              f"{len(r['covers'])} deliverable(s) ===")
        print(f"  assignment : {adj_name}  [0 pts, group {r.assignment_group_id}, manual post]")
        print(f"  quiz       : {quiz_name}  [{PROV["completion_points"]} pts, "
              f"group {PROV["participation_group_id"]}, 6 questions]")
        print(f"  module     : {r['module']}")
        if a.action == "plan":
            e = round(covered * 0.85, 2)
            print(f"  at a team score of 85% ({e:g}/{covered:g}), a factor of "
                  f"{cfg.scoring.get("floor", 0.60):.2f} would post {round(e*cfg.scoring.get("floor", 0.60)-e, 2):+.2f} "
                  f"and {cfg.scoring.get("ceiling", 1.10):.2f} would post {round(e*cfg.scoring.get("ceiling", 1.10)-e, 2):+.2f}")
            if False or PROV["participation_group_id"] == 0 \
               or r.assignment_group_id == 0:
                print("  !! placeholder ids (000000) still in the config -- fill these in first")
            continue

        if adj_name in existing_a:
            adj = existing_a[adj_name]; print(f"  -> assignment exists ({adj['id']}), skipped")
        else:
            adj = c.request("POST", f"courses/{CID}/assignments", data={
                "assignment[name]": adj_name, "assignment[description]": adj_text(r, cfg),
                "assignment[points_possible]": 0,
                "assignment[assignment_group_id]": r.assignment_group_id,
                "assignment[submission_types][]": "none",
                "assignment[due_at]": r.adjustment_due,
                "assignment[published]": "true"}).json()
            print(f"  -> created assignment {adj['id']}; manual post "
                  f"{'set' if graphql_manual_post(adj['id']) else 'FAILED - set it in the UI'}")

        if quiz_name in existing_q:
            q = existing_q[quiz_name]; print(f"  -> quiz exists ({q['id']}), skipped")
        else:
            q = c.request("POST", f"courses/{CID}/quizzes", data={
                "quiz[title]": quiz_name,
                "quiz[description]": f"<p>Peer evaluation for <strong>{r.arc}</strong> "
                                     f"({r.phase.lower()}). Feeds <em>{adj_name}</em>.</p>",
                "quiz[quiz_type]": "graded_survey",
                "quiz[assignment_group_id]": PROV["participation_group_id"],
                "quiz[due_at]": r.quiz_due, "quiz[allowed_attempts]": 2,
                "quiz[scoring_policy]": "keep_latest", "quiz[published]": "false",
                "quiz[anonymous_submissions]": "false",
                "quiz[show_correct_answers]": "true"}).json()
            built = survey.build(cfg.survey_cfg())
            per = round(PROV["completion_points"] / len(built), 4)
            for payload in built:
                payload = {**payload, "points_possible": per}
                c.request("POST", f"courses/{CID}/quizzes/{q['id']}/questions",
                          json={"question": payload})
            # publish twice to force the cached points_possible to recompute, then pin it
            c.request("PUT", f"courses/{CID}/quizzes/{q['id']}", data={"quiz[published]": "true"})
            c.request("PUT", f"courses/{CID}/quizzes/{q['id']}",
                      data={"quiz[points_possible]": PROV["completion_points"]})
            print(f"  -> created quiz {q['id']} with {len(built)} questions")

        mid = mods.get(r.module)
        if mid:
            titles = {i.get("title") for i in
                      c.get(f"courses/{CID}/modules/{mid}", **{"include[]": "items"}).get("items") or []}
            for title, ctype, cid_ in ((quiz_name, "Quiz", q["id"]),
                                       (adj_name, "Assignment", adj["id"])):
                if title in titles:
                    continue
                c.request("POST", f"courses/{CID}/modules/{mid}/items", data={
                    "module_item[title]": title, "module_item[type]": ctype,
                    "module_item[content_id]": cid_,
                    "module_item[completion_requirement][type]":
                        "must_submit" if ctype == "Quiz" else "must_view"})
            print(f"  -> placed in module '{r['module']}'")
        else:
            print(f"  !! module '{r['module']}' not found — place both items manually")

        state[f"{r.arc}::{r.phase}"] = {
            "adjustment_assignment_id": adj["id"], "quiz_id": q["id"],
            "arc": r.arc, "phase": r.phase,
            "group_category_id": r.get("group_category_id"),
            "covers": [d["name"] for d in r.covers],
            "covers_ids": [d["assignment_id"] for d in r.covers if d.get("assignment_id")],
            "covered_points": covered}

    if a.action == "apply":
        STATE.write_text(json.dumps(state, indent=2))
        print(f"\nwrote {STATE.name} — peer_report.py reads this to know which quiz feeds which "
              f"adjustment.\nRun `python3 provision.py verify` to confirm every object.")


if __name__ == "__main__":
    try:
        main()
    except ConfigError as e:
        raise SystemExit(f"config: {e}")
