"""Verify the scoring engine against the worked examples in the source papers."""
import unittest
from ags.scoring import validate_ballot, score_team, apply_factor

NORBERT, BOB, SALLY = 1, 2, 3
TEAM = [NORBERT, BOB, SALLY]


def ballots(raw, members=TEAM, **kw):
    return [validate_ballot(r, v, members, justification="x" * 30, **kw)
            for r, v in raw.items()]


class TestD4PGuidelinesExample(unittest.TestCase):
    """The Norbert/Sally/Bob example from 'D4P: Peer Evaluation Guidelines'."""

    RAW = {
        NORBERT: {NORBERT: 98, BOB: 101, SALLY: 101},
        SALLY:   {NORBERT: 80, SALLY: 110, BOB: 110},
        BOB:     {NORBERT: 82, SALLY: 109, BOB: 109},
    }

    def test_all_ballots_legal(self):
        for b in ballots(self.RAW):
            self.assertTrue(b.valid, b.problems)
            self.assertEqual(sum(b.ratings.values()), 300)

    def test_means_and_factors(self):
        res, _ = score_team(TEAM, ballots(self.RAW))
        # Norbert: (98+80+82)/3 = 86.67 ; Sally & Bob: (101+110+109)/3 = 106.67
        self.assertAlmostEqual(res[NORBERT].mean_received, 260 / 3, places=3)
        self.assertAlmostEqual(res[SALLY].mean_received, 320 / 3, places=3)
        self.assertAlmostEqual(res[BOB].mean_received, 320 / 3, places=3)
        # ceiling 1.10 binds on the two high contributors
        self.assertAlmostEqual(res[NORBERT].factor, 0.8667, places=3)
        self.assertAlmostEqual(res[SALLY].factor, 1.0667, places=3)

    def test_means_conserve_the_zero_sum(self):
        res, _ = score_team(TEAM, ballots(self.RAW))
        self.assertAlmostEqual(sum(r.mean_received for r in res.values()), 300, places=6)

    def test_detects_the_papers_signature_dysfunction_profile(self):
        """S3.4: contributors rate the slacker low; the slacker rates everyone ~100."""
        res, _ = score_team(TEAM, ballots(self.RAW))
        self.assertTrue(any("self_over_peer" in f for f in res[NORBERT].flags),
                        f"expected Norbert flagged, got {res[NORBERT].flags}")
        self.assertEqual(res[SALLY].flags, [])
        self.assertEqual(res[BOB].flags, [])
        # self=98 vs peers=(80+82)/2=81 -> gap 17 >= 15
        self.assertAlmostEqual(res[NORBERT].peer_mean_excl_self, 81.0)


class TestPaperSection34Example(unittest.TestCase):
    """S3.4: 'if a deliverable is awarded a score of 85/100 by the instructor...'"""

    def test_published_individual_scores(self):
        # "Student A ... average rating of 108 ... would receive 91.8"
        self.assertEqual(apply_factor(85, 100, 1.08), 91.80)
        # "while the other two receive scores of 81.6" (average rating 96)
        self.assertEqual(apply_factor(85, 100, 0.96), 81.60)

    def test_balanced_team_is_a_noop(self):
        self.assertEqual(apply_factor(85, 100, 1.00), 85.00)


