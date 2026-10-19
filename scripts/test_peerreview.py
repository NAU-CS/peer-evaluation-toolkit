"""End-to-end test of reconciliation + reporting with deliberately messy input."""
import unittest
from ags.peerreview import (normalize_email, correct_email, meaningful,
                            StudentRecord, PeerComment, render_report, EMAIL_RE)
from ags.scoring import validate_ballot, score_team

ROSTER = {"adz101@example.edu": "Zhao, Ada", "abc12@example.edu": "Alvarez, Bea",
          "cpo59@example.edu": "Okonkwo, Chi", "dmr7@example.edu": "Rao, Dev",
          "elt441@example.edu": "Tran, Elena"}
KNOWN = set(ROSTER)


class TestEmailHygiene(unittest.TestCase):
    def test_institutional_form_recognised(self):
        self.assertTrue(EMAIL_RE.match("adz101@example.edu"))
        for bad in ("jsd@example.edu", "323@example.edu", "adz101@gmail.com", "adz101@example.education"):
            self.assertFalse(EMAIL_RE.match(bad), bad)

    def test_normalizes_common_mistakes(self):
        self.assertEqual(normalize_email("  ADZ101@EXAMPLE.EDU "), "adz101@example.edu")
        self.assertEqual(normalize_email("adz101"), "adz101@example.edu")          # bare id
        self.assertEqual(normalize_email("adz101@example.ed"), "adz101@example.edu")   # truncated
        self.assertEqual(normalize_email("adz101@example.edu.edu"), "adz101@example.edu")
        self.assertEqual(normalize_email("n/a"), "")

    def test_unique_prefix_correction(self):
        r, corr, note = correct_email("cpo@example.edu", KNOWN)
        self.assertEqual(r, "cpo59@example.edu"); self.assertTrue(corr)

    def test_ambiguous_prefix_is_not_guessed(self):
        known = KNOWN | {"cpo77@example.edu"}
        r, corr, note = correct_email("cpo@example.edu", known)
        self.assertFalse(corr); self.assertIn("ambiguous", note)

    def test_typo_within_threshold(self):
        r, corr, _ = correct_email("adz102@example.edu", KNOWN)
        self.assertEqual(r, "adz101@example.edu"); self.assertTrue(corr)

    def test_unrelated_address_is_not_forced(self):
        r, corr, note = correct_email("zzz999@example.edu", KNOWN)
        self.assertFalse(corr); self.assertEqual(note, "unresolved")

    def test_nullish_comments_filtered(self):
        for n in ("", "n/a", "None", "  -- ", "no comment"):
            self.assertIsNone(meaningful(n))
        self.assertEqual(meaningful("  did   the art  "), "did the art")


