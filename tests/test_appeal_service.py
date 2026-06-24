from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from appeal.service import run_appeal
from judges.schemas import RoastPanel, Verdict


class FakeStructuredModel:
    def __init__(self):
        self.prompts: list[str] = []

    def invoke(self, messages):
        prompt = "\n".join(message.content for message in messages)
        self.prompts.append(prompt)
        judge = "vc"
        for candidate in ["vc", "engineer", "pm", "customer", "competitor"]:
            if (
                f'"{candidate}"' in prompt
                or f"judge field must be exactly {candidate}" in prompt.lower()
            ):
                judge = candidate
                break

        return Verdict(
            judge=judge,
            verdict="CONDITIONAL",
            roast=f"The appeal helps, but {judge} still sees material execution risk in this pitch.",
            score=6,
            key_concern="The founder needs more evidence before this becomes a clear pass.",
        )


class FakeAppealModel:
    def __init__(self):
        self.structured_model = FakeStructuredModel()
        self.synthesis_prompts: list[str] = []

    def with_structured_output(self, schema):
        self.schema = schema
        return self.structured_model

    def invoke(self, messages):
        prompt = "\n".join(message["content"] for message in messages)
        self.synthesis_prompts.append(prompt)

        class Response:
            content = "The appeal improved the case, but the panel still needs harder evidence before upgrading beyond conditional."

        return Response()


def _original_panel() -> RoastPanel:
    return RoastPanel(
        verdicts=[
            Verdict(
                judge="vc",
                verdict="FAIL",
                roast="The market feels too small for venture scale.",
                score=3,
                key_concern="The market is not clearly venture scale.",
            ),
            Verdict(
                judge="engineer",
                verdict="FAIL",
                roast="The prototype is easy; reliable production behavior is the hard part.",
                score=4,
                key_concern="Reliability is unproven.",
            ),
            Verdict(
                judge="pm",
                verdict="FAIL",
                roast="The ICP is not narrow enough to guide product decisions.",
                score=3,
                key_concern="The ICP is too broad.",
            ),
            Verdict(
                judge="customer",
                verdict="FAIL",
                roast="I would not pay unless the savings are obvious in week one.",
                score=3,
                key_concern="Willingness to pay is unclear.",
            ),
            Verdict(
                judge="competitor",
                verdict="FAIL",
                roast="We could add this as a feature if it gets traction.",
                score=2,
                key_concern="Incumbents can copy it quickly.",
            ),
        ]
    )


class AppealServiceTest(unittest.TestCase):
    def test_invoke_judge_on_appeal_retries_when_structured_output_is_none(self):
        from appeal.service import invoke_judge_on_appeal

        calls = {"count": 0}

        class FlakyStructuredModel:
            def invoke(self, messages):
                calls["count"] += 1
                if calls["count"] < 2:
                    return None
                return Verdict(
                    judge="customer",
                    verdict="CONDITIONAL",
                    roast="The appeal adds useful context, but switching costs still dominate the decision.",
                    score=5,
                    key_concern="Payroll migration risk remains the main blocker.",
                )

        class FlakyModel:
            def with_structured_output(self, schema):
                return FlakyStructuredModel()

        verdict = invoke_judge_on_appeal(
            FlakyModel(),
            "customer",
            "AI payroll for home-health agencies",
            _original_panel(),
            {"final_synthesis": "Needs stronger proof."},
            "We have signed LOIs from three agencies.",
        )

        self.assertEqual(verdict.judge.value, "customer")
        self.assertEqual(calls["count"], 2)

    def test_run_appeal_passes_user_rebuttal_to_each_judge_and_synthesizes(self):
        model = FakeAppealModel()
        appeal_text = "We already have three hospital pilots and signed LOIs worth $180k ARR."

        result = run_appeal(
            model=model,
            startup_idea="AI compliance copilot for hospitals",
            roast_panel=_original_panel(),
            debate_result={"final_synthesis": "The idea needs proof of demand."},
            appeal_text=appeal_text,
            memory_context="Prior pitch scored 3.0/10 because demand was vague.",
        )

        self.assertEqual(len(result.revised_panel.verdicts), 5)
        self.assertEqual(
            {verdict.judge.value for verdict in result.revised_panel.verdicts},
            {"vc", "engineer", "pm", "customer", "competitor"},
        )
        self.assertIn("panel still needs harder evidence", result.revised_synthesis)
        self.assertEqual(len(model.structured_model.prompts), 5)
        self.assertTrue(all(appeal_text in prompt for prompt in model.structured_model.prompts))
        self.assertIn("Prior pitch scored", model.structured_model.prompts[0])
        self.assertIn("signed LOIs", model.synthesis_prompts[0])


if __name__ == "__main__":
    unittest.main()
