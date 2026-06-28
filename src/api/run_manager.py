"""Run engine decoupled from the HTTP connection.

A ``RunManager`` drives ``stream_pipeline`` to completion exactly once per run,
buffering every event in a durable SQLite log. HTTP clients are pure subscribers:
they replay the log and then await new events. This means a browser can
disconnect and reconnect, or several tabs can watch the same run, without the
run dying or a second viewer getting rejected.
"""

import asyncio
from collections.abc import AsyncIterator
import logging
from pathlib import Path
from uuid import uuid4

from api.deps import (
    RunRecord,
    build_model_for_run,
    build_research_context_for_run,
    build_startup_idea_context,
)
from api.events import run_failed_envelope, stream_connected_envelope, to_api_envelope
from api.run_store import RunStore
from api.schemas import ApiEventEnvelope, CreateRunRequest
from config import Settings, get_settings
from events import RunMetrics
from observability.metrics import log_run_metrics
from pipeline import stream_pipeline

logger = logging.getLogger(__name__)


class _RunState:
    """Per-run lifecycle and subscriber wake-ups (event-loop owned)."""

    def __init__(
        self,
        record: RunRecord,
        *,
        store: RunStore,
        done: bool = False,
    ) -> None:
        self.record = record
        self._store = store
        self.done = done
        self.task: asyncio.Task | None = None
        self._subscribers: set[asyncio.Event] = set()

    def append(self, envelope: ApiEventEnvelope) -> ApiEventEnvelope:
        envelope = self._store.append_event(self.record.run_id, envelope)
        for wakeup in self._subscribers:
            wakeup.set()
        return envelope

    def finish(self) -> None:
        self.done = True
        for wakeup in self._subscribers:
            wakeup.set()

    def add_subscriber(self, wakeup: asyncio.Event) -> None:
        self._subscribers.add(wakeup)

    def remove_subscriber(self, wakeup: asyncio.Event) -> None:
        self._subscribers.discard(wakeup)


class RunManager:
    def __init__(
        self,
        db_path: Path | None = None,
        *,
        recover_on_init: bool = True,
        stale_minutes: int | None = None,
    ) -> None:
        self._store = RunStore(db_path)
        self._runs: dict[str, _RunState] = {}
        self._stale_minutes = (
            stale_minutes if stale_minutes is not None else get_settings().stale_run_minutes
        )
        if recover_on_init:
            self.recover_stale_runs()

    def recover_stale_runs(self) -> list[str]:
        recovered = self._store.recover_stale_runs(self._stale_minutes)
        for run_id in recovered:
            state = self._runs.get(run_id)
            if state is not None:
                state.record.status = "failed"
                state.finish()
        return recovered

    def close(self) -> None:
        self._store.close()

    def create(self, request: CreateRunRequest) -> RunRecord:
        run_id = str(uuid4())
        record = RunRecord(run_id=run_id, request=request)
        self._store.insert_run(record)
        self._runs[run_id] = _RunState(record, store=self._store)
        return record

    def get(self, run_id: str) -> RunRecord | None:
        state = self._runs.get(run_id)
        if state is not None:
            return state.record
        return self._store.get_run_record(run_id)

    def list_events(self, run_id: str) -> list[ApiEventEnvelope]:
        return self._store.list_events_after(run_id, -1)

    def _ensure_state(self, run_id: str) -> _RunState:
        state = self._runs.get(run_id)
        if state is not None:
            return state
        record = self._store.get_run_record(run_id)
        if record is None:
            raise KeyError(run_id)
        terminal = record.status in ("completed", "failed")
        state = _RunState(record, store=self._store, done=terminal)
        self._runs[run_id] = state
        return state

    def _fail_interrupted(self, state: _RunState) -> None:
        """Engine task was lost (restart); fail cleanly instead of re-driving."""
        if self._store.fail_run(state.record.run_id) is None:
            return
        state.record.status = "failed"
        state.finish()

    def ensure_started(self, run_id: str, settings: Settings) -> None:
        """Start the run's background task once. Idempotent."""
        state = self._ensure_state(run_id)
        if state.record.status in ("completed", "failed"):
            return
        if state.task is not None:
            return
        if state.record.status == "running":
            self._fail_interrupted(state)
            return
        if state.record.status == "created":
            state.record.status = "running"
            self._store.update_status(run_id, "running")
        state.append(stream_connected_envelope(run_id=run_id))
        state.task = asyncio.create_task(self._drive(run_id, settings))

    async def subscribe(
        self, run_id: str, *, after_sequence: int = -1
    ) -> AsyncIterator[ApiEventEnvelope]:
        """Replay persisted events after ``after_sequence``, then stream live."""
        state = self._ensure_state(run_id)
        wakeup = asyncio.Event()
        state.add_subscriber(wakeup)
        try:
            cursor = max(0, after_sequence + 1)
            while True:
                for envelope in self._store.list_events_after(run_id, cursor - 1):
                    yield envelope
                    cursor = envelope.sequence + 1
                if state.done:
                    # ponytail: fast-fail can append the terminal event after the query
                    # above; drain once more so run_failed is not dropped on CI.
                    for envelope in self._store.list_events_after(run_id, cursor - 1):
                        yield envelope
                        cursor = envelope.sequence + 1
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
                model_runtime=record.request.model_runtime,
            ):
                if isinstance(event, RunMetrics):
                    log_run_metrics(event.as_dict(), run_id=run_id)
                emit(to_api_envelope(event, run_id=run_id, sequence=0))

        try:
            await asyncio.to_thread(work)
            record.status = "completed"
            self._store.update_status(run_id, "completed")
        except Exception:
            logger.exception("Run %s failed", run_id)
            record.status = "failed"
            self._store.update_status(run_id, "failed")
            state.append(
                run_failed_envelope(
                    run_id=run_id,
                    sequence=0,
                    message="The roast run failed. Please try again.",
                )
            )
        finally:
            state.finish()


_manager = RunManager(db_path=get_settings().runs_db_path)


def get_run_manager() -> RunManager:
    return _manager
