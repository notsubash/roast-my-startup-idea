"""Phase 1: parallel judge panel with event streaming."""

from collections.abc import Callable, Iterator
import concurrent.futures
import logging

from config import JUDGE_ORDER
from events import JudgesDispatched, JudgeVerdictCompleted, RoastPanelCompleted
from judges.guardrails import is_degenerate_panel
from judges.schemas import RoastPanel, Verdict
from judges.service import (
    DEGENERATE_PANEL_RETRY_SUFFIX,
    LENS_OVERLAP_RETRY_SUFFIX,
    invoke_judge,
)
from observability import build_run_config, idea_fingerprint, traceable
from observability.metrics import RunMetricsCollector
from run_control import check_abort
from verification import JUDGE_ROLE_NAMES, assess_lens_uniqueness

logger = logging.getLogger(__name__)

# ponytail: weak local models often herd; two retries before surfacing a warning.
MAX_PANEL_RETRIES = 2


def _panel_retry_suffixes(verdicts: list[Verdict]) -> list[str]:
    suffixes: list[str] = []
    if is_degenerate_panel(verdicts):
        suffixes.append(DEGENERATE_PANEL_RETRY_SUFFIX)
    if not assess_lens_uniqueness(verdicts).get("lens_uniqueness_passed", True):
        suffixes.append(LENS_OVERLAP_RETRY_SUFFIX)
    return suffixes


def _judge_retry_suffix(
    judge: str,
    *,
    base_suffixes: list[str],
    uniform_score: int | None,
    uniform_verdict: str | None,
) -> str:
    parts = list(base_suffixes)
    if uniform_score is not None and uniform_verdict is not None:
        parts.append(
            f"As {JUDGE_ROLE_NAMES[judge]}, score from your rubric only. The prior panel was "
            f"uniformly {uniform_verdict}/{uniform_score}; your score should reflect "
            f"{judge}-specific criteria and usually differ from other judges."
        )
    return "\n\n".join(parts)


def _run_judge_panel(
    model,
    startup_idea: str,
    memory_context: str | None,
    research_context: str | None,
    run_config: dict,
    *,
    system_suffix: str | None = None,
    judge_suffix: Callable[[str], str | None] | None = None,
    metrics: RunMetricsCollector | None = None,
    abort_check: Callable[[], str | None] | None = None,
) -> dict[str, Verdict]:
    total = len(JUDGE_ORDER)
    with concurrent.futures.ThreadPoolExecutor(max_workers=total) as pool:
        future_to_judge = {
            pool.submit(
                invoke_judge,
                model,
                judge,
                startup_idea,
                memory_context,
                research_context,
                run_config,
                system_suffix=judge_suffix(judge) if judge_suffix else system_suffix,
                metrics=metrics,
            ): judge
            for judge in JUDGE_ORDER
        }

        results: dict[str, Verdict] = {}
        for future in concurrent.futures.as_completed(future_to_judge):
            # ponytail: in-flight judge calls still finish; abort stops before the next wait.
            check_abort(abort_check)
            judge = future_to_judge[future]
            results[judge] = future.result()
    return results


def stream_roast_panel(
    model,
    startup_idea: str,
    memory_context: str | None = None,
    research_context: str | None = None,
    run_config: dict | None = None,
    metrics: RunMetricsCollector | None = None,
    abort_check: Callable[[], str | None] | None = None,
) -> Iterator[JudgeVerdictCompleted | JudgesDispatched | RoastPanelCompleted]:
    """Run all judges in parallel; yield verdict events after the panel completes."""
    check_abort(abort_check)
    total = len(JUDGE_ORDER)
    yield JudgesDispatched(total=total)
    resolved_config = run_config or build_run_config(
        "roast-panel",
        tags=["phase:roast"],
        metadata={"idea_fingerprint": idea_fingerprint(startup_idea)},
    )

    results = _run_judge_panel(
        model,
        startup_idea,
        memory_context,
        research_context,
        resolved_config,
        metrics=metrics,
        abort_check=abort_check,
    )
    check_abort(abort_check)
    verdicts = [results[judge] for judge in JUDGE_ORDER]

    for _ in range(MAX_PANEL_RETRIES):
        retry_suffixes = _panel_retry_suffixes(verdicts)
        if not retry_suffixes:
            break
        if metrics is not None:
            metrics.discard_phase("roast")
        degenerate = is_degenerate_panel(verdicts)
        uniform_score = verdicts[0].score if degenerate else None
        uniform_verdict = verdicts[0].verdict.value if degenerate else None
        suffix_factory = (
            (
                lambda judge, suffixes=retry_suffixes, score=uniform_score, verdict=uniform_verdict: (
                    _judge_retry_suffix(
                        judge,
                        base_suffixes=suffixes,
                        uniform_score=score,
                        uniform_verdict=verdict,
                    )
                )
            )
            if degenerate
            else None
        )
        results = _run_judge_panel(
            model,
            startup_idea,
            memory_context,
            research_context,
            resolved_config,
            system_suffix="\n\n".join(retry_suffixes) if not degenerate else None,
            judge_suffix=suffix_factory,
            metrics=metrics,
            abort_check=abort_check,
        )
        check_abort(abort_check)
        verdicts = [results[judge] for judge in JUDGE_ORDER]

    roast_degenerate_panel = is_degenerate_panel(verdicts)
    if roast_degenerate_panel:
        logger.warning(
            "Roast panel remained degenerate after %d retries; continuing with low-confidence flag",
            MAX_PANEL_RETRIES,
        )

    lens_quality = assess_lens_uniqueness(verdicts)
    # ponytail: uniform scores already flag low confidence; don't also kill the run on overlap.
    if (
        not roast_degenerate_panel
        and not lens_quality.get("lens_legacy", True)
        and not lens_quality.get("lens_uniqueness_passed", True)
    ):
        raise ValueError(
            "Roast panel remained overlapping after retry; refusing indistinct lens outputs"
        )

    for completed, judge in enumerate(JUDGE_ORDER, start=1):
        yield JudgeVerdictCompleted(
            judge=judge,
            verdict=results[judge],
            completed=completed,
            total=total,
        )

    panel = RoastPanel(verdicts=verdicts)
    yield RoastPanelCompleted(panel=panel, degenerate_panel=roast_degenerate_panel)


@traceable(name="run_roast_panel", run_type="chain", tags=["phase:roast"])
def run_roast_panel(
    model,
    startup_idea: str,
    memory_context: str | None = None,
    research_context: str | None = None,
    run_config: dict | None = None,
) -> RoastPanel:
    """Blocking convenience wrapper — returns the final panel."""
    panel = None
    for event in stream_roast_panel(
        model,
        startup_idea,
        memory_context,
        research_context,
        run_config=run_config,
    ):
        if isinstance(event, RoastPanelCompleted):
            panel = event.panel
    assert panel is not None
    return panel
