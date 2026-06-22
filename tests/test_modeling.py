import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import Settings
from modeling import build_chat_model


class ModelingTest(unittest.TestCase):
    def _settings(self) -> Settings:
        return Settings(
            local_model="ollama:qwen3.5:9b",
            deepseek_model="deepseek-v4-pro",
            deepseek_base_url="https://api.deepseek.com",
            max_debate_rounds=3,
            enable_web_search=False,
            web_search_max_results=3,
            deepseek_backend="langchain",
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
    def test_build_chat_model_prefers_chatdeepseek_when_backend_is_langchain(
        self,
        init_chat_model_mock,
        chat_deepseek_mock,
    ):
        build_chat_model(
            "deepseek",
            settings=self._settings(),
            deepseek_api_key="secret",
            deepseek_backend="langchain",
        )
        chat_deepseek_mock.assert_called_once_with(
            model="deepseek-v4-pro",
            api_key="secret",
            base_url="https://api.deepseek.com",
            extra_body={"thinking": {"type": "disabled"}},
        )
        init_chat_model_mock.assert_not_called()

    @patch("modeling.init_chat_model")
    def test_build_chat_model_uses_openai_compat_for_deepseek(self, init_chat_model_mock):
        build_chat_model(
            "deepseek",
            settings=self._settings(),
            deepseek_api_key="secret",
            deepseek_backend="openai",
        )
        init_chat_model_mock.assert_called_once_with(
            model="deepseek-v4-pro",
            model_provider="openai",
            base_url="https://api.deepseek.com",
            api_key="secret",
            extra_body={"thinking": {"type": "disabled"}},
        )

    @patch("modeling.ChatDeepSeek", None)
    @patch("modeling.init_chat_model")
    def test_build_chat_model_falls_back_to_openai_when_chatdeepseek_missing(
        self,
        init_chat_model_mock,
    ):
        build_chat_model(
            "deepseek",
            settings=self._settings(),
            deepseek_api_key="secret",
            deepseek_backend="langchain",
        )
        init_chat_model_mock.assert_called_once()

    def test_build_chat_model_rejects_missing_deepseek_key(self):
        with self.assertRaisesRegex(ValueError, "DEEPSEEK_API_KEY"):
            build_chat_model(
                "deepseek",
                settings=self._settings(),
                deepseek_api_key=None,
            )


if __name__ == "__main__":
    unittest.main()
