"""Deterministic two-phase pipeline — the production execution path.

Phase 1: parallel structured judge calls (ThreadPoolExecutor)
Phase 2: LangGraph debate graph (fixed turn order)

DeepAgents orchestrator is NOT used here. Local models often fail to
reliably dispatch all five judge subagents via task(); debate routing
must be deterministic, not LLM-planned.
"""

from collections.abc import Callable, Iterator

from debate.service import run_debate, stream_debate
from events import (
    DebateCompleted,
    PhaseStarted,
    PipelineCompleted,
    PipelineEvent,
    RoastPanelCompleted,
    RunMetrics,
)
from judges.panel import run_roast_panel, stream_roast_panel
from judges.schemas import RoastPanel
from memory.context import build_memory_context
from memory.models import IdeaRecord
from memory.retrieval import records_for_memory
from memory.store import IdeaStore
from observability import build_run_config, idea_fingerprint, traceable
from observability.metrics import ModelRuntime, PhaseTimer, RunMetricsCollector
from orchestrator.deep_agent import run_roast_via_orchestrator
from run_control import check_abort
from version import get_version


def _pipeline_metadata(
    *,
    startup_idea: str,
    max_debate_rounds: int,
    execution_flow: str = "deterministic",
) -> dict:
    return {
        "app_version": get_version(),
        "execution_flow": execution_flow,
        "idea_fingerprint": idea_fingerprint(startup_idea),
        "max_debate_rounds": max_debate_rounds,
    }


def _pipeline_run_config(
    run_name: str,
    *,
    startup_idea: str,
    max_debate_rounds: int,
    execution_flow: str = "deterministic",
) -> dict:
    return build_run_config(
        run_name,
        tags=[f"flow:{execution_flow}"],
        metadata=_pipeline_metadata(
            startup_idea=startup_idea,
            max_debate_rounds=max_debate_rounds,
            execution_flow=execution_flow,
        ),
    )


def stream_pipeline(
    model,
    startup_idea: str,
    max_debate_rounds: int = 3,
    user_id: str | None = None,
    idea_store: IdeaStore | None = None,
    memory_limit: int = 3,
    memory_context: str | None = None,
    research_context: str | None = None,
    run_config: dict | None = None,
    model_runtime: ModelRuntime = "local",
    abort_check: Callable[[], str | None] | None = None,
) -> Iterator[PipelineEvent]:
    """Run roast panel then debate, yielding all intermediate events."""
    resolved_memory_context = memory_context or ""
    if not resolved_memory_context and user_id and idea_store:
        resolved_memory_context = build_memory_context(
            records_for_memory(idea_store, user_id, startup_idea, limit=memory_limit)
        )

    resolved_config = run_config or _pipeline_run_config(
        "roast-pipeline",
        startup_idea=startup_idea,
        max_debate_rounds=max_debate_rounds,
    )

    metrics = RunMetricsCollector(model_runtime=model_runtime)
    timer = PhaseTimer()
    in_debate = False

    check_abort(abort_check)
    yield PhaseStarted(phase="roast")

    roast_panel: RoastPanel | None = None
    for event in stream_roast_panel(
        model,
        startup_idea,
        resolved_memory_context,
        research_context,
        run_config=resolved_config,
        metrics=metrics,
        abort_check=abort_check,
    ):
        yield event
        check_abort(abort_check)
        if isinstance(event, RoastPanelCompleted):
            roast_panel = event.panel

    if roast_panel is None:
        raise RuntimeError("Roast panel did not complete")

    check_abort(abort_check)
    timer.start_debate()
    in_debate = True
    yield PhaseStarted(phase="debate")

    debate_result: dict | None = None
    for event in stream_debate(
        model,
        startup_idea,
        roast_panel,
        max_debate_rounds,
        run_config=resolved_config,
        metrics=metrics,
        abort_check=abort_check,
    ):
        yield event
        if isinstance(event, DebateCompleted):
            debate_result = {
                "debate_messages": event.debate_messages,
                "final_synthesis": event.final_synthesis,
            }

    if debate_result is None:
        raise RuntimeError("Debate did not complete")

    if user_id and idea_store:
        idea_store.save(
            IdeaRecord(
                user_id=user_id,
                idea_text=startup_idea,
                roast_panel=roast_panel,
                debate_result=debate_result,
            )
        )

    roast_seconds, debate_seconds, total_seconds = timer.finish(in_debate=in_debate)
    metrics_payload = metrics.snapshot(
        roast_seconds=roast_seconds,
        debate_seconds=debate_seconds,
        total_seconds=total_seconds,
    )
    check_abort(abort_check)
    yield RunMetrics(**metrics_payload)
    yield PipelineCompleted(roast_panel=roast_panel, debate_result=debate_result)


@traceable(name="run_pipeline", run_type="chain", tags=["flow:deterministic"])
def run_pipeline(
    model,
    startup_idea: str,
    max_debate_rounds: int = 3,
    user_id: str | None = None,
    idea_store: IdeaStore | None = None,
    memory_limit: int = 3,
    research_context: str | None = None,
) -> tuple[RoastPanel, dict]:
    """Blocking convenience wrapper for CLI and tests."""
    run_config = _pipeline_run_config(
        "roast-pipeline",
        startup_idea=startup_idea,
        max_debate_rounds=max_debate_rounds,
    )
    memory_context = ""
    if user_id and idea_store:
        memory_context = build_memory_context(
            records_for_memory(idea_store, user_id, startup_idea, limit=memory_limit)
        )

    roast_panel = run_roast_panel(
        model,
        startup_idea,
        memory_context,
        research_context,
        run_config=run_config,
    )
    debate_result = run_debate(
        model,
        startup_idea,
        roast_panel,
        max_debate_rounds,
        run_config=run_config,
    )
    if user_id and idea_store:
        idea_store.save(
            IdeaRecord(
                user_id=user_id,
                idea_text=startup_idea,
                roast_panel=roast_panel,
                debate_result=debate_result,
            )
        )
    return roast_panel, debate_result


@traceable(name="run_deepagent_pipeline", run_type="chain", tags=["flow:deepagents"])
def run_deepagent_pipeline(
    model,
    startup_idea: str,
    max_debate_rounds: int = 3,
    research_context: str | None = None,
    web_search_enabled: bool = False,
) -> tuple[RoastPanel, dict]:
    """Experimental flow: DeepAgents for roast phase + deterministic debate."""
    run_config = _pipeline_run_config(
        "deepagent-pipeline",
        startup_idea=startup_idea,
        max_debate_rounds=max_debate_rounds,
        execution_flow="deepagents",
    )
    roast_panel = run_roast_via_orchestrator(
        model=model,
        startup_idea=startup_idea,
        research_context=research_context,
        web_search_enabled=web_search_enabled,
        run_config=run_config,
    )
    debate_result = run_debate(
        model,
        startup_idea,
        roast_panel,
        max_debate_rounds,
        run_config=run_config,
    )
    return roast_panel, debate_result
