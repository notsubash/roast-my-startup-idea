from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from judges.schemas import Verdict, VerdictLabel, judgeLabel
import tests  # noqa: F401
from verification import assess_lens_uniqueness, find_duplicate_evidence_judges
from verification.lens import sentence_similarity

SAMPLE_FIX = "Interview ten target buyers and document their top workflow pain before building."
SAMPLE_EVIDENCE = "Three signed LOIs from target buyers would change this verdict."


def _verdict(
    judge: str,
    *,
    key_concern: str = "No clear buyer path.",
    recommended_fix: str | None = SAMPLE_FIX,
    evidence_to_change_verdict: str | None = SAMPLE_EVIDENCE,
) -> Verdict:
    return Verdict(
        judge=judgeLabel(judge),
        verdict=VerdictLabel.FAIL,
        roast="This idea lacks a credible buyer and clear wedge in a crowded market.",
        score=3,
        key_concern=key_concern,
        recommended_fix=recommended_fix,
        evidence_to_change_verdict=evidence_to_change_verdict,
    )


class LensUniquenessTest(unittest.TestCase):
    def test_assess_lens_uniqueness_skips_legacy_panels(self):
        legacy = [{"judge": "vc", "key_concern": "x", "score": 3, "verdict": "FAIL"}]
        result = assess_lens_uniqueness(legacy)
        self.assertTrue(result["lens_legacy"])
        self.assertTrue(result["lens_uniqueness_passed"])

    def test_find_duplicate_evidence_judges_flags_exact_and_near_duplicates(self):
        shared = "Three signed LOIs from enterprise buyers with fifty thousand ACV"
        near = "Three signed LOIs from enterprise buyers with fifty thousand ACV each"
        verdicts = [
            _verdict("vc", evidence_to_change_verdict=shared),
            _verdict("customer", evidence_to_change_verdict=shared),
            _verdict("engineer", evidence_to_change_verdict=near),
            _verdict("pm", evidence_to_change_verdict="Ten ICP interviews naming workflow pain."),
        ]
        duplicates = find_duplicate_evidence_judges(verdicts)
        self.assertIn("vc", duplicates)
        self.assertIn("customer", duplicates)
        self.assertIn("engineer", duplicates)
        self.assertNotIn("pm", duplicates)

    def test_assess_lens_uniqueness_skips_partial_evidence_panels(self):
        partial = [
            {
                "judge": "vc",
                "key_concern": "Weak returns.",
                "evidence_to_change_verdict": "Three signed LOIs.",
                "score": 3,
                "verdict": "FAIL",
            },
            {"judge": "engineer", "key_concern": "Unproven stack.", "score": 3, "verdict": "FAIL"},
        ]
        result = assess_lens_uniqueness(partial)
        self.assertTrue(result["lens_legacy"])
        self.assertTrue(result["lens_uniqueness_passed"])

    def test_assess_lens_uniqueness_flags_overlapping_concerns(self):
        shared_concern = "No credible buyer path for this wedge."
        verdicts = [
            _verdict(
                "vc",
                key_concern=shared_concern,
                evidence_to_change_verdict="Three signed LOIs with $50k+ ACV.",
            ),
            _verdict(
                "engineer",
                key_concern=shared_concern,
                evidence_to_change_verdict="Production benchmark with p99 under 200ms.",
            ),
            _verdict(
                "pm",
                key_concern="ICP is too broad.",
                evidence_to_change_verdict="Ten ICP interviews ranking pain top-two.",
            ),
            _verdict(
                "customer",
                key_concern="Price is too high.",
                evidence_to_change_verdict="Paid pilot with twenty renewals after month one.",
            ),
            _verdict(
                "competitor",
                key_concern="Easy to copy.",
                evidence_to_change_verdict="Exclusive distribution blocking incumbents for eighteen months.",
            ),
        ]
        result = assess_lens_uniqueness(verdicts)
        self.assertFalse(result["lens_legacy"])
        self.assertFalse(result["lens_uniqueness_passed"])
        self.assertEqual(len(result["lens_overlapping_concern_pairs"]), 1)

    def test_assess_lens_uniqueness_flags_generic_evidence_rate(self):
        verdicts = [
            _verdict("vc", evidence_to_change_verdict="Do more research on the buyer."),
            _verdict("engineer", evidence_to_change_verdict="Show more evidence."),
            _verdict("pm", evidence_to_change_verdict="Validate the market."),
            _verdict(
                "customer",
                evidence_to_change_verdict="Twenty users renew after month one at list price.",
            ),
            _verdict(
                "competitor",
                evidence_to_change_verdict="Exclusive channel blocks incumbent copy for eighteen months.",
            ),
        ]
        result = assess_lens_uniqueness(verdicts)
        self.assertFalse(result["lens_legacy"])
        self.assertFalse(result["lens_uniqueness_passed"])
        self.assertGreaterEqual(result["lens_generic_evidence_count"], 3)
        self.assertGreater(result["lens_generic_evidence_rate"], 0.4)

    def test_assess_lens_uniqueness_passes_distinct_lens_asks(self):
        verdicts = [
            _verdict(
                "vc",
                key_concern="Weak venture returns.",
                evidence_to_change_verdict="Three signed LOIs with $50k+ ACV.",
            ),
            _verdict(
                "engineer",
                key_concern="Unproven reliability at scale.",
                evidence_to_change_verdict="Production benchmark with p99 under 200ms.",
            ),
            _verdict(
                "pm",
                key_concern="ICP is too broad.",
                evidence_to_change_verdict="Ten ICP interviews ranking pain top-two.",
            ),
            _verdict(
                "customer",
                key_concern="Price is too high.",
                evidence_to_change_verdict="Paid pilot with twenty renewals after month one.",
            ),
            _verdict(
                "competitor",
                key_concern="Easy to copy.",
                evidence_to_change_verdict="Exclusive distribution blocking incumbents for eighteen months.",
            ),
        ]
        result = assess_lens_uniqueness(verdicts)
        self.assertTrue(result["lens_uniqueness_passed"])

    def test_sentence_similarity_catches_near_paraphrase(self):
        left = "three signed lois from enterprise buyers with fifty thousand acv"
        right = "three signed lois from enterprise buyers with fifty thousand acv each"
        self.assertGreaterEqual(sentence_similarity(left, right), 0.85)


if __name__ == "__main__":
    unittest.main()
