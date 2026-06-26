"""Run engine decoupled from the HTTP connection.

A ``RunManager`` drives ``stream_pipeline`` to completion exactly once per run,
buffering every event in an append-only log. HTTP clients are pure subscribers:
they replay the buffer and then await new events. This means a browser can
disconnect and reconnect, or several tabs can watch the same run, without the
run dying or a second viewer getting rejected.
"""

import asyncio
from collections.abc import AsyncIterator
import logging
from uuid import uuid4

from api.deps import (
    RunRecord,
    build_model_for_run,
    build_research_context_for_run,
    build_startup_idea_context,
)
from api.events import run_failed_envelope, stream_connected_envelope, to_api_envelope
from api.schemas import ApiEventEnvelope, CreateRunRequest
from config import Settings
from pipeline import stream_pipeline

logger = logging.getLogger(__name__)


class _RunState:
    """Per-run buffer, lifecycle, and subscriber wake-ups (event-loop owned)."""

    def __init__(self, record: RunRecord) -> None:
        self.record = record
        self.events: list[ApiEventEnvelope] = []
        self.done = False
        self.task: asyncio.Task | None = None
        self._subscribers: set[asyncio.Event] = set()

    def append(self, envelope: ApiEventEnvelope) -> None:
        envelope.sequence = len(self.events)
        self.events.append(envelope)
        for wakeup in self._subscribers:
            wakeup.set()

    def finish(self) -> None:
        self.done = True
        for wakeup in self._subscribers:
            wakeup.set()

    def add_subscriber(self, wakeup: asyncio.Event) -> None:
        self._subscribers.add(wakeup)

    def remove_subscriber(self, wakeup: asyncio.Event) -> None:
        self._subscribers.discard(wakeup)


class RunManager:
    # ponytail: in-memory, per-process, no eviction — fine for a single uvicorn
    # process. Multi-worker / restart-survival is Phase 3 (SQLite event log).
    def __init__(self) -> None:
        self._runs: dict[str, _RunState] = {}

    def create(self, request: CreateRunRequest) -> RunRecord:
        run_id = str(uuid4())
        self._runs[run_id] = _RunState(RunRecord(run_id=run_id, request=request))
        return self._runs[run_id].record

    def get(self, run_id: str) -> RunRecord | None:
        state = self._runs.get(run_id)
        return state.record if state is not None else None

    def ensure_started(self, run_id: str, settings: Settings) -> None:
        """Start the run's background task once. Idempotent."""
        state = self._runs[run_id]
        if state.task is not None:
            return
        state.record.status = "running"
        state.append(stream_connected_envelope(run_id=run_id))
        state.task = asyncio.create_task(self._drive(run_id, settings))

    async def subscribe(
        self, run_id: str, *, after_sequence: int = -1
    ) -> AsyncIterator[ApiEventEnvelope]:
        """Replay buffered events after ``after_sequence``, then stream live."""
        state = self._runs[run_id]
        wakeup = asyncio.Event()
        state.add_subscriber(wakeup)
        try:
            cursor = max(0, after_sequence + 1)
            while True:
                while cursor < len(state.events):
                    yield state.events[cursor]
                    cursor += 1
                if state.done:
                    return
                await wakeup.wait()
                wakeup.clear()
        finally:
            state.remove_subscriber(wakeup)

    async def _drive(self, run_id: str, settings: Settings) -> None:
        state = self._runs[run_id]
        loop = asyncio.get_running_loop()
        record = state.record

        def emit(envelope: ApiEventEnvelope) -> None:
            loop.call_soon_threadsafe(state.append, envelope)

        def work() -> None:
            startup_idea = build_startup_idea_context(record.request)
            model = build_model_for_run(record.request, settings)
            research_context = build_research_context_for_run(
                record.request, startup_idea, settings, model
            )
            for event in stream_pipeline(
                model,
                startup_idea,
                max_debate_rounds=record.request.max_debate_rounds,
                research_context=research_context,
            ):
                emit(to_api_envelope(event, run_id=run_id, sequence=0))

        try:
            await asyncio.to_thread(work)
            record.status = "completed"
        except Exception:
            logger.exception("Run %s failed", run_id)
            record.status = "failed"
            state.append(
                run_failed_envelope(
                    run_id=run_id,
                    sequence=0,
                    message="The roast run failed. Please try again.",
                )
            )
        finally:
            state.finish()


# ponytail: module singleton — Phase 3 swaps this for a SQLite-backed store so
# multiple workers / a server restart can share run state.
_manager = RunManager()


def get_run_manager() -> RunManager:
    return _manager
