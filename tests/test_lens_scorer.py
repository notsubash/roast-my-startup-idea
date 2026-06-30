from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evals.scorers.lens import score_lens_differentiation


class LensScorerTest(unittest.TestCase):
    def test_score_lens_differentiation_passes_distinct_asks(self):
        verdicts = [
            {
                "judge": "vc",
                "evidence_to_change_verdict": "Three signed LOIs with $50k ACV.",
                "key_concern": "Weak fundability.",
            },
            {
                "judge": "engineer",
                "evidence_to_change_verdict": "Benchmark p99 latency under 200ms.",
                "key_concern": "Unproven stack.",
            },
            {
                "judge": "pm",
                "evidence_to_change_verdict": "Ten ICP interviews naming top-two pain.",
                "key_concern": "Unclear ICP.",
            },
            {
                "judge": "customer",
                "evidence_to_change_verdict": "Twenty paid pilots without month-one churn.",
                "key_concern": "No willingness to pay.",
            },
            {
                "judge": "competitor",
                "evidence_to_change_verdict": "Exclusive distribution for eighteen months.",
                "key_concern": "Easy to copy.",
            },
        ]
        result = score_lens_differentiation(verdicts)
        self.assertFalse(result["lens_legacy"])
        self.assertTrue(result["lens_differentiation_passed"])
        self.assertTrue(result["passed"])

    def test_score_lens_differentiation_fails_duplicate_asks(self):
        shared = "Provide more evidence and validate the market."
        verdicts = [
            {
                "judge": "vc",
                "evidence_to_change_verdict": shared,
                "key_concern": "Weak fundability.",
            },
            {
                "judge": "customer",
                "evidence_to_change_verdict": shared,
                "key_concern": "No buyers.",
            },
            {
                "judge": "engineer",
                "evidence_to_change_verdict": "Ship latency benchmarks.",
                "key_concern": "Stack risk.",
            },
            {
                "judge": "pm",
                "evidence_to_change_verdict": "Ten ICP interviews.",
                "key_concern": "ICP unclear.",
            },
            {
                "judge": "competitor",
                "evidence_to_change_verdict": "Exclusive distribution.",
                "key_concern": "No moat.",
            },
        ]
        result = score_lens_differentiation(verdicts)
        self.assertFalse(result["lens_legacy"])
        self.assertFalse(result["lens_differentiation_passed"])
        self.assertIn("vc", result["lens_duplicate_evidence_judges"])

    def test_score_lens_differentiation_skips_legacy_panels(self):
        verdicts = [{"judge": "vc", "key_concern": "Only concern."}]
        result = score_lens_differentiation(verdicts)
        self.assertTrue(result["lens_legacy"])
        self.assertTrue(result["lens_differentiation_passed"])


if __name__ == "__main__":
    unittest.main()
