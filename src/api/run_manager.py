"""Run engine decoupled from the HTTP connection.

A ``RunManager`` drives ``stream_pipeline`` to completion exactly once per run,
buffering every event in a durable SQLite log. HTTP clients are pure subscribers:
they replay the log and then await new events. This means a browser can
disconnect and reconnect, or several tabs can watch the same run, without the
run dying or a second viewer getting rejected.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
import logging
from pathlib import Path
import threading
import time
from uuid import uuid4

from api.deps import (
    RunRecord,
    build_model_for_run,
    build_research_context_for_run,
    build_startup_idea_context,
)
from api.events import (
    run_cancelled_envelope,
    run_failed_envelope,
    stream_connected_envelope,
    to_api_envelope,
)
from api.run_store import RunStore
from api.schemas import ApiEventEnvelope, CreateRunRequest, VerdictSummary
from appeal.service import AppealResult, run_appeal
from config import Settings, get_settings
from events import RunMetrics
from judges.schemas import RoastPanel
from observability.metrics import log_run_metrics
from pipeline import stream_pipeline
from run_control import RunAbort

logger = logging.getLogger(__name__)


def _verdict_summary_from_panel(panel: dict) -> VerdictSummary | None:
    verdicts = panel.get("verdicts")
    if not isinstance(verdicts, list) or not verdicts:
        return None
    counts = {"pass": 0, "fail": 0, "conditional": 0}
    scores: list[float] = []
    for item in verdicts:
        if not isinstance(item, dict):
            continue
        label = str(item.get("verdict", "")).lower()
        if label in counts:
            counts[label] += 1
        score = item.get("score")
        if isinstance(score, (int, float)):
            scores.append(float(score))
    if not any(counts.values()):
        return None
    avg = sum(scores) / len(scores) if scores else None
    return VerdictSummary(
        pass_count=counts["pass"],
        fail_count=counts["fail"],
        conditional_count=counts["conditional"],
        avg_score=round(avg, 1) if avg is not None else None,
    )


def _summary_for_completed_run(store: RunStore, run_id: str) -> VerdictSummary | None:
    appeal = store.get_latest_event(run_id, "appeal_completed")
    if appeal is not None:
        revised = appeal.payload.get("revised_panel")
        if isinstance(revised, dict):
            summary = _verdict_summary_from_panel(revised)
            if summary is not None:
                return summary

    completed = store.get_latest_event(run_id, "run_completed")
    if completed is None:
        return None
    roast_panel = completed.payload.get("roast_panel")
    if isinstance(roast_panel, dict):
        return _verdict_summary_from_panel(roast_panel)
    return None


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
        self._cancel = threading.Event()

    def append(self, envelope: ApiEventEnvelope) -> ApiEventEnvelope:
        envelope = self._store.append_event(self.record.run_id, envelope)
        for wakeup in self._subscribers:
            wakeup.set()
        return envelope

    def append_once(self, envelope: ApiEventEnvelope, *, guard_type: str) -> ApiEventEnvelope:
        envelope = self._store.append_event_once(
            self.record.run_id, envelope, guard_type=guard_type
        )
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

    def request_cancel(self) -> None:
        self._cancel.set()


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

    def list_runs(
        self, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[tuple[RunRecord, VerdictSummary | None]], int]:
        records, total = self._store.list_runs(limit=limit, offset=offset)
        items: list[tuple[RunRecord, VerdictSummary | None]] = []
        for record in records:
            summary = (
                _summary_for_completed_run(self._store, record.run_id)
                if record.status == "completed"
                else None
            )
            items.append((record, summary))
        return items, total

    async def appeal(
        self,
        run_id: str,
        appeal_text: str,
        settings: Settings,
    ) -> tuple[RoastPanel, AppealResult]:
        record = self.get(run_id)
        if record is None:
            raise KeyError(run_id)
        if record.status != "completed":
            raise ValueError("Run must be completed before submitting an appeal")
        if self._store.get_latest_event(run_id, "appeal_completed") is not None:
            raise ValueError("An appeal has already been submitted for this run")

        completed = self._store.get_latest_event(run_id, "run_completed")
        if completed is None:
            raise ValueError("Run has no completed results to appeal")

        roast_panel = RoastPanel.model_validate(completed.payload["roast_panel"])
        debate_result = completed.payload.get("debate_result")
        if not isinstance(debate_result, dict):
            debate_result = {}

        model = build_model_for_run(record.request, settings)
        startup_idea = build_startup_idea_context(record.request)
        result = await asyncio.to_thread(
            run_appeal,
            model,
            startup_idea,
            roast_panel,
            debate_result,
            appeal_text,
        )

        state = self._ensure_state(run_id)
        try:
            state.append_once(
                ApiEventEnvelope(
                    type="appeal_completed",
                    run_id=run_id,
                    sequence=0,
                    payload={
                        "appeal_text": appeal_text.strip(),
                        "original_panel": roast_panel.model_dump(mode="json"),
                        "revised_panel": result.revised_panel.model_dump(mode="json"),
                        "revised_synthesis": result.revised_synthesis,
                    },
                    created_at=datetime.now(UTC),
                ),
                guard_type="appeal_completed",
            )
        except ValueError as exc:
            raise ValueError("An appeal has already been submitted for this run") from exc
        return roast_panel, result

    def _ensure_state(self, run_id: str) -> _RunState:
        state = self._runs.get(run_id)
        if state is not None:
            return state
        record = self._store.get_run_record(run_id)
        if record is None:
            raise KeyError(run_id)
        terminal = record.status in ("completed", "failed", "cancelled")
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
        if state.record.status in ("completed", "failed", "cancelled"):
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

    def cancel(self, run_id: str) -> RunRecord:
        state = self._ensure_state(run_id)
        if state.record.status in ("completed", "failed", "cancelled"):
            raise ValueError("Run already finished")
        if state.record.status == "created":
            state.record.status = "cancelled"
            self._store.update_status(run_id, "cancelled")
            state.append(stream_connected_envelope(run_id=run_id))
            state.append(run_cancelled_envelope(run_id=run_id, sequence=0))
            state.finish()
            return state.record
        state.request_cancel()
        return state.record

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
            started_at = time.monotonic()
            max_seconds = settings.max_run_seconds

            def abort_check() -> str | None:
                if state._cancel.is_set():
                    return "cancelled"
                if max_seconds > 0 and time.monotonic() - started_at > max_seconds:
                    return "budget_exceeded"
                return None

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
                abort_check=abort_check,
            ):
                if isinstance(event, RunMetrics):
                    log_run_metrics(event.as_dict(), run_id=run_id)
                emit(to_api_envelope(event, run_id=run_id, sequence=0))

        try:
            await asyncio.to_thread(work)
            event_types = {envelope.type for envelope in self._store.list_events_after(run_id, -1)}
            if "run_completed" in event_types:
                record.status = "completed"
                self._store.update_status(run_id, "completed")
            elif state._cancel.is_set():
                record.status = "cancelled"
                self._store.update_status(run_id, "cancelled")
                if "run_cancelled" not in event_types:
                    state.append(run_cancelled_envelope(run_id=run_id, sequence=0))
            else:
                record.status = "completed"
                self._store.update_status(run_id, "completed")
        except RunAbort as exc:
            if exc.reason == "cancelled":
                record.status = "cancelled"
                self._store.update_status(run_id, "cancelled")
                state.append(run_cancelled_envelope(run_id=run_id, sequence=0))
            else:
                record.status = "failed"
                self._store.update_status(run_id, "failed")
                state.append(
                    run_failed_envelope(
                        run_id=run_id,
                        sequence=0,
                        message="Run exceeded the wall-clock budget. Please try again.",
                    )
                )
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
