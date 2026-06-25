"""Run lifecycle routes."""

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.deps import (
    RunRegistry,
    build_idea_preview,
    build_model_for_run,
    build_research_context_for_run,
    build_startup_idea_context,
    get_app_settings,
    get_run_registry,
)
from api.events import run_failed_envelope, stream_connected_envelope, to_api_envelope
from api.schemas import CreateRunRequest, RunCreatedResponse, RunStatusResponse
from config import Settings
from pipeline import stream_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(tags=["runs"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _format_sse(envelope) -> str:
    return f"data: {json.dumps(envelope.model_dump(mode='json'))}\n\n"


@router.post("/runs", response_model=RunCreatedResponse)
def create_run(
    request: CreateRunRequest,
    registry: Annotated[RunRegistry, Depends(get_run_registry)],
) -> RunCreatedResponse:
    record = registry.create(request)
    return RunCreatedResponse(run_id=record.run_id)


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
def get_run_status(
    run_id: str,
    registry: Annotated[RunRegistry, Depends(get_run_registry)],
) -> RunStatusResponse:
    record = registry.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunStatusResponse(
        run_id=record.run_id,
        status=record.status,
        idea_preview=build_idea_preview(record.request.idea),
        created_at=record.created_at,
    )


@router.get("/runs/{run_id}/events")
def stream_run_events(
    run_id: str,
    registry: Annotated[RunRegistry, Depends(get_run_registry)],
    settings: Annotated[Settings, Depends(get_app_settings)],
):
    record = registry.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if not registry.try_claim(run_id):
        current = registry.get(run_id)
        status = current.status if current is not None else "unknown"
        raise HTTPException(status_code=409, detail=f"Run is already {status}")

    def generate():
        sequence = 0
        yield _format_sse(stream_connected_envelope(run_id=run_id, sequence=sequence))
        sequence += 1
        try:
            startup_idea = build_startup_idea_context(record.request)
            model = build_model_for_run(record.request, settings)
            research_context = build_research_context_for_run(
                record.request,
                startup_idea,
                settings,
                model,
            )
            for event in stream_pipeline(
                model,
                startup_idea,
                max_debate_rounds=record.request.max_debate_rounds,
                research_context=research_context,
            ):
                envelope = to_api_envelope(event, run_id=run_id, sequence=sequence)
                sequence += 1
                yield _format_sse(envelope)
            registry.mark_completed(run_id)
        except Exception:
            logger.exception("Run %s failed during streaming", run_id)
            registry.mark_failed(run_id)
            envelope = run_failed_envelope(
                run_id=run_id,
                sequence=sequence,
                message="The roast run failed. Please try again.",
            )
            yield _format_sse(envelope)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
