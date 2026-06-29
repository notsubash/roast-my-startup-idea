from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from judges.schemas import Verdict, VerdictLabel, judgeLabel
import tests  # noqa: F401
from verification import (
    assess_revote_quality,
    fix_fields_missing_judges,
    is_degenerate_fixes,
    is_degenerate_panel,
    score_verdict_mismatches,
    verify_verdict_invariants,
)
from verification.invariants import check_score_change_bounded

SAMPLE_FIX = "Interview ten target buyers and document their top workflow pain before building."
SAMPLE_EVIDENCE = "Three signed LOIs from target buyers would change this verdict."


def _verdict(
    judge: str,
    *,
    verdict: str = "FAIL",
    score: int = 3,
    recommended_fix: str | None = SAMPLE_FIX,
    evidence_to_change_verdict: str | None = SAMPLE_EVIDENCE,
    key_concern: str = "No clear buyer path.",
) -> Verdict:
    return Verdict(
        judge=judgeLabel(judge),
        verdict=VerdictLabel(verdict),
        roast="This idea lacks a credible buyer and clear wedge in a crowded market.",
        score=score,
        key_concern=key_concern,
        recommended_fix=recommended_fix,
        evidence_to_change_verdict=evidence_to_change_verdict,
    )


class VerificationInvariantsTest(unittest.TestCase):
    def test_verify_verdict_invariants_accepts_valid_verdict(self):
        result = verify_verdict_invariants(_verdict("vc"), expected_judge="vc")
        self.assertTrue(result.ok)

    def test_verify_verdict_invariants_rejects_duplicate_fix(self):
        concern = "No credible buyer path."
        result = verify_verdict_invariants(
            _verdict("vc", key_concern=concern, recommended_fix=concern),
            expected_judge="vc",
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.first_failure().code, "recommended_fix_duplicates_key_concern")

    def test_score_verdict_mismatches_works_on_dicts(self):
        mismatches = score_verdict_mismatches(
            [{"judge": "vc", "verdict": "PASS", "score": 2, "key_concern": "x"}]
        )
        self.assertEqual(len(mismatches), 1)
        self.assertIn("vc", mismatches[0])


class VerificationPanelTest(unittest.TestCase):
    def test_is_degenerate_fixes_detects_identical_fixes(self):
        verdicts = [
            _verdict("vc", recommended_fix="Run ten buyer interviews this month."),
            _verdict("engineer", recommended_fix="Run ten buyer interviews this month."),
        ]
        self.assertTrue(is_degenerate_fixes(verdicts))

    def test_is_degenerate_fixes_allows_distinct_fixes(self):
        verdicts = [
            _verdict("vc", recommended_fix="Interview ten enterprise buyers."),
            _verdict("engineer", recommended_fix="Publish a reliability benchmark."),
        ]
        self.assertFalse(is_degenerate_fixes(verdicts))

    def test_is_degenerate_panel_matches_dict_inputs(self):
        uniform = [
            {"judge": "vc", "verdict": "PASS", "score": 10},
            {"judge": "pm", "verdict": "PASS", "score": 10},
        ]
        self.assertTrue(is_degenerate_panel(uniform))

    def test_fix_fields_missing_judges(self):
        missing = fix_fields_missing_judges(
            [
                {
                    "judge": "vc",
                    "recommended_fix": SAMPLE_FIX,
                    "evidence_to_change_verdict": SAMPLE_EVIDENCE,
                },
                {"judge": "pm"},
            ]
        )
        self.assertEqual(missing, ["pm"])

    def test_check_score_change_bounded_rejects_large_swings(self):
        original = _verdict("vc", score=3)
        revised = _verdict("vc", score=8, evidence_to_change_verdict="Debate changed my view.")
        check = check_score_change_bounded(original, revised, max_delta=3)
        self.assertIsNotNone(check)
        self.assertIn("max 3", check.message)

    def test_assess_revote_quality_flags_unexplained_and_herded(self):
        initial = [
            _verdict("vc", score=5),
            _verdict("engineer", score=5),
            _verdict("pm", score=5),
            _verdict("customer", score=5),
            _verdict("competitor", score=5),
        ]
        revised = [
            _verdict("vc", score=3, evidence_to_change_verdict=SAMPLE_EVIDENCE),
            _verdict("engineer", score=3, evidence_to_change_verdict="Round 2 engineer argument."),
            _verdict("pm", score=3, evidence_to_change_verdict="Round 2 pm argument."),
            _verdict("customer", score=3, evidence_to_change_verdict="Round 2 customer argument."),
            _verdict(
                "competitor", score=3, evidence_to_change_verdict="Round 2 competitor argument."
            ),
        ]
        quality = assess_revote_quality(
            [v.model_dump() for v in initial],
            [v.model_dump() for v in revised],
            max_delta=3,
        )
        self.assertTrue(quality["revote_present"])
        self.assertIn("vc", quality["revote_unexplained_changes"])
        self.assertTrue(quality["revote_herded_deltas"])
        self.assertFalse(quality["revote_passed"])

    def test_assess_revote_quality_flags_directional_pile_on(self):
        initial = [
            _verdict("vc", score=5),
            _verdict("engineer", score=5),
            _verdict("pm", score=5),
            _verdict("customer", score=4),
            _verdict("competitor", score=3),
        ]
        revised = [
            _verdict("vc", score=3, evidence_to_change_verdict="Round 2 customer argument."),
            _verdict("engineer", score=5),
            _verdict("pm", score=2, evidence_to_change_verdict="Round 3 pm argument."),
            _verdict("customer", score=1, evidence_to_change_verdict="Round 2 customer argument."),
            _verdict("competitor", score=3),
        ]
        quality = assess_revote_quality(
            [v.model_dump() for v in initial],
            [v.model_dump() for v in revised],
        )
        self.assertTrue(quality["revote_directional_pile_on"])
        self.assertEqual(quality["revote_pile_on_direction"], "down")


if __name__ == "__main__":
    unittest.main()