class TestValidation(unittest.TestCase):
    def test_rejects_wrong_total_by_rescaling(self):
        b = validate_ballot(SALLY, {NORBERT: 90, BOB: 90, SALLY: 90}, TEAM,
                            justification="x" * 30)
        self.assertTrue(b.valid)
        self.assertEqual(sum(b.ratings.values()), 300)
        self.assertEqual(b.normalized_from, {NORBERT: 90, BOB: 90, SALLY: 90})
        self.assertIn("rescaled", b.problems[0])

    def test_rescale_preserves_relative_ranking(self):
        # within the rescale threshold: 285 is 5% off 300, so it is repaired
        b = validate_ballot(SALLY, {NORBERT: 85, BOB: 100, SALLY: 100}, TEAM,
                            justification="x" * 30)
        self.assertTrue(b.valid, b.problems)
        self.assertEqual(sum(b.ratings.values()), 300)
        self.assertLess(b.ratings[NORBERT], b.ratings[BOB])

    def test_far_off_total_is_held_rather_than_rescaled(self):
        # 250 is 16.7% off 300 -- previously silently rescaled, which manufactured
        # extreme factors from a ballot the student never intended
        b = validate_ballot(SALLY, {NORBERT: 50, BOB: 100, SALLY: 100}, TEAM,
                            justification="x" * 30)
        self.assertFalse(b.valid)
        self.assertIn("HOLD FOR INSTRUCTOR REVIEW", " ".join(b.problems))

    def test_incomplete_ballot_is_invalid_not_invented(self):
        b = validate_ballot(SALLY, {NORBERT: 150, SALLY: 150}, TEAM)
        self.assertFalse(b.valid)
        self.assertIn("did not rate 1 team member(s)", b.problems)

    def test_missing_justification_for_extreme_rating(self):
        b = validate_ballot(SALLY, {NORBERT: 40, BOB: 130, SALLY: 130}, TEAM,
                            justification="")
        self.assertIn("missing required justification", b.problems)

    def test_justification_required_for_any_nonequal_split_when_configured(self):
        b = validate_ballot(SALLY, {NORBERT: 95, BOB: 100, SALLY: 105}, TEAM,
                            justification="",
                            require_justification_for_any_nonequal_split=True)
        self.assertIn("missing required justification", b.problems)

    def test_out_of_range_rating_rejected(self):
        b = validate_ballot(SALLY, {NORBERT: -10, BOB: 155, SALLY: 155}, TEAM)
        self.assertFalse(b.valid)


