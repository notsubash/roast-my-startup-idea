"""Single-judge evaluation — no UI, no orchestration."""

from collections.abc import Callable
import json
import time
from typing import Literal

from jinja2 import Environment, FileSystemLoader
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from config import PROMPTS_DIR, get_settings
from idea_context import UNTRUSTED_DATA_INSTRUCTION, wrap_untrusted, wrap_user_idea
from judges.guardrails import GuardrailError, validate_structured_verdict
from judges.schemas import Verdict
from observability import build_run_config, idea_fingerprint, optional_config_kwargs
from observability.metrics import RunMetricsCollector

MetricsPhase = Literal["roast", "debate"]

template_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))
JUDGE_MAX_ATTEMPTS = 3

INJECTION_DEFENSE = UNTRUSTED_DATA_INSTRUCTION

DEGENERATE_PANEL_RETRY_SUFFIX = (
    "IMPORTANT: The prior panel returned identical scores from every judge, which is "
    "suspicious. Score independently from your rubric; do not copy other judges."
)

REVOTE_ANTI_HERD_SUFFIX = (
    "Re-vote from your role's rubric only. Do not herd to the loudest debate voice or "
    "parrot another judge's catchphrase unless it genuinely changed your assessment. "
    "There is no live founder in the debate — never cite founder non-responsiveness as evidence."
)

JUDGE_TEMPLATES = {
    "vc": "vc_judge_prompt.jinja2",
    "engineer": "engineer_judge_prompt.jinja2",
    "pm": "pm_judge_prompt.jinja2",
    "customer": "customer_judge_prompt.jinja2",
    "competitor": "competitor_judge_prompt.jinja2",
}


def judge_system_prompt(judge: str, *, suffix: str | None = None) -> str:
    template = template_env.get_template(JUDGE_TEMPLATES[judge]).render()
    prompt = f"{template}\n\n{INJECTION_DEFENSE}"
    if suffix:
        prompt = f"{prompt}\n\n{suffix}"
    return prompt


def build_judge_user_prompt(
    startup_idea: str,
    memory_context: str | None = None,
    research_context: str | None = None,
) -> str:
    return template_env.get_template("judge_user_prompt.jinja2").render(
        startup_idea=wrap_user_idea(startup_idea),
        memory_context=wrap_untrusted(memory_context, "memory") if memory_context else None,
        research_context=wrap_untrusted(research_context, "research") if research_context else None,
    )


def _message_text(messages) -> str:
    parts: list[str] = []
    for message in messages:
        content = getattr(message, "content", message)
        parts.append(content if isinstance(content, str) else str(content))
    return "\n\n".join(parts)


def _structured_result_text(result) -> str:
    if hasattr(result, "model_dump_json"):
        return result.model_dump_json()
    if isinstance(result, dict):
        return json.dumps(result)
    return str(result)


def invoke_structured_verdict(
    structured_model,
    messages,
    judge: str,
    *,
    run_config: dict,
    label: str = "judge",
    metrics: RunMetricsCollector | None = None,
    started_at: float | None = None,
    post_validate: Callable[[Verdict], None] | None = None,
    metrics_phase: MetricsPhase = "roast",
) -> Verdict:
    prompt_text = _message_text(messages)
    output_parts: list[str] = []
    attempt_started = started_at if started_at is not None else time.perf_counter()
    last_error: ValidationError | GuardrailError | None = None
    for attempt in range(JUDGE_MAX_ATTEMPTS):
        result = structured_model.invoke(messages, **optional_config_kwargs(run_config))

        if result is None:
            continue

        output_parts.append(_structured_result_text(result))

        try:
            verdict = Verdict.model_validate(result)
            validate_structured_verdict(verdict, judge=judge)
            if post_validate is not None:
                post_validate(verdict)
            if metrics is not None:
                elapsed = time.perf_counter() - attempt_started
                if metrics_phase == "debate":
                    metrics.record_debate(
                        f"revote-{judge}",
                        seconds=elapsed,
                        response=result,
                        prompt_text=prompt_text,
                        output_text="\n".join(output_parts),
                    )
                else:
                    metrics.record_judge(
                        judge,
                        seconds=elapsed,
                        response=result,
                        prompt_text=prompt_text,
                        output_text="\n".join(output_parts),
                    )
            return verdict
        except (ValidationError, GuardrailError) as exc:
            last_error = exc
            if attempt + 1 < JUDGE_MAX_ATTEMPTS:
                evidence_hint = (
                    "evidence_to_change_verdict must cite what in the debate changed your score."
                    if label == "revote judge"
                    else "evidence_to_change_verdict must name verifiable "
                    "proof that would change your score."
                )
                bounds_hint = (
                    f" Score may move at most {get_settings().max_revote_score_delta} points per re-vote."
                    if label == "revote judge"
                    else ""
                )
                messages = [
                    *messages,
                    HumanMessage(
                        content=(
                            f"Your previous structured verdict was rejected: {exc}. "
                            "Return a corrected complete Verdict JSON. "
                            "recommended_fix must prescribe a concrete next action beyond "
                            f"key_concern. {evidence_hint}{bounds_hint}"
                        )
                    ),
                ]

    if last_error is not None:
        raise ValueError(
            f"{judge} {label} returned an invalid structured verdict after "
            f"{JUDGE_MAX_ATTEMPTS} attempts: {last_error}"
        ) from last_error

    raise ValueError(
        f"{judge} {label} returned no structured verdict after {JUDGE_MAX_ATTEMPTS} attempts"
    )


def invoke_judge(
    model,
    judge: str,
    startup_idea: str,
    memory_context: str | None = None,
    research_context: str | None = None,
    run_config: dict | None = None,
    *,
    system_suffix: str | None = None,
    metrics: RunMetricsCollector | None = None,
) -> Verdict:
    """Evaluate one startup idea with structured output."""
    user_content = build_judge_user_prompt(
        startup_idea=startup_idea,
        memory_context=memory_context,
        research_context=research_context,
    )

    structured_model = model.with_structured_output(Verdict)
    messages = [
        SystemMessage(content=judge_system_prompt(judge, suffix=system_suffix)),
        HumanMessage(content=user_content),
    ]
    resolved_config = run_config or build_run_config(
        f"judge-{judge}",
        tags=["phase:roast", f"judge:{judge}"],
        metadata={"idea_fingerprint": idea_fingerprint(startup_idea)},
    )

    started_at = time.perf_counter()
    return invoke_structured_verdict(
        structured_model,
        messages,
        judge,
        run_config=resolved_config,
        label="judge",
        metrics=metrics,
        started_at=started_at,
    )
