from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from judges.service import invoke_judge
import tests  # noqa: F401

SAMPLE_FIX = (
    "Interview ten municipal buyers and document their procurement workflow before building."
)
SAMPLE_EVIDENCE = (
    "Three signed pilot agreements with city public-works departments would change this verdict."
)


class FakeStructuredModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def invoke(self, messages, **_kwargs):
        self.calls += 1
        return self.responses.pop(0)


class FakeModel:
    def __init__(self, responses):
        self.structured_model = FakeStructuredModel(responses)

    def with_structured_output(self, schema):
        return self.structured_model


class JudgeServiceTest(unittest.TestCase):
    def test_invoke_judge_rejects_missing_structured_verdict(self):
        model = FakeModel([None, None, None])

        with self.assertRaisesRegex(
            ValueError,
            "pm judge returned no structured verdict",
        ):
            invoke_judge(
                model=model,
                judge="pm",
                startup_idea="AI pothole detection for municipalities",
            )

        self.assertEqual(model.structured_model.calls, 3)

    def test_invoke_judge_retries_missing_structured_verdict(self):
        model = FakeModel(
            [
                None,
                {
                    "judge": "pm",
                    "verdict": "CONDITIONAL",
                    "roast": "The target buyer and workflow are too fuzzy for a reliable product strategy.",
                    "score": 4,
                    "key_concern": "The municipal buyer path is not clear enough.",
                    "recommended_fix": SAMPLE_FIX,
                    "evidence_to_change_verdict": SAMPLE_EVIDENCE,
                },
            ]
        )

        verdict = invoke_judge(
            model=model,
            judge="pm",
            startup_idea="AI pothole detection for municipalities",
        )

        self.assertEqual(verdict.judge.value, "pm")
        self.assertEqual(model.structured_model.calls, 2)


if __name__ == "__main__":
    unittest.main()
