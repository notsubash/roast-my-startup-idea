"""Phase 2: LangGraph debate — deterministic turn order, event streaming."""

from collections.abc import Iterator
from typing import Any

from langchain_core.messages import HumanMessage

from config import JUDGE_ORDER
from debate.graph import build_debate_graph
from events import (
    DebateCompleted,
    DebateMessagePublished,
    DebateRoundStarted,
    DebateSpeakerThinking,
    DebateSynthesisPublished,
    DebateTokenDelta,
)
from judges.schemas import RoastPanel
from observability import build_run_config, idea_fingerprint, optional_config_kwargs, traceable
from observability.metrics import RunMetricsCollector


def _initial_state(startup_idea: str, roast_panel: RoastPanel, max_rounds: int) -> dict:
    return {
        "messages": [HumanMessage(content="Begin the debate.")],
        "startup_idea": startup_idea,
        "verdicts": [v.model_dump() for v in roast_panel.verdicts],
        "debate_messages": [],
        "round": 1,
        "max_rounds": max_rounds,
        "current_speaker_idx": 0,
        "final_synthesis": None,
    }


def stream_debate(
    model,
    startup_idea: str,
    roast_panel: RoastPanel,
    max_rounds: int = 3,
    run_config: dict | None = None,
    metrics: RunMetricsCollector | None = None,
) -> Iterator[
    DebateRoundStarted
    | DebateSpeakerThinking
    | DebateTokenDelta
    | DebateMessagePublished
    | DebateSynthesisPublished
    | DebateCompleted
]:
    """Stream debate graph node updates as frontend-agnostic events."""
    debate_graph = build_debate_graph(model, metrics=metrics)
    initial_state = _initial_state(startup_idea, roast_panel, max_rounds)
    resolved_config = run_config or build_run_config(
        "debate-graph",
        tags=["phase:debate"],
        metadata={
            "idea_fingerprint": idea_fingerprint(startup_idea),
            "max_rounds": max_rounds,
            "judge_count": len(roast_panel.verdicts),
        },
    )

    current_round_displayed = 0
    all_debate_messages: list[dict] = []
    final_synthesis: str | None = None

    for stream_item in debate_graph.stream(
        initial_state,
        stream_mode=["custom", "updates"],
        **optional_config_kwargs(resolved_config),
    ):
        mode, payload = stream_item

        if mode == "custom":
            if payload.get("type") != "debate_token":
                continue
            token_round = payload["round"]
            if token_round != current_round_displayed:
                current_round_displayed = token_round
                yield DebateRoundStarted(round=current_round_displayed)
            yield DebateTokenDelta(
                speaker=payload["speaker"],
                round=token_round,
                delta=payload["delta"],
            )
            continue

        state_update = payload
        for node_name, node_output in state_update.items():
            if node_name in ("__start__", "advance_round"):
                continue

            new_messages = node_output.get("debate_messages", [])
            for msg in new_messages:
                all_debate_messages.append(msg)
                if msg["speaker"] == "moderator":
                    continue

                msg_round = msg["round"]
                if msg_round != current_round_displayed:
                    current_round_displayed = msg_round
                    yield DebateRoundStarted(round=current_round_displayed)

                yield DebateMessagePublished(
                    speaker=msg["speaker"],
                    round=msg["round"],
                    content=msg["content"],
                )

            synthesis = node_output.get("final_synthesis")
            if synthesis:
                final_synthesis = synthesis
                yield DebateSynthesisPublished(content=synthesis)
            else:
                next_idx = node_output.get("current_speaker_idx", 0)
                if next_idx < len(JUDGE_ORDER):
                    yield DebateSpeakerThinking(
                        judge=JUDGE_ORDER[next_idx],
                        round=current_round_displayed or 1,
                    )

    yield DebateCompleted(
        debate_messages=all_debate_messages,
        final_synthesis=final_synthesis,
    )


@traceable(name="run_debate", run_type="chain", tags=["phase:debate"])
def run_debate(
    model,
    startup_idea: str,
    roast_panel: RoastPanel,
    max_rounds: int = 3,
    run_config: dict | None = None,
) -> dict[str, Any]:
    """Blocking convenience wrapper — returns the final debate state dict."""
    result: dict[str, Any] = {}
    for event in stream_debate(
        model,
        startup_idea,
        roast_panel,
        max_rounds,
        run_config=run_config,
    ):
        if isinstance(event, DebateCompleted):
            result = {
                "debate_messages": event.debate_messages,
                "final_synthesis": event.final_synthesis,
            }
    return result
