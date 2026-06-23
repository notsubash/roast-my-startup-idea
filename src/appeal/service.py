from dataclasses import dataclass
from typing import Any

from jinja2 import Environment, FileSystemLoader
from langchain_core.messages import HumanMessage, SystemMessage

from config import JUDGE_ORDER, PROMPTS_DIR
from judges.schemas import RoastPanel, Verdict
from judges.service import judge_system_prompt

template_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))


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
    prompt = template_env.get_template("appeal_judge_prompt.jinja2").render(
        judge=judge,
        startup_idea=startup_idea,
        original_verdict_json=original.model_dump_json(),
        original_synthesis=debate_result.get("final_synthesis") or "No synthesis was produced.",
        appeal_text=appeal_text,
        memory_context=memory_context,
    )

    return structured_model.invoke(
        [
            SystemMessage(content=judge_system_prompt(judge)),
            HumanMessage(content=prompt),
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
    prompt = template_env.get_template("appeal_synthesis_prompt.jinja2").render(
        startup_idea=startup_idea,
        original_synthesis=original_synthesis or "No original synthesis was produced.",
        appeal_text=appeal_text,
        original_panel=_format_panel(original_panel),
        revised_panel=_format_panel(revised_panel),
    )
    response = model.invoke(
        [
            {
                "role": "user",
                "content": prompt,
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