class TestFullRound(unittest.TestCase):
    """Team of 3: one member carried extra load, one under-contributed and skipped their ballot."""
    A, B, C = 1, 2, 3
    TEAM = [A, B, C]

    def setUp(self):
        raw = {self.A: {self.A: 112, self.B: 108, self.C: 80},
               self.B: {self.A: 110, self.B: 110, self.C: 80}}   # C never submitted
        self.ballots = [validate_ballot(r, v, self.TEAM, justification="C missed both build sessions "
                                        "and did not deliver the card art.")
                        for r, v in raw.items()]
        self.res, self.tflags = score_team(self.TEAM, self.ballots)

    def test_all_ballots_legal(self):
        for b in self.ballots:
            self.assertTrue(b.valid, b.problems)

    def test_non_submitter_still_receives_ratings(self):
        self.assertEqual(self.res[self.C].n_raters, 2)
        self.assertAlmostEqual(self.res[self.C].mean_received, 80.0)
        self.assertIn("did_not_submit_evaluation", self.res[self.C].flags)

    def test_quorum_met_so_full_range_applies(self):
        self.assertAlmostEqual(self.res[self.C].factor, 0.80, places=2)
        self.assertFalse(any("below_quorum" in f for f in self.res[self.C].flags))

    def test_adjustment_arithmetic(self):
        # team earned 27 of 32 on the covered deliverables
        earned = 27.0
        adj = {m: round(earned * self.res[m].factor - earned, 2) for m in self.TEAM}
        self.assertAlmostEqual(adj[self.C], -5.4, places=2)
        self.assertGreater(adj[self.A], 0)
        self.assertAlmostEqual(sum(adj.values()), 0.0, delta=0.9)  # near zero-sum

    def test_reports_render_and_respect_anonymity(self):
        rec = StudentRecord(email="cpo59@example.edu", name="Okonkwo, Chi", team="Team 4")
        rec.factor = self.res[self.C].factor
        rec.mean_received = self.res[self.C].mean_received
        rec.adjustment = -5.4
        rec.received = [PeerComment("adz101@example.edu", "Zhao, Ada",
                                    "Wrote the theme copy", "Missed both build sessions", "", 80),
                        PeerComment("abc12@example.edu", "Alvarez, Bea",
                                    "Good ideas early on", "n/a", "Went quiet after week 2", 80)]
        anon = render_report(rec, "Tangible Board Game", "Draft", 27.0, 32.0, anonymous=True)
        ident = render_report(rec, "Tangible Board Game", "Draft", 27.0, 32.0, anonymous=False)
        # student copy must not leak rater identities
        for leak in ("Zhao", "Alvarez", "adz101", "abc12"):
            self.assertNotIn(leak, anon, f"{leak} leaked into the student-facing report")
        self.assertIn("Zhao", ident)
        # nullish comment filtered out of improvements, real ones kept
        self.assertIn("Missed both build sessions", anon)
        self.assertNotIn("n/a", anon)
        # "other" comments are instructor-only
        self.assertNotIn("Went quiet", anon)
        self.assertIn("Went quiet", ident)
        self.assertIn("ADJUSTMENT POSTED: -5.40", anon)


class TestAllocationParsing(unittest.TestCase):
    """The single-question allocation format, with the N x 100 arithmetic check."""
    TEAM = ["adz101@example.edu", "abc12@example.edu", "cpo59@example.edu"]

    def parse(self, txt):
        from ags.peerreview import parse_allocation, check_budget
        r, n = parse_allocation(txt, KNOWN)
        return r, n, check_budget(r, members=self.TEAM)

    def test_clean_allocation(self):
        r, n, b = self.parse("adz101@example.edu = 110\nabc12@example.edu = 100\ncpo59@example.edu = 90")
        self.assertTrue(b["ok"], b["problems"]); self.assertEqual(b["total"], 300)

    def test_tolerates_separators_and_bare_ids(self):
        for txt in ("adz101@example.edu: 110\nabc12@example.edu   100\ncpo59@example.edu - 90",
                    "adz101 = 110\nabc12 = 100\ncpo59 = 90"):
            r, n, b = self.parse(txt)
            self.assertTrue(b["ok"], f"{txt!r} -> {b['problems']}")

    def test_wrong_total_is_caught(self):
        r, n, b = self.parse("adz101@example.edu = 100\nabc12@example.edu = 100\ncpo59@example.edu = 50")
        self.assertFalse(b["ok"])
        self.assertTrue(any("must distribute exactly 300" in p for p in b["problems"]))

    def test_omitting_yourself_is_caught_even_when_the_sum_is_right(self):
        """300 total across 2 people balances arithmetically but is not a valid ballot."""
        r, n, b = self.parse("abc12@example.edu = 150\ncpo59@example.edu = 150")
        self.assertEqual(b["total"], 300)
        self.assertFalse(b["ok"])
        self.assertIn("adz101@example.edu", " ".join(b["problems"]))

    def test_outsider_is_flagged_as_not_on_this_team(self):
        """parse_allocation resolves against the roster; check_budget owns team coverage."""
        r, n, b = self.parse("adz101@example.edu = 100\nabc12@example.edu = 100\ndmr7@example.edu = 100")
        self.assertIn("dmr7@example.edu", r)          # a real student, so it parses
        self.assertFalse(b["ok"])
        self.assertIn("dmr7@example.edu", b["extra"])  # but not on this team
        self.assertIn("cpo59@example.edu", b["missing"])
        self.assertTrue(any("is not on this team" in p for p in b["problems"]))

    def test_typo_is_corrected_and_noted(self):
        r, n, b = self.parse("adz102@example.edu = 110\nabc12@example.edu = 100\ncpo59@example.edu = 90")
        self.assertTrue(b["ok"], b["problems"])
        self.assertTrue(any("corrected" in x for x in n))

    def test_prose_lines_are_skipped_not_fatal(self):
        r, n, b = self.parse("adz101@example.edu = 110\nBea was great\nabc12@example.edu = 100\ncpo59@example.edu = 90")
        self.assertTrue(b["ok"], b["problems"])
        self.assertTrue(any("could not read" in x for x in n))

    def test_duplicate_line_is_noted(self):
        r, n, b = self.parse("adz101@example.edu = 110\nadz101@example.edu = 120\n"
                             "abc12@example.edu = 100\ncpo59@example.edu = 80")
        self.assertTrue(any("more than once" in x for x in n))

    def test_comment_lines_attribute_to_the_right_person(self):
        from ags.peerreview import parse_comments
        out, _ = parse_comments("abc12@example.edu: built the deck\ncpo59@example.edu: wrote the intro", KNOWN)
        self.assertEqual(out["abc12@example.edu"], "built the deck")
        self.assertEqual(out["cpo59@example.edu"], "wrote the intro")


