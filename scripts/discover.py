#!/usr/bin/env python3
"""Print the Canvas ids you need for course.yml.

    python3 discover.py                 # everything
    python3 discover.py --quizzes       # just one section

Finding these by hand means clicking through Canvas and reading URLs. This asks
the API instead. Nothing is written; it is safe to run any time.
"""
import argparse
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ags.canvas import Canvas, CanvasError          # noqa: E402
from ags.config import load, ConfigError            # noqa: E402

W = 78


def head(t):
    print(f"\n{t}\n{'-' * min(len(t), W)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    for s in ("groups", "quizzes", "assignments"):
        ap.add_argument(f"--{s}", action="store_true")
    a = ap.parse_args()
    only = {s for s in ("groups", "quizzes", "assignments") if getattr(a, s)}

    try:
        cfg = load(a.config)
    except ConfigError as e:
        print(f"config: {e}", file=sys.stderr)
        return 2
    c = Canvas(base_url=cfg.base_url)
    cid = cfg.course_id

    course = c.get(f"courses/{cid}")
    print(f"{course.get('name')}  (course_id: {cid})")

    if not only or "groups" in only:
        head("group_category_id  -- the group SET a round evaluates")
        for g in c.paginate(f"courses/{cid}/group_categories"):
            groups = list(c.paginate(f"group_categories/{g['id']}/groups"))
            # Self-signup sets are usually created with many empty slots, so the
            # count that matters is how many actually have members in them.
            peopled = sum(1 for x in groups if (x.get("members_count") or 0) > 0)
            print(f"  {g['id']:>8}  {g['name']}   "
                  f"({peopled} teams with members, {len(groups)} groups)")

    if not only or "quizzes" in only:
        head("survey_quiz_id  -- the peer-evaluation survey for a round")
        for q in c.paginate(f"courses/{cid}/quizzes"):
            kind = q.get("quiz_type") or ""
            mark = "  <- graded survey" if kind == "graded_survey" else ""
            print(f"  {q['id']:>8}  {(q.get('title') or '')[:52]:52}{mark}")

    if not only or "assignments" in only:
        groups = {g["id"]: g["name"] for g in c.paginate(f"courses/{cid}/assignment_groups")}
        by_group = {}
        for asg in c.paginate(f"courses/{cid}/assignments"):
            by_group.setdefault(asg.get("assignment_group_id"), []).append(asg)

        head("adjustment_assignment_id  -- 0-point assignments (candidates)")
        any_zero = False
        for gid, items in by_group.items():
            for asg in items:
                if (asg.get("points_possible") or 0) == 0:
                    any_zero = True
                    print(f"  {asg['id']:>8}  {(asg.get('name') or '')[:48]:48}"
                          f"  [{groups.get(gid, '?')}]")
        if not any_zero:
            print("  none yet -- provision.py creates these, or add them by hand (0 points,")
            print("  same assignment group as the deliverables the round covers).")

        head("covers[].assignment_id  -- your group deliverables, by assignment group")
        for gid, items in by_group.items():
            print(f"\n  [{groups.get(gid, '?')}]")
            for asg in sorted(items, key=lambda x: x.get("due_at") or ""):
                pts = asg.get("points_possible")
                grp = "group" if asg.get("group_category_id") else "     "
                print(f"    {asg['id']:>8}  {str(pts if pts is not None else '-'):>5} pts  "
                      f"{grp}  {(asg.get('name') or '')[:46]}")

    print("\nCopy the ids you need into course.yml.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ConfigError as e:
        raise SystemExit(f"config: {e}")
    except CanvasError as e:
        raise SystemExit(f"Canvas: {e}")
