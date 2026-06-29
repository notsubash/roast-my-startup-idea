from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from debate.nodes import make_moderator_node
import tests  # noqa: F401


class FakeResponse:
    def __init__(self, content: str):
        self.content = content


class StructuredFailModel:
    def __init__(self):
        self.prose_prompts: list[str] = []

    def with_structured_output(self, _schema):
        class Structured:
            def invoke(self, _messages, **_kwargs):
                raise ValueError("structured output unavailable")

        return Structured()

    def invoke(self, messages, **_kwargs):
        self.prose_prompts.append(messages[0]["content"])
        return FakeResponse(
            "**1. Overall verdict:** FAIL\n"
            "**2. Final score from 1-10:** 3\n"
            "**3. Consensus points**\n"
            "- Buyers are unconvinced."
        )


def _moderator_state() -> dict:
    return {
        "startup_idea": "AI tool that summarizes privacy policies.",
        "verdicts": [
            {
                "judge": "vc",
                "verdict": "FAIL",
                "score": 3,
                "key_concern": "No defensibility.",
            }
        ],
        "debate_messages": [
            {"speaker": "vc", "round": 1, "content": "Still no moat."},
        ],
        "round": 1,
    }


class ModeratorNodeTest(unittest.TestCase):
    def test_moderator_falls_back_to_legacy_prose_prompt(self):
        model = StructuredFailModel()
        result = make_moderator_node(model)(_moderator_state())

        self.assertIsNone(result["structured_synthesis"])
        self.assertIn("**1. Overall verdict:** FAIL", result["final_synthesis"])
        self.assertEqual(len(model.prose_prompts), 1)
        self.assertIn("Produce a final synthesis of the debate", model.prose_prompts[0])
        self.assertNotIn("overall_recommendation:", model.prose_prompts[0])


if __name__ == "__main__":
    unittest.main()