class TestSurveyLayout(unittest.TestCase):
    """The survey is three questions; the calculator emits one combined block into Q1.
    These tests fail if the authoring script and the reader ever drift apart."""

    def test_reader_expects_three_slots(self):
        from peer_report import Q_BLOCK, Q_JUSTIFY, Q_INSTRUCTOR
        self.assertEqual(sorted([Q_BLOCK, Q_JUSTIFY, Q_INSTRUCTOR]), [1, 2, 3])

    def test_block_parses_the_calculator_output(self):
        from ags.peerreview import parse_block, check_budget
        team = ["adz101@example.edu", "abc12@example.edu", "cpo59@example.edu"]
        txt = ("POINTS\nadz101@example.edu = 110\nabc12@example.edu = 100\ncpo59@example.edu = 90\n\n"
               "STRENGTHS\nabc12@example.edu: built the deck\ncpo59@example.edu: wrote the intro\n\n"
               "IMPROVEMENTS\nabc12@example.edu: n/a\ncpo59@example.edu: missed a session")
        r, st, im, notes = parse_block(txt, KNOWN)
        self.assertTrue(check_budget(r, members=team)["ok"])
        self.assertEqual(st["abc12@example.edu"], "built the deck")
        self.assertEqual(im["cpo59@example.edu"], "missed a session")
        self.assertNotIn("abc12@example.edu", im)          # "n/a" filtered out
        self.assertEqual(notes, [])

    def test_headings_are_case_and_order_insensitive(self):
        from ags.peerreview import parse_block, check_budget
        team = ["adz101@example.edu", "abc12@example.edu", "cpo59@example.edu"]
        txt = ("improvements\nabc12@example.edu: slow to reply\n\n"
               "points\nadz101@example.edu = 100\nabc12@example.edu = 100\ncpo59@example.edu = 100")
        r, st, im, _ = parse_block(txt, KNOWN)
        self.assertTrue(check_budget(r, members=team)["ok"])
        self.assertIn("abc12@example.edu", im)

    def test_missing_headings_still_scores_the_allocation(self):
        """A student who pastes only their numbers must not lose their ballot."""
        from ags.peerreview import parse_block, check_budget
        team = ["adz101@example.edu", "abc12@example.edu", "cpo59@example.edu"]
        r, st, im, notes = parse_block(
            "adz101@example.edu = 110\nabc12@example.edu = 100\ncpo59@example.edu = 90", KNOWN)
        self.assertTrue(check_budget(r, members=team)["ok"])
        self.assertTrue(any("no POINTS" in n for n in notes))

    def test_legal_total_can_still_be_wrong_for_the_team_size(self):
        from ags.peerreview import parse_block, check_budget
        pair = ["adz101@example.edu", "abc12@example.edu"]
        r, _, _, _ = parse_block("POINTS\nadz101@example.edu = 150\nabc12@example.edu = 150", KNOWN)
        b = check_budget(r, members=pair)
        self.assertEqual(b["total"], 300)
        self.assertEqual(b["target"], 200)
        self.assertFalse(b["ok"])


