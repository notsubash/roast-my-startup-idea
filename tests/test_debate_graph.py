from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from debate.graph import build_debate_graph
from debate.router import JUDGE_ORDER
import tests  # noqa: F401


class FakeResponse:
    def __init__(self, content: str | None):
        self.content = content


class FakeModel:
    def __init__(self):
        self.calls = 0

    def invoke(self, messages, **_kwargs):
        self.calls += 1
        return FakeResponse(f"Fake Response {self.calls}")


class TestDebateGraph(unittest.TestCase):
    def test_debate_routes_each_judge_for_each_round_then_moderates(self):
        model = FakeModel()
        graph = build_debate_graph(model)

        result = graph.invoke(
            {
                "startup_idea": "AI tool that summarizes privacy policies.",
                "verdicts": [
                    {
                        "judge": "vc",
                        "verdict": "FAIL",
                        "roast": "Weak moat.",
                        "score": 3,
                        "key_concern": "No defensibility.",
                    },
                    {
                        "judge": "engineer",
                        "verdict": "CONDITIONAL",
                        "roast": "Feasible but brittle.",
                        "score": 5,
                        "key_concern": "Extraction reliability.",
                    },
                    {
                        "judge": "pm",
                        "verdict": "FAIL",
                        "roast": "Unclear habit.",
                        "score": 3,
                        "key_concern": "Low user urgency.",
                    },
                    {
                        "judge": "customer",
                        "verdict": "FAIL",
                        "roast": "I would ignore it.",
                        "score": 2,
                        "key_concern": "Too much friction.",
                    },
                    {
                        "judge": "competitor",
                        "verdict": "FAIL",
                        "roast": "Easy to copy.",
                        "score": 2,
                        "key_concern": "Incumbents can bundle it.",
                    },
                ],
                "messages": [],
                "round": 1,
                "max_rounds": 2,
                "current_speaker_idx": 0,
                "final_synthesis": None,
            }
        )

        speaker_messages = [
            message for message in result["debate_messages"] if message["speaker"] != "moderator"
        ]

        self.assertEqual(
            [message["speaker"] for message in speaker_messages],
            JUDGE_ORDER + JUDGE_ORDER,
        )

        self.assertEqual(
            [message["round"] for message in speaker_messages],
            [1, 1, 1, 1, 1, 2, 2, 2, 2, 2],
        )

        self.assertEqual(
            result["debate_messages"][-1]["speaker"],
            "moderator",
        )

        self.assertIsNotNone(result["final_synthesis"])
        self.assertEqual(model.calls, 11)


if __name__ == "__main__":
    unittest.main()
