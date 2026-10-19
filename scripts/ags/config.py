"""Load one course's configuration from a single YAML file.

Why this file exists
--------------------
Course wiring used to live in four places that disagreed with each other: a
`.env`, a `config.example.yaml` that no code actually read, a
`provision.example.yaml`, and a hardcoded ROUNDS table inside peer_report.py.
Adopting the toolkit meant finding all four. Now there is one file.

The split is deliberate:

    course.yml      every non-secret thing about YOUR course -- ids, rounds,
                    thresholds. Gitignored, because the ids are yours.
    the token       never in a file. Read from the macOS keychain, or from
                    CANVAS_TOKEN in the environment. See ags.canvas.

So a config file is safe to hand to a colleague as a starting point, and a
leaked config file is not a leaked credential.
"""
import os
import pathlib

try:
    import yaml
except ImportError:                      # pragma: no cover
    yaml = None

CONFIG_NAME = "course.yml"
ENV_VAR = "PEER_EVAL_CONFIG"


class ConfigError(RuntimeError):
    pass


class Round:
    """One peer-evaluation checkpoint: a survey, an adjustment, and what it scales."""

    def __init__(self, key, d):
        self.key = key
        self.arc = _need(d, "arc", f"rounds.{key}")
        self.phase = _need(d, "phase", f"rounds.{key}")
        self.group_category_id = _int(d, "group_category_id", f"rounds.{key}")
        # Blank until provision.py creates them; peer_report.py checks before use.
        self.survey_quiz_id = _opt_int(d.get("survey_quiz_id"))
        self.adjustment_assignment_id = _opt_int(d.get("adjustment_assignment_id"))
        covers = d.get("covers") or []
        if not covers:
            raise ConfigError(
                f"rounds.{key}.covers is empty.\n"
                "  List the group deliverables this round's factor multiplies. The adjustment\n"
                "  is computed from the team's earned score across exactly these assignments.")
        # Build-time-only fields. peer_report.py never reads these; provision.py
        # needs them to CREATE the quiz and adjustment, and they are harmless once
        # the objects exist. Optional, so a config written by hand stays short.
        self.module = d.get("module")
        self.quiz_due = d.get("quiz_due")
        self.adjustment_due = d.get("adjustment_due")
        self.assignment_group_id = d.get("assignment_group_id")

        self.covers = []
        for i, c in enumerate(covers):
            if not isinstance(c, dict) or "assignment_id" not in c:
                raise ConfigError(
                    f"rounds.{key}.covers[{i}] needs an assignment_id.\n"
                    "  Expected: {name: Part 1, points: 9, assignment_id: 123456}")
            self.covers.append({"name": c.get("name") or f"assignment {c['assignment_id']}",
                                "points": c.get("points"),
                                "assignment_id": int(c["assignment_id"])})

    def require(self, field):
        """Fetch an id that must exist by now, with a message that says what to do."""
        v = getattr(self, field)
        if v is None:
            raise ConfigError(
                f"rounds.{self.key}.{field} is not set yet.\n"
                f"  Create the Canvas objects first:  python3 provision.py apply\n"
                f"  Or fill the id in by hand:        python3 discover.py")
        return v

    @property
    def covered_ids(self):
        return [c["assignment_id"] for c in self.covers]

    @property
    def covered_points(self):
        return sum(c["points"] or 0 for c in self.covers)

    @property
    def title(self):
        return f"{self.arc} -- {self.phase}"