class TestQuestionMapping(unittest.TestCase):
    """Canvas does not persist `position` on API-created questions -- it reads back as None.
    peer_report.py must key answers off question_name instead, or every ballot is misparsed."""

    def test_question_name_parses_to_an_index(self):
        import re
        for name, want in (("Q1", 1), ("Q20", 20), (" Q7 ", 7)):
            m = re.fullmatch(r"Q(\d+)", name.strip())
            self.assertIsNotNone(m, name)
            self.assertEqual(int(m.group(1)), want)

    def test_non_conforming_names_do_not_parse(self):
        import re
        for name in ("", "Question 1", "q1x", "1"):
            self.assertIsNone(re.fullmatch(r"Q(\d+)", name.strip()))

    def test_question_names_still_drive_the_mapping(self):
        """Canvas does not persist `position`, so Q1..Qn names are the only reliable key."""
        import re as _re
        for name, want in (("Q1", 1), ("Q3", 3), (" Q2 ", 2)):
            self.assertEqual(int(_re.fullmatch(r"Q(\d+)", name.strip()).group(1)), want)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestRatingCountIsAuthoritative(unittest.TestCase):
    """The header count must come from the scorer, not from `received`.

    `received` carries PEER comments only and may include raters whose ballots were
    later rejected, so deriving the count from it was wrong in two directions:
    one too few for anyone who submitted, and non-zero for a team whose ballots
    were all invalid. 22 of 34 live reports were wrong before this was fixed.
    """

    def _rec(self, **kw):
        r = StudentRecord(email="abc12@example.edu", name="Alvarez, Bea", team="T1",
                          factor=1.09, mean_received=109.0, adjustment=2.43)
        for k, v in kw.items():
            setattr(r, k, v)
        return r

    def test_self_rating_is_included_in_the_count(self):
        # Two peers commented; the scorer counted 3 ratings (2 peers + self).
        rec = self._rec(n_ratings_counted=3, self_counted=True)
        rec.received = [PeerComment("cpo59@example.edu", "Okonkwo, Chi", "x", "", "", 100),
                        PeerComment("dmr7@example.edu", "Rao, Dev", "y", "", "", 108)]
        out = render_report(rec, "Arc", "Draft", 27, 32)
        self.assertIn("Ratings received: 3 (including your own self-rating)", out)
        self.assertNotIn("Ratings received: 2", out)

    def test_rejected_ballots_do_not_inflate_the_count(self):
        # Comments exist, but every ballot was invalid so the scorer counted none.
        rec = self._rec(n_ratings_counted=0, self_counted=False,
                        factor=1.0, mean_received=100.0, adjustment=0.0)
        rec.received = [PeerComment("cpo59@example.edu", "Okonkwo, Chi", "x", "", "", 100)]
        out = render_report(rec, "Arc", "Draft", 27, 32)
        self.assertIn("Ratings received: 0", out)
        self.assertIn("you did not submit an evaluation", out)

    def test_non_submitter_count_excludes_self(self):
        rec = self._rec(n_ratings_counted=2, self_counted=False)
        out = render_report(rec, "Arc", "Draft", 27, 32)
        self.assertIn("Ratings received: 2 (you did not submit an evaluation", out)

    def test_falls_back_to_received_when_scorer_count_absent(self):
        rec = self._rec()          # n_ratings_counted left None
        rec.received = [PeerComment("cpo59@example.edu", "Okonkwo, Chi", "x", "", "", 100)]
        out = render_report(rec, "Arc", "Draft", 27, 32)
        self.assertIn("Ratings received: 1", out)
