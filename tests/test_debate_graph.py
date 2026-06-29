from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from debate.graph import build_debate_graph
from debate.router import JUDGE_ORDER
from judges.schemas import Verdict
import tests  # noqa: F401

SAMPLE_FIX = "Interview ten target buyers and document their top workflow pain before building."
SAMPLE_EVIDENCE = "Three signed LOIs from target buyers would change this verdict."


class FakeResponse:
    def __init__(self, content: str | None):
        self.content = content


def _revote_verdict(judge: str, score: int) -> Verdict:
    label = "FAIL" if score <= 3 else "CONDITIONAL" if score <= 6 else "PASS"
    return Verdict(
        judge=judge,
        verdict=label,
        roast=f"The {judge} judge still sees execution risk after the debate.",
        score=score,
        key_concern=f"The {judge} concern remains partially unresolved.",
        recommended_fix=SAMPLE_FIX,
        evidence_to_change_verdict=SAMPLE_EVIDENCE,
    )


class FakeStructuredModel:
    def invoke(self, messages, **_kwargs):
        parts = []
        for message in messages:
            content = getattr(message, "content", message)
            parts.append(content if isinstance(content, str) else str(content))
        prompt = "\n".join(parts)
        judge = "vc"
        for candidate in JUDGE_ORDER:
            if (
                f'"{candidate}"' in prompt
                or f"judge field must be exactly {candidate}" in prompt.lower()
            ):
                judge = candidate
                break
        scores = {"vc": 3, "engineer": 5, "pm": 4, "customer": 2, "competitor": 2}
        return _revote_verdict(judge, scores[judge])


class FakeModel:
    def __init__(self):
        self.calls = 0

    def _next_content(self) -> str:
        self.calls += 1
        return f"Fake Response {self.calls}"

    def with_structured_output(self, schema):
        return FakeStructuredModel()

    def stream(self, messages, **_kwargs):
        yield FakeResponse(self._next_content())

    def invoke(self, messages, **_kwargs):
        return FakeResponse(self._next_content())


class TestDebateGraph(unittest.TestCase):
    def test_debate_routes_each_judge_for_each_round_then_moderates(self):
        model = FakeModel()
        graph = build_debate_graph(model)

        verdicts = [
            {
                "judge": "vc",
                "verdict": "FAIL",
                "roast": "The moat is weak and the wedge is not defensible yet.",
                "score": 3,
                "key_concern": "No defensibility.",
            },
            {
                "judge": "engineer",
                "verdict": "CONDITIONAL",
                "roast": "Feasible to build but brittle under real production load.",
                "score": 5,
                "key_concern": "Extraction reliability.",
            },
            {
                "judge": "pm",
                "verdict": "FAIL",
                "roast": "The habit loop is unclear and retention looks weak.",
                "score": 3,
                "key_concern": "Low user urgency.",
            },
            {
                "judge": "customer",
                "verdict": "FAIL",
                "roast": "I would ignore this because the friction is too high.",
                "score": 2,
                "key_concern": "Too much friction.",
            },
            {
                "judge": "competitor",
                "verdict": "FAIL",
                "roast": "This is easy to copy and incumbents can bundle it.",
                "score": 2,
                "key_concern": "Incumbents can bundle it.",
            },
        ]

        result = graph.invoke(
            {
                "startup_idea": "AI tool that summarizes privacy policies.",
                "verdicts": verdicts,
                "initial_verdicts": verdicts,
                "messages": [],
                "round": 1,
                "max_rounds": 2,
                "current_speaker_idx": 0,
                "final_synthesis": None,
                "structured_synthesis": None,
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
        self.assertEqual(len(result["verdicts"]), 5)
        self.assertEqual(result["verdicts"][1]["score"], 5)
        self.assertEqual(model.calls, 11)


if __name__ == "__main__":
    unittest.main()
