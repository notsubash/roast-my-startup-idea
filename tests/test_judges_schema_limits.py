from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from judges.schemas import Verdict
import tests  # noqa: F401


class VerdictSchemaLimitsTest(unittest.TestCase):
    def test_verdict_truncates_overlong_recommended_fix_instead_of_failing(self):
        long_fix = "A" * 500
        verdict = Verdict(
            judge="vc",
            verdict="FAIL",
            roast="A" * 50,
            score=3,
            key_concern="Demand is not proven.",
            recommended_fix=long_fix,
        )
        self.assertLessEqual(len(verdict.recommended_fix), 400)
        self.assertTrue(verdict.recommended_fix.endswith("..."))

    def test_verdict_truncates_overlong_evidence_instead_of_failing(self):
        long_evidence = "B" * 500
        verdict = Verdict(
            judge="vc",
            verdict="FAIL",
            roast="A" * 50,
            score=3,
            key_concern="Demand is not proven.",
            evidence_to_change_verdict=long_evidence,
        )
        self.assertLessEqual(len(verdict.evidence_to_change_verdict), 400)
        self.assertTrue(verdict.evidence_to_change_verdict.endswith("..."))

    def test_legacy_verdict_json_without_fix_fields_loads(self):
        legacy_json = (
            '{"judge":"vc","verdict":"FAIL","roast":"The market is crowded and unclear.",'
            '"score":3,"key_concern":"No clear buyer path."}'
        )
        verdict = Verdict.model_validate_json(legacy_json)
        self.assertIsNone(verdict.recommended_fix)
        self.assertIsNone(verdict.evidence_to_change_verdict)

    def test_verdict_truncates_overlong_roast_instead_of_failing(self):
        long_roast = "A" * 1100
        verdict = Verdict(
            judge="vc",
            verdict="FAIL",
            roast=long_roast,
            score=3,
            key_concern="Demand is not proven.",
        )
        self.assertLessEqual(len(verdict.roast), 1000)
        self.assertTrue(verdict.roast.endswith("..."))


if __name__ == "__main__":
    unittest.main()