class TestEdgeCases(unittest.TestCase):
    def test_no_submissions_defaults_everyone_to_neutral(self):
        res, flags = score_team(TEAM, [])
        self.assertTrue(all(r.factor == 1.0 for r in res.values()))
        self.assertIn("no_valid_ballots: all factors defaulted to 1.00", flags)

    def test_non_submitter_still_receives_ratings(self):
        """A student who skips the eval must not erase their teammates' data."""
        raw = {SALLY: {NORBERT: 80, SALLY: 110, BOB: 110},
               BOB:   {NORBERT: 82, SALLY: 109, BOB: 109}}
        res, _ = score_team(TEAM, ballots(raw))
        self.assertAlmostEqual(res[NORBERT].mean_received, 81.0)
        self.assertEqual(res[NORBERT].n_raters, 2)
        self.assertIn("did_not_submit_evaluation", res[NORBERT].flags)
        self.assertNotIn("did_not_submit_evaluation", res[SALLY].flags)

    def test_practice_round_forces_neutral_factor(self):
        raw = {SALLY: {NORBERT: 40, SALLY: 130, BOB: 130}}
        res, _ = score_team(TEAM, ballots(raw), practice=True)
        self.assertTrue(all(r.factor == 1.0 for r in res.values()))
        # ...but the diagnostic mean is still recorded for the report
        self.assertAlmostEqual(res[NORBERT].mean_received, 40.0)

    def test_clamp_floor_binds(self):
        raw = {SALLY: {NORBERT: 0, SALLY: 150, BOB: 150},
               BOB:   {NORBERT: 0, SALLY: 150, BOB: 150},
               NORBERT: {NORBERT: 0, SALLY: 150, BOB: 150}}
        res, _ = score_team(TEAM, ballots(raw))
        self.assertEqual(res[NORBERT].mean_received, 0.0)
        self.assertEqual(res[NORBERT].factor, 0.60)

    def test_pair_is_flagged_as_non_anonymous(self):
        pair = [NORBERT, BOB]
        raw = {NORBERT: {NORBERT: 100, BOB: 100}, BOB: {NORBERT: 100, BOB: 100}}
        _, flags = score_team(pair, ballots(raw, members=pair))
        self.assertTrue(any("NOT anonymous" in f for f in flags))

    def test_pair_ratings_are_trivially_derivable(self):
        """Demonstrates why min_size=3: partner's rating is recoverable exactly."""
        pair = [NORBERT, BOB]
        raw = {NORBERT: {NORBERT: 120, BOB: 80}, BOB: {NORBERT: 90, BOB: 110}}
        res, _ = score_team(pair, ballots(raw, members=pair))
        norbert = res[NORBERT]
        recovered = 2 * norbert.mean_received - norbert.self_rating
        self.assertEqual(recovered, 90)   # exactly what Bob privately said

    def test_flat_ballot_against_disagreeing_team_is_flagged(self):
        """S3.4 profile at N=3: the gap alone is too small, the flat ballot is the tell."""
        raw = {
            101: {101: 105, 102: 105, 103: 90},
            102: {101: 108, 102: 107, 103: 85},
            103: {101: 100, 102: 100, 103: 100},   # non-performer, flat ballot
        }
        team = [101, 102, 103]
        res, _ = score_team(team, ballots(raw, members=team))
        self.assertTrue(any("flat_ballot_vs_team" in f for f in res[103].flags),
                        f"expected 103 flagged, got {res[103].flags}")
        self.assertEqual(res[101].flags, [])
        self.assertEqual(res[102].flags, [])

    def test_flat_ballot_not_flagged_when_whole_team_agrees(self):
        """A genuinely balanced team must not trip the detector."""
        team = [101, 102, 103]
        raw = {r: {101: 100, 102: 100, 103: 100} for r in team}
        res, _ = score_team(team, ballots(raw, members=team))
        for m in team:
            self.assertFalse(any("flat_ballot_vs_team" in f for f in res[m].flags))

    def test_all_even_split_flagged_for_collusion_review(self):
        raw = {r: {NORBERT: 100, BOB: 100, SALLY: 100} for r in TEAM}
        _, flags = score_team(TEAM, ballots(raw))
        self.assertTrue(any("all_ratings_exactly_even" in f for f in flags))


class TestGradeApplication(unittest.TestCase):
    def test_worked_example_13pt_deliverable(self):
        """13-pt deliverable, team scores 11."""
        self.assertEqual(apply_factor(11, 13, 1.08), 11.88)
        self.assertEqual(apply_factor(11, 13, 0.88), 9.68)

    def test_cap_prevents_over_points_possible(self):
        self.assertEqual(apply_factor(13, 13, 1.10, cap_at_points_possible=True), 13.0)
        self.assertEqual(apply_factor(13, 13, 1.10, cap_at_points_possible=False), 14.3)

    def test_ungraded_team_deliverable_yields_no_individual_grade(self):
        self.assertIsNone(apply_factor(None, 13, 1.08))


