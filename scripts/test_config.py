"""Config and survey tests.

Deliberately dependency-free: these build Config from a dict rather than going
through load(), so the suite still runs with PyYAML absent, as the README claims.
"""
import unittest

from ags.config import Config, Round, ConfigError
from ags import survey


def base(**over):
    d = {"canvas": {"base_url": "https://canvas.example.edu/", "course_id": 123},
         "rounds": {"r1": {"arc": "Project", "phase": "Draft",
                           "group_category_id": 7, "survey_quiz_id": 8,
                           "adjustment_assignment_id": 9,
                           "covers": [{"name": "P1", "points": 10, "assignment_id": 11}]}}}
    d.update(over)
    return d


class TestSurveyLayout(unittest.TestCase):
    """The builder and the reader share this; drift here caused a silent data bug."""

    def test_three_questions_in_order(self):
        self.assertEqual([q.canvas_name for q in survey.QUESTIONS], ["Q1", "Q2", "Q3"])

    def test_q1_is_the_only_student_facing_question(self):
        aud = {q.canvas_name: q.audience for q in survey.QUESTIONS}
        self.assertEqual(aud["Q1"], survey.STUDENTS)
        self.assertEqual(aud["Q2"], survey.INSTRUCTOR)
        self.assertEqual(aud["Q3"], survey.INSTRUCTOR)

    def test_positions_match_canvas_names(self):
        for q in survey.QUESTIONS:
            self.assertEqual(q.canvas_name, f"Q{q.position}")
        self.assertEqual(survey.POSITION, {"block": 1, "justification": 2, "instructor": 3})

    def test_build_emits_one_payload_per_question(self):
        built = survey.build({"email_example": "abc123@x.edu"})
        self.assertEqual(len(built), len(survey.QUESTIONS))
        self.assertEqual([b["question_name"] for b in built], ["Q1", "Q2", "Q3"])
        for b in built:
            self.assertEqual(b["question_type"], "essay_question")
            self.assertTrue(b["question_text"].strip())

    def test_q1_embeds_the_configured_allocator(self):
        t = survey.question_text("block", {"allocator_url": "https://example.org/alloc/"})
        self.assertIn("https://example.org/alloc/", t)
        self.assertIn('data-allocator-embed="1"', t)

    def test_q2_reflects_the_configured_justification_band(self):
        t = survey.question_text("justification", {"justify_below": 70, "justify_above": 130})
        self.assertIn("70", t)
        self.assertIn("130", t)

    def test_no_account_specific_markup_ships_in_the_template(self):
        # The live course injects DesignPLUS css/js per account; that must not be
        # baked into what an adopter builds.
        for b in survey.build({}):
            self.assertNotIn("instructure-uploads", b["question_text"])
            self.assertNotIn("<script", b["question_text"])


class TestConfig(unittest.TestCase):
    def test_loads_a_minimal_course(self):
        c = Config(base(), "test.yml")
        self.assertEqual(c.course_id, 123)
        self.assertEqual(c.base_url, "https://canvas.example.edu")   # trailing slash stripped
        self.assertEqual(list(c.rounds), ["r1"])

    def test_placeholder_course_id_is_rejected(self):
        d = base(); d["canvas"]["course_id"] = "000000"
        with self.assertRaises(ConfigError) as e:
            Config(d, "test.yml")
        self.assertIn("course_id", str(e.exception))

    def test_missing_base_url_is_rejected(self):
        d = base(); d["canvas"]["base_url"] = ""
        import os
        os.environ.pop("CANVAS_BASE_URL", None)
        with self.assertRaises(ConfigError):
            Config(d, "test.yml")

    def test_no_rounds_is_rejected(self):
        with self.assertRaises(ConfigError):
            Config(base(rounds={}), "test.yml")

    def test_covers_must_not_be_empty(self):
        d = base(); d["rounds"]["r1"]["covers"] = []
        with self.assertRaises(ConfigError) as e:
            Config(d, "test.yml")
        self.assertIn("covers", str(e.exception))

    def test_covers_entry_needs_an_assignment_id(self):
        d = base(); d["rounds"]["r1"]["covers"] = [{"name": "P1", "points": 10}]
        with self.assertRaises(ConfigError):
            Config(d, "test.yml")

    def test_covered_points_and_ids(self):
        d = base()
        d["rounds"]["r1"]["covers"] = [{"name": "a", "points": 9, "assignment_id": 1},
                                       {"name": "b", "points": 13, "assignment_id": 2}]
        r = Config(d, "t").rounds["r1"]
        self.assertEqual(r.covered_points, 22)
        self.assertEqual(r.covered_ids, [1, 2])
        self.assertEqual(r.title, "Project -- Draft")

    def test_unprovisioned_ids_are_allowed_until_used(self):
        d = base()
        d["rounds"]["r1"]["survey_quiz_id"] = "000000"
        r = Config(d, "t").rounds["r1"]
        self.assertIsNone(r.survey_quiz_id)
        with self.assertRaises(ConfigError) as e:
            r.require("survey_quiz_id")
        self.assertIn("provision.py", str(e.exception))

    def test_defaults_when_knobs_absent(self):
        k = Config(base(), "t").score_kwargs()
        self.assertEqual(k["floor"], 0.60)
        self.assertEqual(k["ceiling"], 1.10)
        self.assertEqual(k["pair_policy"], "clamp")
        self.assertTrue(k["include_self_rating"])

    def test_knobs_override_defaults(self):
        c = Config(base(scoring={"floor": 0.5, "justify_below": 70},
                        teams={"pair_policy": "neutralize"}), "t")
        k = c.score_kwargs()
        self.assertEqual(k["floor"], 0.5)
        self.assertEqual(k["pair_policy"], "neutralize")
        self.assertEqual(c.ballot_kwargs()["justify_below"], 70)

    def test_survey_cfg_feeds_the_question_builder(self):
        c = Config(base(email={"example": "zzz9@x.edu"},
                        allocator_url="https://a/"), "t")
        s = c.survey_cfg()
        self.assertEqual(s["email_example"], "zzz9@x.edu")
        self.assertIn("zzz9@x.edu", survey.question_text("block", s))


if __name__ == "__main__":
    unittest.main()
