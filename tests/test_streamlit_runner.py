from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import tests  # noqa: F401

sys.modules.setdefault(
    "streamlit",
    types.SimpleNamespace(
        markdown=lambda *args, **kwargs: None,
        write=lambda *args, **kwargs: None,
    ),
)

from judges.schemas import RoastPanel, Verdict
from observability.metrics import format_run_metrics_footer
from ui.streamlit_runner import run_deepagent_roast_in_status


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


class FakeStatus:
    def __init__(self):
        self.messages: list[str] = []

    def write(self, message: str):
        self.messages.append(message)


class StreamlitRunnerTest(unittest.TestCase):
    @patch("ui.streamlit_runner.run_roast_panel")
    @patch("ui.streamlit_runner.run_roast_via_orchestrator")
    def test_run_deepagent_roast_falls_back_to_deterministic_on_parser_failure(
        self,
        run_roast_via_orchestrator_mock,
        run_roast_panel_mock,
    ):
        run_roast_via_orchestrator_mock.side_effect = ValueError(
            "No valid RoastPanel or individual judge verdicts found"
        )
        panel = _panel()
        run_roast_panel_mock.return_value = panel
        status = FakeStatus()

        result = run_deepagent_roast_in_status(
            model=object(),
            startup_idea="Wearable spatial-audio translator for deaf users",
            status=status,
            memory_context="prior memory",
            research_context=None,
            web_search_enabled=True,
        )

        self.assertEqual(result, panel)
        self.assertTrue(
            any("falling back to deterministic phase 1" in m.lower() for m in status.messages)
        )
        run_roast_panel_mock.assert_called_once()

    def test_format_run_metrics_footer_matches_spec_example(self):
        footer = format_run_metrics_footer(
            {
                "roast_seconds": 4.2,
                "debate_seconds": 11.8,
                "total_tokens": 3100,
                "estimated_cost_usd": 0.004,
            }
        )
        self.assertEqual(footer, "Roast 4.2s · Debate 11.8s · ~3.1k tokens · ~$0.004")


if __name__ == "__main__":
    unittest.main()
