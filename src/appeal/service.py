from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config import JUDGE_ORDER
from judges.schemas import RoastPanel, Verdict
from judges.service import judge_system_prompt


@dataclass(frozen=True)
class AppealResult:
    revised_panel: RoastPanel
    revised_synthesis: str


def _response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    return str(content).strip()


def _original_verdict(roast_panel: RoastPanel, judge: str) -> Verdict:
    for verdict in roast_panel.verdicts:
        if verdict.judge.value == judge:
            return verdict
    raise ValueError(f"Missing original verdict for judge: {judge}")


def _format_panel(panel: RoastPanel) -> str:
    return "\n".join(
        f"- {verdict.judge.value}: {verdict.verdict.value}, {verdict.score}/10, concern: {verdict.key_concern}"
        for verdict in panel.verdicts
    )


def invoke_judge_on_appeal(
    model,
    judge: str,
    startup_idea: str,
    roast_panel: RoastPanel,
    debate_result: dict,
    appeal_text: str,
    memory_context: str | None = None,
) -> Verdict:
    """Ask one judge to revise or defend their verdict after founder appeal."""
    original = _original_verdict(roast_panel, judge)
    structured_model = model.with_structured_output(Verdict)
    prior_context = f"\n\nPrior user memory:\n{memory_context}" if memory_context else ""

    return structured_model.invoke(
        [
            SystemMessage(content=judge_system_prompt(judge)),
            HumanMessage(
                content=(
                    f'You are re-evaluating the same startup idea as the "{judge}" judge. '
                    f"The judge field must be exactly {judge}.\n\n"
                    f"Startup idea:\n{startup_idea}\n\n"
                    f"Original verdict:\n{original.model_dump_json()}\n\n"
                    f"Original panel synthesis:\n{debate_result.get('final_synthesis') or 'No synthesis was produced.'}\n\n"
                    f"Founder appeal:\n{appeal_text}\n"
                    f"{prior_context}\n\n"
                    "Re-evaluate only if the founder materially addressed your original key concern. "
                    "You may keep, raise, or lower the score. Do not reward rhetoric without concrete evidence. "
                    "Return a complete Verdict object for your judge."
                )
            ),
        ]
    )


def synthesize_appeal(
    model,
    startup_idea: str,
    original_panel: RoastPanel,
    revised_panel: RoastPanel,
    original_synthesis: str | None,
    appeal_text: str,
) -> str:
    response = model.invoke(
        [
            {
                "role": "user",
                "content": (
                    "You are the moderator for Roast My Startup appeal mode.\n\n"
                    f"Startup idea:\n{startup_idea}\n\n"
                    f"Original synthesis:\n{original_synthesis or 'No original synthesis was produced.'}\n\n"
                    f"Founder appeal:\n{appeal_text}\n\n"
                    f"Original panel:\n{_format_panel(original_panel)}\n\n"
                    f"Revised panel:\n{_format_panel(revised_panel)}\n\n"
                    "Write a concise appeal synthesis. Explain what changed, what did not, "
                    "and whether the appeal materially improved the case."
                ),
            }
        ]
    )
    return _response_text(response)


def run_appeal(
    model,
    startup_idea: str,
    roast_panel: RoastPanel,
    debate_result: dict,
    appeal_text: str,
    memory_context: str | None = None,
) -> AppealResult:
    appeal_text = appeal_text.strip()
    if not appeal_text:
        raise ValueError("Appeal text is required")

    revised_verdicts = [
        invoke_judge_on_appeal(
            model=model,
            judge=judge,
            startup_idea=startup_idea,
            roast_panel=roast_panel,
            debate_result=debate_result,
            appeal_text=appeal_text,
            memory_context=memory_context,
        )
        for judge in JUDGE_ORDER
    ]
    revised_panel = RoastPanel(verdicts=revised_verdicts)
    revised_synthesis = synthesize_appeal(
        model=model,
        startup_idea=startup_idea,
        original_panel=roast_panel,
        revised_panel=revised_panel,
        original_synthesis=debate_result.get("final_synthesis"),
        appeal_text=appeal_text,
    )
    return AppealResult(revised_panel=revised_panel, revised_synthesis=revised_synthesis)