class TestSafetyRails(unittest.TestCase):
    """Regression tests for the rescale/quorum defects found in adversarial review."""

    def test_wildly_wrong_total_is_held_not_rescaled(self):
        """{100,0,0} on a 3-person team must NOT become {300,0,0}."""
        b = validate_ballot(NORBERT, {NORBERT: 100, BOB: 0, SALLY: 0}, TEAM,
                            justification="x" * 30)
        self.assertFalse(b.valid)
        self.assertIn("HOLD FOR INSTRUCTOR REVIEW", " ".join(b.problems))
        self.assertNotIn(300, b.ratings.values())

    def test_small_slip_still_rescales(self):
        b = validate_ballot(NORBERT, {NORBERT: 100, BOB: 100, SALLY: 95}, TEAM,
                            justification="x" * 30)
        self.assertTrue(b.valid)
        self.assertEqual(sum(b.ratings.values()), 300)

    def test_rescale_never_leaves_a_rating_out_of_range(self):
        # 8% off, so it rescales; check nothing lands outside 0-200
        b = validate_ballot(NORBERT, {NORBERT: 180, BOB: 80, SALLY: 16}, TEAM,
                            justification="x" * 30)
        if b.valid:
            for v in b.ratings.values():
                self.assertGreaterEqual(v, 0)
                self.assertLessEqual(v, 200)

    PAIR_RAW = {NORBERT: {NORBERT: 130, BOB: 70}, BOB: {NORBERT: 120, BOB: 80}}

    def test_team_of_two_default_clamps_rather_than_neutralizing(self):
        """Teams of 2 are expected in this course, so accountability is kept but narrowed."""
        pair = [NORBERT, BOB]
        res, _ = score_team(pair, ballots(self.PAIR_RAW, members=pair))
        self.assertAlmostEqual(res[BOB].factor, 0.80, places=2)   # raw 0.75, floored at 0.80
        self.assertAlmostEqual(res[NORBERT].factor, 1.10, places=2)
        for m in pair:
            self.assertTrue(any("team_of_2" in f for f in res[m].flags))

    def test_team_of_two_neutralize_policy_still_available(self):
        pair = [NORBERT, BOB]
        res, _ = score_team(pair, ballots(self.PAIR_RAW, members=pair),
                            pair_policy="neutralize")
        for m in pair:
            self.assertEqual(res[m].factor, 1.0)

    def test_team_of_two_full_policy_uses_the_normal_clamp(self):
        pair = [NORBERT, BOB]
        res, _ = score_team(pair, ballots(self.PAIR_RAW, members=pair), pair_policy="full")
        self.assertAlmostEqual(res[BOB].factor, 0.75, places=2)

    def test_unanimous_low_is_flagged_for_intervention(self):
        raw = {NORBERT: {NORBERT: 60, BOB: 120, SALLY: 120},
               BOB:     {NORBERT: 55, BOB: 125, SALLY: 120},
               SALLY:   {NORBERT: 50, BOB: 125, SALLY: 125}}
        res, _ = score_team(TEAM, ballots(raw))
        self.assertTrue(any("UNANIMOUS_LOW" in f for f in res[NORBERT].flags),
                        res[NORBERT].flags)
        self.assertFalse(any("UNANIMOUS_LOW" in f for f in res[BOB].flags))
        self.assertAlmostEqual(res[NORBERT].factor, 0.60, places=2)   # floor holds

    def test_one_low_rating_among_several_is_not_unanimous(self):
        raw = {NORBERT: {NORBERT: 100, BOB: 100, SALLY: 100},
               BOB:     {NORBERT: 60, BOB: 120, SALLY: 120},
               SALLY:   {NORBERT: 100, BOB: 100, SALLY: 100}}
        res, _ = score_team(TEAM, ballots(raw))
        self.assertFalse(any("UNANIMOUS_LOW" in f for f in res[NORBERT].flags))

    def test_pair_flag_always_warns_about_anonymity(self):
        pair = [NORBERT, BOB]
        for pol in ("clamp", "neutralize", "full"):
            res, _ = score_team(pair, ballots(self.PAIR_RAW, members=pair), pair_policy=pol)
            self.assertTrue(any("NOT anonymous" in f for f in res[BOB].flags), pol)

    def test_single_ballot_cannot_swing_a_full_factor(self):
        raw = {NORBERT: {NORBERT: 140, BOB: 80, SALLY: 80}}
        res, _ = score_team(TEAM, ballots(raw))
        self.assertAlmostEqual(res[NORBERT].factor, 1.10, places=2)
        self.assertAlmostEqual(res[BOB].factor, 0.90, places=2)
        for m in TEAM:
            self.assertTrue(any("below_quorum" in f for f in res[m].flags))

    def test_quorum_met_allows_the_full_range(self):
        raw = {NORBERT: {NORBERT: 60, BOB: 120, SALLY: 120},
               BOB:     {NORBERT: 60, BOB: 120, SALLY: 120},
               SALLY:   {NORBERT: 60, BOB: 120, SALLY: 120}}
        res, _ = score_team(TEAM, ballots(raw))
        self.assertAlmostEqual(res[NORBERT].factor, 0.60, places=2)
        self.assertFalse(any("below_quorum" in f for f in res[NORBERT].flags))


