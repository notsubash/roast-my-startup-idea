"""Deterministic two-phase pipeline — the production execution path.

Phase 1: parallel structured judge calls (ThreadPoolExecutor)
Phase 2: LangGraph debate graph (fixed turn order)

DeepAgents orchestrator is NOT used here. Local models often fail to
reliably dispatch all five judge subagents via task(); debate routing
must be deterministic, not LLM-planned.
"""

from collections.abc import Iterator

from debate.service import run_debate, stream_debate
from events import (
    DebateCompleted,
    PhaseStarted,
    PipelineCompleted,
    PipelineEvent,
    RoastPanelCompleted,
)
from judges.panel import run_roast_panel, stream_roast_panel
from judges.schemas import RoastPanel
from memory.context import build_memory_context
from memory.models import IdeaRecord
from memory.store import IdeaStore
from orchestrator.deep_agent import run_roast_via_orchestrator


def stream_pipeline(
    model,
    startup_idea: str,
    max_debate_rounds: int = 3,
    user_id: str | None = None,
    idea_store: IdeaStore | None = None,
    memory_limit: int = 3,
    research_context: str | None = None,
) -> Iterator[PipelineEvent]:
    """Run roast panel then debate, yielding all intermediate events."""
    memory_context = ""
    if user_id and idea_store:
        memory_context = build_memory_context(
            idea_store.list_recent(user_id, limit=memory_limit)
        )

    yield PhaseStarted(phase="roast")

    roast_panel: RoastPanel | None = None
    for event in stream_roast_panel(
        model,
        startup_idea,
        memory_context,
        research_context,
    ):
        yield event
        if isinstance(event, RoastPanelCompleted):
            roast_panel = event.panel

    if roast_panel is None:
        raise RuntimeError("Roast panel did not complete")

    yield PhaseStarted(phase="debate")

    debate_result: dict | None = None
    for event in stream_debate(model, startup_idea, roast_panel, max_debate_rounds):
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

    yield PipelineCompleted(roast_panel=roast_panel, debate_result=debate_result)


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
    memory_context = ""
    if user_id and idea_store:
        memory_context = build_memory_context(
            idea_store.list_recent(user_id, limit=memory_limit)
        )

    roast_panel = run_roast_panel(model, startup_idea, memory_context, research_context)
    debate_result = run_debate(model, startup_idea, roast_panel, max_debate_rounds)
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


def run_deepagent_pipeline(
    model,
    startup_idea: str,
    max_debate_rounds: int = 3,
    research_context: str | None = None,
    web_search_enabled: bool = False,
) -> tuple[RoastPanel, dict]:
    """Experimental flow: DeepAgents for roast phase + deterministic debate."""
    roast_panel = run_roast_via_orchestrator(
        model=model,
        startup_idea=startup_idea,
        research_context=research_context,
        web_search_enabled=web_search_enabled,
    )
    debate_result = run_debate(model, startup_idea, roast_panel, max_debate_rounds)
    return roast_panel, debate_result
