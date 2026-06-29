from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llm_resilience import call_with_llm_retry, is_transient_llm_error
import tests  # noqa: F401


class RemoteProtocolError(RuntimeError):
    """Stand-in for httpx/httpcore RemoteProtocolError in tests."""


class LLMResilienceTest(unittest.TestCase):
    def test_is_transient_llm_error_matches_by_type_name(self):
        self.assertTrue(is_transient_llm_error(RemoteProtocolError("peer closed")))

    def test_is_transient_llm_error_rejects_validation_errors(self):
        self.assertFalse(is_transient_llm_error(ValueError("bad verdict")))

    def test_call_with_llm_retry_recovers_after_transient_failure(self):
        calls = {"count": 0}

        def flaky() -> str:
            calls["count"] += 1
            if calls["count"] == 1:
                raise RemoteProtocolError("peer closed")
            return "ok"

        self.assertEqual(call_with_llm_retry(flaky, label="test call"), "ok")
        self.assertEqual(calls["count"], 2)


if __name__ == "__main__":
    unittest.main()
