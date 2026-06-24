from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
import tests  # noqa: F401

sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evals import BASELINE_SOURCES, EVAL_RUNTIMES
from evals.run_eval import run_local_eval


class EvalRunRuntimeTest(unittest.TestCase):
    def test_eval_runtimes_include_local_and_deepseek(self):
        self.assertEqual(EVAL_RUNTIMES, ("local", "deepseek"))
        self.assertIn("synthetic", BASELINE_SOURCES)

    def test_run_local_eval_rejects_unknown_runtime(self):
        with self.assertRaisesRegex(ValueError, "Unsupported runtime"):
            run_local_eval(runtime="openai")

    @patch("evals.run_eval.run_idea_eval")
    @patch("evals.run_eval.filter_ideas")
    @patch("evals.run_eval.load_golden_ideas")
    @patch("evals.run_eval.build_chat_model")
    @patch("evals.run_eval.get_settings")
    def test_run_local_eval_uses_deepseek_runtime(
        self,
        get_settings_mock,
        build_chat_model_mock,
        load_golden_ideas_mock,
        filter_ideas_mock,
        run_idea_eval_mock,
    ):
        from evals.dataset.loader import load_golden_ideas

        idea = next(item for item in load_golden_ideas() if item.id == "smartpatch")
        load_golden_ideas_mock.return_value = [idea]
        filter_ideas_mock.return_value = [idea]
        get_settings_mock.return_value = type(
            "Settings",
            (),
            {
                "max_debate_rounds": 2,
                "local_model": "qwen3.5:9b",
                "deepseek_model": "deepseek-v4-pro",
            },
        )()
        run_idea_eval_mock.return_value = {
            "idea_id": "smartpatch",
            "idea_text": "Test idea",
            "tags": ["hardware"],
            "judge_attempts": [{"judge": "vc", "success": True}],
            "roast_panel": {"verdicts": [{"judge": "vc"}]},
            "debate_result": {"debate_messages": [], "final_synthesis": "ok"},
            "timings": {"roast_seconds": 1.0, "debate_seconds": 1.0, "total_seconds": 2.0},
        }

        payload = run_local_eval(runtime="deepseek", full=False, limit=1, include_appeals=False)

        build_chat_model_mock.assert_called_once()
        self.assertEqual(build_chat_model_mock.call_args[0][0], "deepseek")
        self.assertEqual(payload["runtime"], "deepseek")
        self.assertEqual(payload["model"], "deepseek-v4-pro")
        self.assertEqual(payload["tier"], "golden")


if __name__ == "__main__":
    unittest.main()
