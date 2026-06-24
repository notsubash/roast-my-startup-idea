from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from judges.schemas import RoastPanel, Verdict
from pipeline import run_deepagent_pipeline


def _panel() -> RoastPanel:
    return RoastPanel(
        verdicts=[
            Verdict(
                judge="vc",
                verdict="FAIL",
                roast="Weak moat and costly distribution in a crowded market.",
                score=3,
                key_concern="No durable moat.",
            ),
            Verdict(
                judge="engineer",
                verdict="CONDITIONAL",
                roast="Feasible architecture, but reliability and integrations are more complex than presented.",
                score=5,
                key_concern="Reliability risk.",
            ),
            Verdict(
                judge="pm",
                verdict="FAIL",
                roast="The target persona is broad and the wedge is not concrete enough to drive retention.",
                score=4,
                key_concern="Unclear ICP.",
            ),
            Verdict(
                judge="customer",
                verdict="FAIL",
                roast="I would not switch unless this replaces my current workflow with near-zero friction.",
                score=3,
                key_concern="Weak switching incentive.",
            ),
            Verdict(
                judge="competitor",
                verdict="FAIL",
                roast="Incumbents can copy this quickly as a bundled feature once demand appears.",
                score=2,
                key_concern="Easy replication.",
            ),
        ]
    )


class DeepAgentPipelineTest(unittest.TestCase):
    @patch("pipeline.run_debate")
    @patch("pipeline.run_roast_via_orchestrator")
    def test_run_deepagent_pipeline_uses_orchestrator_for_phase_one(
        self,
        run_roast_via_orchestrator_mock,
        run_debate_mock,
    ):
        panel = _panel()
        run_roast_via_orchestrator_mock.return_value = panel
        run_debate_mock.return_value = {"debate_messages": [], "final_synthesis": "summary"}

        roast_panel, debate_result = run_deepagent_pipeline(
            model=object(),
            startup_idea="AI copilot for regulated healthcare onboarding",
            max_debate_rounds=2,
        )

        self.assertEqual(roast_panel, panel)
        self.assertEqual(debate_result["final_synthesis"], "summary")
        run_roast_via_orchestrator_mock.assert_called_once()
        run_debate_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
