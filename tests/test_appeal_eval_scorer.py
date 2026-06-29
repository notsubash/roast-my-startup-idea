"""Unit tests for appeal discrimination eval scorer."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.scorers.appeal import score_appeal_discrimination
from judges.schemas import RoastPanel, Verdict, VerdictLabel, judgeLabel


def _verdict(judge: judgeLabel, score: int) -> Verdict:
    return Verdict(
        judge=judge,
        verdict=VerdictLabel.CONDITIONAL,
        roast="This pitch still leaves material gaps the founder must close.",
        score=score,
        key_concern="No LOIs yet.",
        evidence_to_change_verdict="Three signed LOIs would change this verdict.",
    )


class AppealDiscriminationScorerTests(unittest.TestCase):
    def test_strong_beats_weak_on_score_movement(self):
        baseline = RoastPanel(
            verdicts=[
                _verdict(judgeLabel.VC, 4),
                _verdict(judgeLabel.ENGINEER, 4),
                _verdict(judgeLabel.PM, 4),
                _verdict(judgeLabel.CUSTOMER, 4),
                _verdict(judgeLabel.COMPETITOR, 4),
            ]
        )
        result = {
            "roast_panel": baseline.model_dump(mode="json"),
            "appeal_weak": {
                "success": True,
                "revised_panel": baseline.model_dump(mode="json"),
            },
            "appeal_strong": {
                "success": True,
                "revised_panel": RoastPanel(
                    verdicts=[
                        baseline.verdicts[0].model_copy(update={"score": 6}),
                        *baseline.verdicts[1:],
                    ]
                ).model_dump(mode="json"),
            },
        }
        scored = score_appeal_discrimination(
            result,
            expected_delta_direction={"weak": "flat", "strong": "up"},
        )
        self.assertTrue(scored["appeal_beats_weak"])
        self.assertTrue(scored["appeal_discrimination_passed"])
        self.assertTrue(scored["appeal_weak_direction_ok"])
        self.assertTrue(scored["appeal_strong_direction_ok"])

    def test_skips_when_appeals_missing(self):
        scored = score_appeal_discrimination({})
        self.assertTrue(scored["appeal_discrimination_passed"])

    def test_tie_fails_discrimination(self):
        baseline = RoastPanel(
            verdicts=[
                _verdict(judgeLabel.VC, 4),
                _verdict(judgeLabel.ENGINEER, 4),
                _verdict(judgeLabel.PM, 4),
                _verdict(judgeLabel.CUSTOMER, 4),
                _verdict(judgeLabel.COMPETITOR, 4),
            ]
        )
        panel_json = baseline.model_dump(mode="json")
        result = {
            "roast_panel": panel_json,
            "appeal_weak": {"success": True, "revised_panel": panel_json},
            "appeal_strong": {"success": True, "revised_panel": panel_json},
        }
        scored = score_appeal_discrimination(result)
        self.assertFalse(scored["appeal_beats_weak"])
        self.assertFalse(scored["appeal_discrimination_passed"])


if __name__ == "__main__":
    unittest.main()
