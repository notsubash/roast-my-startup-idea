import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import Settings
from judges.schemas import RoastPanel, Verdict
from orchestrator.deep_agent import build_orchestrator, run_roast_via_orchestrator


class DeepAgentOrchestratorTest(unittest.TestCase):
    @patch("orchestrator.deep_agent.create_deep_agent")
    @patch("orchestrator.deep_agent.get_settings")
    def test_build_orchestrator_registers_response_format_per_subagent(
        self,
        get_settings_mock,
        create_deep_agent_mock,
    ):
        get_settings_mock.return_value = Settings(
            local_model="ollama:qwen3.5:9b",
            deepseek_model="deepseek-v4-pro",
            deepseek_base_url="https://api.deepseek.com",
            max_debate_rounds=3,
            enable_web_search=False,
            web_search_max_results=3,
        )
        create_deep_agent_mock.return_value = object()

        build_orchestrator(model=object(), web_search_enabled=False)

        kwargs = create_deep_agent_mock.call_args.kwargs
        subagents = kwargs["subagents"]
        self.assertEqual(len(subagents), 5)
        self.assertTrue(all(agent.get("response_format") is Verdict for agent in subagents))

    @patch("orchestrator.deep_agent.extract_roast_panel")
    @patch("orchestrator.deep_agent.build_orchestrator")
    def test_run_roast_via_orchestrator_retries_without_response_format_on_400(
        self,
        build_orchestrator_mock,
        extract_roast_panel_mock,
    ):
        class FailingAgent:
            def invoke(self, payload):
                raise RuntimeError(
                    "Error code: 400 - {'error': {'message': 'This response_format type is unavailable now'}}"
                )

        class SucceedingAgent:
            def invoke(self, payload):
                return {"messages": []}

        panel = RoastPanel(
            verdicts=[
                Verdict(judge="vc", verdict="FAIL", roast="Weak moat and expensive go-to-market in a crowded category.", score=3, key_concern="No durable moat."),
                Verdict(judge="engineer", verdict="CONDITIONAL", roast="Feasible design, but reliability and edge-case handling are significantly harder than pitched.", score=5, key_concern="Reliability risk."),
                Verdict(judge="pm", verdict="FAIL", roast="Target user remains broad, making prioritization and retention strategy too fuzzy.", score=4, key_concern="Unclear ICP."),
                Verdict(judge="customer", verdict="FAIL", roast="I would not switch from current workflows unless value is immediate and obvious.", score=3, key_concern="Weak switching incentive."),
                Verdict(judge="competitor", verdict="FAIL", roast="Incumbents can copy this quickly as a bundled capability once traction appears.", score=2, key_concern="Easy replication."),
            ]
        )
        build_orchestrator_mock.side_effect = [FailingAgent(), SucceedingAgent()]
        extract_roast_panel_mock.return_value = panel

        result = run_roast_via_orchestrator(
            model=object(),
            startup_idea="Wearable spatial-audio translator",
            web_search_enabled=False,
        )

        self.assertEqual(result, panel)
        self.assertEqual(build_orchestrator_mock.call_count, 2)
        first_call = build_orchestrator_mock.call_args_list[0]
        second_call = build_orchestrator_mock.call_args_list[1]
        self.assertTrue(first_call.kwargs.get("subagent_response_format"))
        self.assertFalse(second_call.kwargs.get("subagent_response_format"))


if __name__ == "__main__":
    unittest.main()
