"""Phase 1: parallel judge panel with event streaming."""

from collections.abc import Callable, Iterator
import concurrent.futures

from config import JUDGE_ORDER
from events import JudgesDispatched, JudgeVerdictCompleted, RoastPanelCompleted
from judges.guardrails import is_degenerate_panel
from judges.schemas import RoastPanel, Verdict
from judges.service import DEGENERATE_PANEL_RETRY_SUFFIX, invoke_judge
from observability import build_run_config, idea_fingerprint, traceable
from observability.metrics import RunMetricsCollector
from run_control import check_abort


def _run_judge_panel(
    model,
    startup_idea: str,
    memory_context: str | None,
    research_context: str | None,
    run_config: dict,
    *,
    system_suffix: str | None = None,
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
                system_suffix=system_suffix,
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
    if is_degenerate_panel(verdicts):
        # ponytail: one retry with an anti-collusion suffix; fail closed if still uniform.
        if metrics is not None:
            metrics.discard_phase("roast")
        results = _run_judge_panel(
            model,
            startup_idea,
            memory_context,
            research_context,
            resolved_config,
            system_suffix=DEGENERATE_PANEL_RETRY_SUFFIX,
            metrics=metrics,
            abort_check=abort_check,
        )
        check_abort(abort_check)
        verdicts = [results[judge] for judge in JUDGE_ORDER]
        if is_degenerate_panel(verdicts):
            raise ValueError(
                "Roast panel remained degenerate after retry; refusing suspicious uniform scores"
            )

    for completed, judge in enumerate(JUDGE_ORDER, start=1):
        yield JudgeVerdictCompleted(
            judge=judge,
            verdict=results[judge],
            completed=completed,
            total=total,
        )

    panel = RoastPanel(verdicts=verdicts)
    yield RoastPanelCompleted(panel=panel)


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