class TestPaginateUnwrap(unittest.TestCase):
    """Canvas wraps a few collections in a single-key envelope; paginate must
    unwrap them or callers silently see one unusable item instead of N."""

    def setUp(self):
        from ags.canvas import Canvas
        self.u = Canvas._unwrap

    def test_bare_list_passes_through(self):
        self.assertEqual(self.u([{"id": 1}, {"id": 2}]), [{"id": 1}, {"id": 2}])

    def test_empty_list_is_a_collection_not_a_single_object(self):
        self.assertEqual(self.u([]), [])

    def test_quiz_submissions_envelope_is_unwrapped(self):
        body = {"quiz_submissions": [{"user_id": 7}, {"user_id": 8}]}
        self.assertEqual(self.u(body), [{"user_id": 7}, {"user_id": 8}])

    def test_quiz_submission_questions_envelope_is_unwrapped(self):
        body = {"quiz_submission_questions": [{"id": 1}]}
        self.assertEqual(self.u(body), [{"id": 1}])

    def test_single_object_is_not_treated_as_a_page(self):
        self.assertIsNone(self.u({"id": 12345, "name": "Example Course"}))

    def test_single_key_object_whose_value_is_not_a_list(self):
        self.assertIsNone(self.u({"name": "Example Course"}))

    def test_multi_key_object_with_a_list_is_not_unwrapped(self):
        # A real object that happens to carry a list field.
        self.assertIsNone(self.u({"id": 3, "tags": ["a", "b"]}))


class TestUnwrapSideload(unittest.TestCase):
    def setUp(self):
        from ags.canvas import Canvas
        self.u = Canvas._unwrap

    def test_meta_sideload_is_ignored(self):
        body = {"quiz_submissions": [{"user_id": 1}], "meta": {"primaryCollection": "x"}}
        self.assertEqual(self.u(body), [{"user_id": 1}])

    def test_two_real_collections_is_ambiguous_so_not_unwrapped(self):
        self.assertIsNone(self.u({"a": [1], "b": [2]}))


class TestHtmlToText(unittest.TestCase):
    def setUp(self):
        from ags.peerreview import html_to_text
        self.f = html_to_text

    def test_br_becomes_newline(self):
        self.assertEqual(self.f("<p>a<br>b</p>"), "a\nb")

    def test_entities_are_unescaped(self):
        self.assertEqual(self.f("<p>Jo &amp; Sam &lt;3</p>"), "Jo & Sam <3")

    def test_paragraphs_separate_sections(self):
        got = self.f("<p>POINTS<br>a@example.edu = 100</p><p>STRENGTHS<br>a@example.edu: x</p>")
        self.assertEqual(got, "POINTS\na@example.edu = 100\n\nSTRENGTHS\na@example.edu: x")

    def test_real_ballot_parses_after_conversion(self):
        from ags.peerreview import parse_block
        raw = ("<p>POINTS<br>abc12@example.edu = 90<br>cpo59@example.edu = 110"
               "<br>dmr7@example.edu = 100</p>")
        known = ["abc12@example.edu", "cpo59@example.edu", "dmr7@example.edu"]
        ratings, _str, _imp, notes = parse_block(self.f(raw), known)
        self.assertEqual(ratings["cpo59@example.edu"], 110)
        self.assertEqual(sum(ratings.values()), 300)
        self.assertNotIn("no response supplied", notes)

    def test_nbsp_and_empty(self):
        self.assertEqual(self.f("<p>a&nbsp;b</p>"), "a b")
        self.assertEqual(self.f(None), "")
        self.assertEqual(self.f(""), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
