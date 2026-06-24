import os
import unittest
from unittest.mock import patch

from observability.langsmith import (
    ObservabilitySettings,
    build_run_config,
    configure_observability,
    idea_fingerprint,
    is_tracing_enabled,
    load_observability_settings,
    optional_config_kwargs,
)


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self._original_env = os.environ.copy()
        os.environ.pop("ROAST_DISABLE_TRACING", None)
        for key in (
            "LANGSMITH_TRACING",
            "LANGSMITH_API_KEY",
            "LANGSMITH_PROJECT",
            "LANGSMITH_ENDPOINT",
            "LANGCHAIN_TRACING_V2",
            "LANGCHAIN_API_KEY",
            "LANGCHAIN_PROJECT",
            "LANGCHAIN_ENDPOINT",
        ):
            os.environ.pop(key, None)
        configure_observability.__globals__["_CONFIGURED"] = False

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._original_env)
        configure_observability.__globals__["_CONFIGURED"] = False
        from config import get_settings

        get_settings.cache_clear()

    def test_load_settings_supports_legacy_langchain_env_vars(self):
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = "legacy-key"
        os.environ["LANGCHAIN_PROJECT"] = "legacy-project"

        settings = load_observability_settings()

        self.assertTrue(settings.enabled)
        self.assertEqual(settings.api_key, "legacy-key")
        self.assertEqual(settings.project, "legacy-project")

    def test_configure_observability_sets_env_when_enabled(self):
        settings = ObservabilitySettings(
            enabled=True,
            api_key="test-key",
            project="test-project",
            endpoint=None,
        )

        enabled = configure_observability(settings)

        self.assertTrue(enabled)
        self.assertEqual(os.environ["LANGSMITH_TRACING"], "true")
        self.assertEqual(os.environ["LANGSMITH_API_KEY"], "test-key")
        self.assertEqual(os.environ["LANGSMITH_PROJECT"], "test-project")
        self.assertEqual(os.environ["LANGCHAIN_TRACING_V2"], "true")

    def test_configure_observability_disabled_without_api_key(self):
        settings = ObservabilitySettings(
            enabled=True,
            api_key=None,
            project="test-project",
            endpoint=None,
        )

        enabled = configure_observability(settings)

        self.assertFalse(enabled)
        self.assertNotIn("LANGSMITH_API_KEY", os.environ)

    def test_build_run_config_empty_when_tracing_disabled(self):
        config = build_run_config(
            "roast-pipeline",
            tags=["phase:roast"],
            metadata={"idea_fingerprint": "abc123"},
        )

        self.assertEqual(config, {})

    def test_build_run_config_includes_metadata_when_enabled(self):
        configure_observability(
            ObservabilitySettings(
                enabled=True,
                api_key="test-key",
                project="test-project",
                endpoint=None,
            )
        )

        config = build_run_config(
            "debate-graph",
            tags=["phase:debate"],
            metadata={"max_rounds": 3},
        )

        self.assertEqual(config["run_name"], "debate-graph")
        self.assertEqual(config["tags"], ["phase:debate"])
        self.assertEqual(config["metadata"]["max_rounds"], 3)
        self.assertTrue(is_tracing_enabled())

    def test_idea_fingerprint_hashes_and_truncates_preview(self):
        text = "An AI-powered journal for startup founders " * 5

        fingerprint = idea_fingerprint(text)

        self.assertIn(":", fingerprint)
        digest, preview = fingerprint.split(":", 1)
        self.assertEqual(len(digest), 12)
        self.assertLessEqual(len(preview), 80)

    def test_optional_config_kwargs_empty_when_tracing_disabled(self):
        self.assertEqual(optional_config_kwargs({}), {})
        self.assertEqual(optional_config_kwargs(None), {})

    def test_optional_config_kwargs_passes_config_when_enabled(self):
        configure_observability(
            ObservabilitySettings(
                enabled=True,
                api_key="test-key",
                project="test-project",
                endpoint=None,
            )
        )
        run_config = build_run_config("judge-vc")

        self.assertEqual(optional_config_kwargs(run_config), {"config": run_config})

    @patch("config.configure_observability")
    def test_get_settings_bootstraps_observability(self, configure_mock):
        from config import get_settings

        get_settings.cache_clear()
        get_settings()

        configure_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
