"""Phase 2: LangGraph debate — deterministic turn order, event streaming."""

from collections.abc import Callable, Iterator
from typing import Any

from langchain_core.messages import HumanMessage

from config import JUDGE_ORDER, get_settings
from debate.graph import build_debate_graph
from events import (
    DebateCompleted,
    DebateMessagePublished,
    DebateRoundStarted,
    DebateSpeakerThinking,
    DebateSynthesisPublished,
    DebateTokenDelta,
    RevoteJudgeCompleted,
    RevoteStarted,
)
from judges.schemas import RoastPanel, Verdict
from observability import build_run_config, idea_fingerprint, optional_config_kwargs, traceable
from observability.metrics import RunMetricsCollector
from run_control import check_abort


def _initial_state(startup_idea: str, roast_panel: RoastPanel, max_rounds: int) -> dict:
    verdicts = [v.model_dump() for v in roast_panel.verdicts]
    return {
        "messages": [HumanMessage(content="Begin the debate.")],
        "startup_idea": startup_idea,
        "verdicts": verdicts,
        "initial_verdicts": verdicts,
        "debate_messages": [],
        "round": 1,
        "max_rounds": max_rounds,
        "current_speaker_idx": 0,
        "final_synthesis": None,
        "structured_synthesis": None,
    }


def stream_debate(
    model,
    startup_idea: str,
    roast_panel: RoastPanel,
    max_rounds: int = 3,
    run_config: dict | None = None,
    metrics: RunMetricsCollector | None = None,
    abort_check: Callable[[], str | None] | None = None,
) -> Iterator[
    DebateRoundStarted
    | DebateSpeakerThinking
    | DebateTokenDelta
    | DebateMessagePublished
    | DebateSynthesisPublished
    | RevoteStarted
    | RevoteJudgeCompleted
    | DebateCompleted
]:
    """Stream debate graph node updates as frontend-agnostic events."""
    enable_revote = get_settings().enable_revote
    debate_graph = build_debate_graph(
        model,
        metrics=metrics,
        abort_check=abort_check,
        enable_revote=enable_revote,
    )
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
    structured_synthesis: dict | None = None
    revised_verdicts: list[dict] | None = None

    for stream_item in debate_graph.stream(
        initial_state,
        stream_mode=["custom", "updates"],
        **optional_config_kwargs(resolved_config),
    ):
        check_abort(abort_check)
        mode, payload = stream_item

        if mode == "custom":
            custom_type = payload.get("type")
            if custom_type == "debate_token":
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
            if custom_type == "revote_started":
                yield RevoteStarted(total=payload["total"])
                continue
            if custom_type == "revote_judge":
                yield RevoteJudgeCompleted(
                    judge=payload["judge"],
                    verdict=Verdict.model_validate(payload["verdict"]),
                    original_score=payload["original_score"],
                    completed=payload["completed"],
                    total=payload["total"],
                )
                continue
            continue

        state_update = payload
        for node_name, node_output in state_update.items():
            if node_name in ("__start__", "advance_round"):
                continue

            if node_name == "revote":
                revised = node_output.get("verdicts")
                if revised is not None:
                    revised_verdicts = revised

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
                structured = node_output.get("structured_synthesis")
                if structured is not None:
                    structured_synthesis = structured
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
        structured_synthesis=structured_synthesis,
        initial_verdicts=initial_state["initial_verdicts"],
        revised_verdicts=revised_verdicts,
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
                "structured_synthesis": event.structured_synthesis,
                "initial_verdicts": event.initial_verdicts,
                "revised_verdicts": event.revised_verdicts,
            }
    return result
