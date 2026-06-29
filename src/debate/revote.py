"""Post-debate re-vote — each judge revises their verdict after the full transcript."""

from __future__ import annotations

from collections.abc import Callable
import concurrent.futures

from jinja2 import Environment, FileSystemLoader
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer

from config import JUDGE_ORDER, PROMPTS_DIR, get_settings
from idea_context import wrap_untrusted, wrap_user_idea
from judges.guardrails import is_degenerate_panel, validate_revote_verdict
from judges.schemas import RoastPanel, Verdict
from judges.service import (
    DEGENERATE_PANEL_RETRY_SUFFIX,
    REVOTE_ANTI_HERD_SUFFIX,
    invoke_structured_verdict,
    judge_system_prompt,
)
from observability import build_run_config, idea_fingerprint, traceable
from observability.metrics import RunMetricsCollector
from run_control import check_abort

template_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))


def score_change_reason(original: Verdict, revised: Verdict) -> str | None:
    """One-line debate justification when a judge moved their score."""
    if original.score == revised.score:
        return None
    return (revised.evidence_to_change_verdict or "").strip() or None


def _original_verdict(roast_panel: RoastPanel, judge: str) -> Verdict:
    for verdict in roast_panel.verdicts:
        if verdict.judge.value == judge:
            return verdict
    raise ValueError(f"Missing original verdict for judge: {judge}")


def _full_transcript(debate_messages: list[dict]) -> str:
    lines = [
        f"Round {msg['round']}: {msg['speaker']}: {msg['content']}"
        for msg in debate_messages
        if msg.get("speaker") != "moderator"
    ]
    raw = "\n".join(lines) if lines else "No debate messages were recorded."
    return wrap_untrusted(raw, "debate")


def invoke_judge_on_revote(
    model,
    judge: str,
    startup_idea: str,
    roast_panel: RoastPanel,
    debate_messages: list[dict],
    *,
    run_config: dict | None = None,
    metrics: RunMetricsCollector | None = None,
    system_suffix: str | None = None,
) -> Verdict:
    """Ask one judge to revise or defend their verdict after the debate."""
    original = _original_verdict(roast_panel, judge)
    structured_model = model.with_structured_output(Verdict)
    prompt = template_env.get_template("revote_judge_prompt.jinja2").render(
        judge=judge,
        startup_idea=wrap_user_idea(startup_idea),
        original_verdict_json=original.model_dump_json(),
        debate_transcript=_full_transcript(debate_messages),
        max_score_delta=get_settings().max_revote_score_delta,
    )
    messages = [
        SystemMessage(
            content=judge_system_prompt(
                judge,
                suffix=REVOTE_ANTI_HERD_SUFFIX
                if not system_suffix
                else f"{REVOTE_ANTI_HERD_SUFFIX}\n\n{system_suffix}",
            )
        ),
        HumanMessage(content=prompt),
    ]
    resolved_config = run_config or build_run_config(
        f"revote-judge-{judge}",
        tags=["phase:debate", "step:revote", f"judge:{judge}"],
        metadata={"idea_fingerprint": idea_fingerprint(startup_idea)},
    )

    def _post_validate(revised: Verdict) -> None:
        validate_revote_verdict(original, revised)

    return invoke_structured_verdict(
        structured_model,
        messages,
        judge,
        run_config=resolved_config,
        label="revote judge",
        metrics=metrics,
        metrics_phase="debate",
        post_validate=_post_validate,
    )


def _emit_revote_custom(event: dict) -> None:
    try:
        writer = get_stream_writer()
    except RuntimeError:
        # ponytail: direct run_revote() calls (tests, CLI) have no graph stream writer.
        return
    if writer:
        writer(event)


def _run_revote_panel(
    model,
    startup_idea: str,
    roast_panel: RoastPanel,
    debate_messages: list[dict],
    run_config: dict,
    *,
    system_suffix: str | None = None,
    metrics: RunMetricsCollector | None = None,
    abort_check: Callable[[], str | None] | None = None,
    emit_events: bool = True,
) -> dict[str, Verdict]:
    total = len(JUDGE_ORDER)
    originals = {judge: _original_verdict(roast_panel, judge) for judge in JUDGE_ORDER}
    if emit_events:
        _emit_revote_custom({"type": "revote_started", "total": total})

    with concurrent.futures.ThreadPoolExecutor(max_workers=total) as pool:
        future_to_judge = {
            pool.submit(
                invoke_judge_on_revote,
                model,
                judge,
                startup_idea,
                roast_panel,
                debate_messages,
                run_config=run_config,
                metrics=metrics,
                system_suffix=system_suffix,
            ): judge
            for judge in JUDGE_ORDER
        }
        results: dict[str, Verdict] = {}
        completed = 0
        for future in concurrent.futures.as_completed(future_to_judge):
            check_abort(abort_check)
            judge = future_to_judge[future]
            verdict = future.result()
            results[judge] = verdict
            completed += 1
            original = originals[judge]
            if emit_events:
                _emit_revote_custom(
                    {
                        "type": "revote_judge",
                        "judge": judge,
                        "verdict": verdict.model_dump(),
                        "original_score": original.score,
                        "completed": completed,
                        "total": total,
                        "change_reason": score_change_reason(original, verdict),
                    }
                )
    return results


@traceable(name="run_revote", run_type="chain", tags=["phase:debate", "step:revote"])
def run_revote(
    model,
    startup_idea: str,
    roast_panel: RoastPanel,
    debate_messages: list[dict],
    *,
    run_config: dict | None = None,
    metrics: RunMetricsCollector | None = None,
    abort_check: Callable[[], str | None] | None = None,
) -> RoastPanel:
    """Re-vote all judges in parallel; retry once on degenerate panels."""
    resolved_config = run_config or build_run_config(
        "revote-panel",
        tags=["phase:debate", "step:revote"],
        metadata={"idea_fingerprint": idea_fingerprint(startup_idea)},
    )

    results = _run_revote_panel(
        model,
        startup_idea,
        roast_panel,
        debate_messages,
        resolved_config,
        metrics=metrics,
        abort_check=abort_check,
    )
    verdicts = [results[judge] for judge in JUDGE_ORDER]

    if is_degenerate_panel(verdicts):
        # ponytail: one anti-collusion retry, same pattern as roast panel.
        if metrics is not None:
            metrics.discard_phase("debate")
        results = _run_revote_panel(
            model,
            startup_idea,
            roast_panel,
            debate_messages,
            resolved_config,
            system_suffix=DEGENERATE_PANEL_RETRY_SUFFIX,
            metrics=metrics,
            abort_check=abort_check,
            emit_events=False,
        )
        verdicts = [results[judge] for judge in JUDGE_ORDER]
        if is_degenerate_panel(verdicts):
            raise ValueError(
                "Revised panel remained degenerate after retry; refusing suspicious uniform scores"
            )

    return RoastPanel(verdicts=verdicts)


def roast_panel_from_state_verdicts(verdicts: list[dict]) -> RoastPanel:
    return RoastPanel(verdicts=[Verdict.model_validate(v) for v in verdicts])


def appeal_baseline_panel(roast_panel: RoastPanel, debate_result: dict | None) -> RoastPanel:
    """Panel judges re-evaluate against after debate re-vote, when present."""
    if debate_result and debate_result.get("revised_verdicts"):
        return roast_panel_from_state_verdicts(debate_result["revised_verdicts"])
    return roast_panel
