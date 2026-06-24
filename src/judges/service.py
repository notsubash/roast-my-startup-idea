"""Single-judge evaluation — no UI, no orchestration."""

from jinja2 import Environment, FileSystemLoader
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from config import PROMPTS_DIR
from judges.schemas import Verdict

template_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))
JUDGE_MAX_ATTEMPTS = 3

JUDGE_TEMPLATES = {
    "vc": "vc_judge_prompt.jinja2",
    "engineer": "engineer_judge_prompt.jinja2",
    "pm": "pm_judge_prompt.jinja2",
    "customer": "customer_judge_prompt.jinja2",
    "competitor": "competitor_judge_prompt.jinja2",
}


def judge_system_prompt(judge: str) -> str:
    return template_env.get_template(JUDGE_TEMPLATES[judge]).render()


def build_judge_user_prompt(
    startup_idea: str,
    memory_context: str | None = None,
    research_context: str | None = None,
) -> str:
    return template_env.get_template("judge_user_prompt.jinja2").render(
        startup_idea=startup_idea,
        memory_context=memory_context,
        research_context=research_context,
    )


def invoke_judge(
    model,
    judge: str,
    startup_idea: str,
    memory_context: str | None = None,
    research_context: str | None = None,
) -> Verdict:
    """Evaluate one startup idea with structured output."""
    user_content = build_judge_user_prompt(
        startup_idea=startup_idea,
        memory_context=memory_context,
        research_context=research_context,
    )

    structured_model = model.with_structured_output(Verdict)
    messages = [
        SystemMessage(content=judge_system_prompt(judge)),
        HumanMessage(content=user_content),
    ]

    last_validation_error: ValidationError | None = None
    for _ in range(JUDGE_MAX_ATTEMPTS):
        result = structured_model.invoke(messages)

        if result is None:
            continue

        try:
            return Verdict.model_validate(result)
        except ValidationError as exc:
            last_validation_error = exc

    if last_validation_error is not None:
        raise ValueError(
            f"{judge} judge returned an invalid structured verdict after "
            f"{JUDGE_MAX_ATTEMPTS} attempts: {last_validation_error}"
        ) from last_validation_error

    raise ValueError(
        f"{judge} judge returned no structured verdict after {JUDGE_MAX_ATTEMPTS} attempts"
    )