class Config:
    def __init__(self, data, path):
        self.path = path
        canvas = data.get("canvas") or {}
        self.base_url = (canvas.get("base_url")
                         or os.environ.get("CANVAS_BASE_URL", "")).rstrip("/")
        if not self.base_url:
            raise ConfigError(
                f"canvas.base_url is not set in {path}.\n"
                "  Your Canvas host, no trailing slash and no /api/v1\n"
                "  e.g. https://canvas.your-university.edu")
        cid = canvas.get("course_id") or os.environ.get("CANVAS_COURSE_ID")
        if not cid or str(cid).strip() in ("", "0", "000000"):
            raise ConfigError(
                f"canvas.course_id is not set in {path}.\n"
                "  It is the number in your course URL: /courses/<THIS>")
        self.course_id = int(cid)

        self.email = data.get("email") or {}
        self.allocator_url = data.get("allocator_url")
        self.scoring = data.get("scoring") or {}
        self.teams = data.get("teams") or {}
        self.flags = data.get("flags") or {}
        self.grading = data.get("grading") or {}
        # Only provision.py reads this; it is absent from most finished configs.
        self.provisioning = data.get("provisioning") or {}

        rounds = data.get("rounds") or {}
        if not rounds:
            raise ConfigError(f"no rounds defined in {path}. See course.example.yml.")
        self.rounds = {k: Round(k, v) for k, v in rounds.items()}

    # -- the knobs, with the same defaults ags.scoring uses -------------------
    def score_kwargs(self):
        """Keyword arguments for ags.scoring.score_team, drawn from this config."""
        s, t, f = self.scoring, self.teams, self.flags
        return dict(
            floor=s.get("floor", 0.60), ceiling=s.get("ceiling", 1.10),
            include_self_rating=s.get("include_self_rating", True),
            pair_policy=t.get("pair_policy", "clamp"),
            pair_floor=t.get("pair_floor", 0.80), pair_ceiling=t.get("pair_ceiling", 1.10),
            min_raters=t.get("min_raters", 2),
            single_ballot_cap=t.get("single_ballot_cap", 0.10),
            low_mean_received=f.get("low_mean_received", 85),
            self_minus_peer_gap=f.get("self_minus_peer_gap", 10),
            flat_ballot_spread=f.get("flat_ballot_spread", 8),
            unanimous_low=f.get("unanimous_low", 80),
        )

    def ballot_kwargs(self):
        s = self.scoring
        return dict(justify_below=s.get("justify_below", 80),
                    justify_above=s.get("justify_above", 120),
                    max_rescale_pct=s.get("max_rescale_pct", 10.0))

    def survey_cfg(self):
        """What ags.survey needs to render question bodies."""
        return dict(email_example=self.email.get("example", "abc123@example.edu"),
                    email_domain=self.email.get("domain", "@example.edu"),
                    allocator_url=self.allocator_url,
                    justify_below=self.scoring.get("justify_below", 80),
                    justify_above=self.scoring.get("justify_above", 120))


def _need(d, key, where):
    v = d.get(key)
    if v in (None, ""):
        raise ConfigError(f"{where}.{key} is required.")
    return v


def _opt_int(v):
    """An id that may legitimately be unset (provision.py has not created it yet)."""
    if v in (None, "", 0) or str(v).strip() in ("000000", "0"):
        return None
    return int(v)


def _int(d, key, where):
    v = d.get(key)
    if v in (None, "", 0) or str(v).strip() in ("000000", "0"):
        raise ConfigError(
            f"{where}.{key} is not filled in.\n"
            f"  Run `python3 discover.py` to list the ids in your course.")
    return int(v)


def find(path=None):
    """Locate the config file: explicit path, $PEER_EVAL_CONFIG, then alongside the scripts."""
    if path:
        p = pathlib.Path(path).expanduser()
        if not p.is_file():
            raise ConfigError(f"no config file at {p}")
        return p
    env = os.environ.get(ENV_VAR)
    if env:
        p = pathlib.Path(env).expanduser()
        if not p.is_file():
            raise ConfigError(f"{ENV_VAR} points at {p}, which does not exist")
        return p
    here = pathlib.Path(__file__).resolve().parent.parent
    for cand in (pathlib.Path.cwd() / CONFIG_NAME, here / CONFIG_NAME):
        if cand.is_file():
            return cand
    raise ConfigError(
        f"no {CONFIG_NAME} found.\n"
        f"  Copy the template and fill it in:\n"
        f"      cp {here / 'course.example.yml'} {here / CONFIG_NAME}\n"
        f"  Then run `python3 discover.py` to list your course's Canvas ids.")


def load(path=None):
    if yaml is None:
        raise ConfigError("PyYAML is required to read the config.\n"
                          "    pip3 install -r requirements.txt")
    p = find(path)
    try:
        data = yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"{p} is not valid YAML:\n  {e}")
    return Config(data, p)
