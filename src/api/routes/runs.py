"""Run lifecycle routes."""

import asyncio
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.deps import build_idea_preview, get_app_settings
from api.run_manager import RunManager, get_run_manager
from api.schemas import ApiEventEnvelope, CreateRunRequest, RunCreatedResponse, RunStatusResponse
from config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["runs"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

SSE_HEARTBEAT_FRAME = ": keep-alive\n\n"


def _parse_last_event_id(request: Request) -> int:
    raw = request.headers.get("Last-Event-ID")
    if not raw:
        return -1
    try:
        value = int(raw.strip())
    except ValueError:
        logger.debug("Invalid Last-Event-ID %r, replaying from start", raw)
        return -1
    if value < 0:
        logger.debug("Negative Last-Event-ID %r, replaying from start", raw)
        return -1
    return value


def _format_sse(envelope: ApiEventEnvelope) -> str:
    payload = json.dumps(envelope.model_dump(mode="json"))
    return f"id: {envelope.sequence}\ndata: {payload}\n\n"


@router.post("/runs", response_model=RunCreatedResponse)
def create_run(
    request: CreateRunRequest,
    manager: Annotated[RunManager, Depends(get_run_manager)],
) -> RunCreatedResponse:
    record = manager.create(request)
    return RunCreatedResponse(run_id=record.run_id)


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
def get_run_status(
    run_id: str,
    manager: Annotated[RunManager, Depends(get_run_manager)],
) -> RunStatusResponse:
    record = manager.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunStatusResponse(
        run_id=record.run_id,
        status=record.status,
        idea_preview=build_idea_preview(record.request.idea),
        created_at=record.created_at,
    )


@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: str,
    request: Request,
    manager: Annotated[RunManager, Depends(get_run_manager)],
    settings: Annotated[Settings, Depends(get_app_settings)],
):
    if manager.get(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")

    # Subscriber model: the engine runs once into a buffer; every connection
    # (including reconnects and extra tabs) just replays + tails that buffer.
    manager.ensure_started(run_id, settings)
    after_sequence = _parse_last_event_id(request)

    async def generate():
        stream = manager.subscribe(run_id, after_sequence=after_sequence)
        iterator = stream.__aiter__()
        while True:
            try:
                envelope = await asyncio.wait_for(
                    iterator.__anext__(), timeout=settings.sse_heartbeat_seconds
                )
                yield _format_sse(envelope)
            except TimeoutError:
                yield SSE_HEARTBEAT_FRAME
            except StopAsyncIteration:
                return

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
