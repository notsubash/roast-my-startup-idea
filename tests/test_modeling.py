from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from config import Settings
from modeling import build_chat_model
import tests  # noqa: F401


class ModelingTest(unittest.TestCase):
    def _settings(self) -> Settings:
        return Settings(
            local_model="ollama:qwen3.5:9b",
            deepseek_model="deepseek-v4-pro",
            deepseek_base_url="https://api.deepseek.com",
            embedding_model="ollama:nomic-embed-text",
            embedding_dimension=768,
            enable_semantic_memory=False,
            max_debate_rounds=3,
            enable_web_search=False,
            web_search_max_results=3,
            sse_heartbeat_seconds=15.0,
            stale_run_minutes=30,
            runs_db_path=Path("data/runs.db"),
        )

    @patch("modeling.init_chat_model")
    def test_build_chat_model_uses_local_model_for_local_choice(self, init_chat_model_mock):
        build_chat_model(
            "local",
            settings=self._settings(),
            deepseek_api_key=None,
        )
        init_chat_model_mock.assert_called_once_with("ollama:qwen3.5:9b")

    @patch("modeling.ChatDeepSeek")
    @patch("modeling.init_chat_model")
    def test_build_chat_model_uses_chatdeepseek_for_deepseek(
        self,
        init_chat_model_mock,
        chat_deepseek_mock,
    ):
        build_chat_model(
            "deepseek",
            settings=self._settings(),
            deepseek_api_key="secret",
        )
        chat_deepseek_mock.assert_called_once_with(
            model="deepseek-v4-pro",
            api_key="secret",
            base_url="https://api.deepseek.com",
            extra_body={"thinking": {"type": "disabled"}},
        )
        init_chat_model_mock.assert_not_called()

    @patch("modeling.ChatDeepSeek", None)
    def test_build_chat_model_rejects_deepseek_when_chatdeepseek_missing(self):
        with self.assertRaisesRegex(ValueError, "langchain-deepseek"):
            build_chat_model(
                "deepseek",
                settings=self._settings(),
                deepseek_api_key="secret",
            )

    def test_build_chat_model_rejects_missing_deepseek_key(self):
        with self.assertRaisesRegex(ValueError, "DEEPSEEK_API_KEY"):
            build_chat_model(
                "deepseek",
                settings=self._settings(),
                deepseek_api_key=None,
            )


if __name__ == "__main__":
    unittest.main()
