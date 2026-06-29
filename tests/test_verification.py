from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from judges.schemas import Verdict, VerdictLabel, judgeLabel
import tests  # noqa: F401
from verification import (
    fix_fields_missing_judges,
    is_degenerate_fixes,
    is_degenerate_panel,
    score_verdict_mismatches,
    verify_verdict_invariants,
)

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


if __name__ == "__main__":
    unittest.main()
