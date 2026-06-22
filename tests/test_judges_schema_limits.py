import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from judges.schemas import Verdict


class VerdictSchemaLimitsTest(unittest.TestCase):
    def test_verdict_truncates_overlong_roast_instead_of_failing(self):
        long_roast = "A" * 900
        verdict = Verdict(
            judge="vc",
            verdict="FAIL",
            roast=long_roast,
            score=3,
            key_concern="Demand is not proven.",
        )
        self.assertLessEqual(len(verdict.roast), 600)
        self.assertTrue(verdict.roast.endswith("..."))


if __name__ == "__main__":
    unittest.main()
