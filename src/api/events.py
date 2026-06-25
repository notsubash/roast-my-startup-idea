"""Convert internal pipeline events into frontend-safe SSE envelopes."""

from datetime import UTC, datetime
from typing import Any

from api.schemas import ApiEventEnvelope
from events import (
    DebateCompleted,
    DebateMessagePublished,
    DebateRoundStarted,
    DebateSpeakerThinking,
    DebateSynthesisPublished,
    JudgesDispatched,
    JudgeVerdictCompleted,
    PhaseStarted,
    PipelineCompleted,
    PipelineEvent,
    RoastPanelCompleted,
)


def _camel_to_snake(name: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index > 0:
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars)


def pipeline_event_type(event: PipelineEvent) -> str:
    if isinstance(event, PipelineCompleted):
        return "run_completed"
    return _camel_to_snake(type(event).__name__)


def pipeline_event_payload(event: PipelineEvent) -> dict[str, Any]:
    if isinstance(event, PhaseStarted):
        return {"phase": event.phase}
    if isinstance(event, JudgesDispatched):
        return {"total": event.total}
    if isinstance(event, JudgeVerdictCompleted):
        return {
            "judge": event.judge,
            "verdict": event.verdict.model_dump(mode="json"),
            "completed": event.completed,
            "total": event.total,
        }
    if isinstance(event, RoastPanelCompleted):
        return {"panel": event.panel.model_dump(mode="json")}
    if isinstance(event, DebateRoundStarted):
        return {"round": event.round}
    if isinstance(event, DebateSpeakerThinking):
        return {"judge": event.judge, "round": event.round}
    if isinstance(event, DebateMessagePublished):
        return {
            "speaker": event.speaker,
            "round": event.round,
            "content": event.content,
        }
    if isinstance(event, DebateSynthesisPublished):
        return {"content": event.content}
    if isinstance(event, DebateCompleted):
        return {
            "debate_messages": event.debate_messages,
            "final_synthesis": event.final_synthesis,
        }
    if isinstance(event, PipelineCompleted):
        return {
            "roast_panel": event.roast_panel.model_dump(mode="json"),
            "debate_result": event.debate_result,
        }
    raise TypeError(f"Unsupported pipeline event: {type(event)!r}")


def to_api_envelope(
    event: PipelineEvent,
    *,
    run_id: str,
    sequence: int,
    created_at: datetime | None = None,
) -> ApiEventEnvelope:
    return ApiEventEnvelope(
        type=pipeline_event_type(event),
        run_id=run_id,
        sequence=sequence,
        payload=pipeline_event_payload(event),
        created_at=created_at or datetime.now(UTC),
    )


def run_failed_envelope(
    *,
    run_id: str,
    sequence: int,
    message: str,
    recoverable: bool = True,
    created_at: datetime | None = None,
) -> ApiEventEnvelope:
    return ApiEventEnvelope(
        type="run_failed",
        run_id=run_id,
        sequence=sequence,
        payload={"message": message, "recoverable": recoverable},
        created_at=created_at or datetime.now(UTC),
    )


def stream_connected_envelope(
    *,
    run_id: str,
    sequence: int = 0,
    created_at: datetime | None = None,
) -> ApiEventEnvelope:
    return ApiEventEnvelope(
        type="stream_connected",
        run_id=run_id,
        sequence=sequence,
        payload={"status": "connected"},
        created_at=created_at or datetime.now(UTC),
    )
