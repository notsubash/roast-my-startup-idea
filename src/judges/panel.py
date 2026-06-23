"""Phase 1: parallel judge panel with event streaming."""

import concurrent.futures
from collections.abc import Iterator

from config import JUDGE_ORDER
from events import JudgeVerdictCompleted, JudgesDispatched, RoastPanelCompleted
from judges.schemas import RoastPanel, Verdict
from judges.service import invoke_judge


def stream_roast_panel(
    model,
    startup_idea: str,
    memory_context: str | None = None,
    research_context: str | None = None,
) -> Iterator[JudgeVerdictCompleted | JudgesDispatched | RoastPanelCompleted]:
    """Run all judges in parallel; yield events as each completes."""
    total = len(JUDGE_ORDER)
    yield JudgesDispatched(total=total)

    with concurrent.futures.ThreadPoolExecutor(max_workers=total) as pool:
        future_to_judge = {
            pool.submit(
                invoke_judge,
                model,
                judge,
                startup_idea,
                memory_context,
                research_context,
            ): judge
            for judge in JUDGE_ORDER
        }

        results: dict[str, Verdict] = {}
        completed = 0
        for future in concurrent.futures.as_completed(future_to_judge):
            judge = future_to_judge[future]
            verdict = future.result()
            results[judge] = verdict
            completed += 1
            yield JudgeVerdictCompleted(
                judge=judge,
                verdict=verdict,
                completed=completed,
                total=total,
            )

    verdicts = [results[judge] for judge in JUDGE_ORDER]
    panel = RoastPanel(verdicts=verdicts)
    yield RoastPanelCompleted(panel=panel)


def run_roast_panel(
    model,
    startup_idea: str,
    memory_context: str | None = None,
    research_context: str | None = None,
) -> RoastPanel:
    """Blocking convenience wrapper — returns the final panel."""
    panel = None
    for event in stream_roast_panel(model, startup_idea, memory_context, research_context):
        if isinstance(event, RoastPanelCompleted):
            panel = event.panel
    assert panel is not None
    return panel
