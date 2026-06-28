"""SQLite-backed durable run metadata and event log."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import logging
from pathlib import Path
import sqlite3
import threading

from api.deps import RunRecord
from api.events import run_failed_envelope
from api.schemas import ApiEventEnvelope, CreateRunRequest
from config import PROJECT_ROOT

logger = logging.getLogger(__name__)

_INTERRUPTED_MESSAGE = "The roast run was interrupted. Please try again."


class RunStore:
    # ponytail: SQLite + in-process notify is enough for single-box multi-worker
    # (shared DB file, one machine). Redis pub/sub is the upgrade for multi-machine.

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or PROJECT_ROOT / "data" / "runs.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                request_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS run_events (
                run_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (run_id, sequence)
            );
            CREATE INDEX IF NOT EXISTS idx_run_events_run_id_sequence
                ON run_events (run_id, sequence);
            """
        )
        self._conn.commit()

    def insert_run(self, record: RunRecord) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO runs (run_id, request_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    record.request.model_dump_json(),
                    record.status,
                    record.created_at.isoformat(),
                    now.isoformat(),
                ),
            )
            self._conn.commit()

    def update_status(self, run_id: str, status: str) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self._conn.execute(
                "UPDATE runs SET status = ?, updated_at = ? WHERE run_id = ?",
                (status, now.isoformat(), run_id),
            )
            self._conn.commit()

    def get_run_record(self, run_id: str) -> RunRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT request_json, status, created_at FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        request_json, status, created_at = row
        return RunRecord(
            run_id=run_id,
            request=CreateRunRequest.model_validate_json(request_json),
            status=status,
            created_at=datetime.fromisoformat(created_at),
        )

    def append_event(self, run_id: str, envelope: ApiEventEnvelope) -> ApiEventEnvelope:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(sequence), -1) FROM run_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            next_sequence = int(row[0]) + 1
            envelope = envelope.model_copy(update={"sequence": next_sequence})
            self._conn.execute(
                """
                INSERT INTO run_events (run_id, sequence, type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    envelope.sequence,
                    envelope.type,
                    json.dumps(envelope.payload),
                    envelope.created_at.isoformat(),
                ),
            )
            self._conn.execute(
                "UPDATE runs SET updated_at = ? WHERE run_id = ?",
                (envelope.created_at.isoformat(), run_id),
            )
            self._conn.commit()
            return envelope

    def append_event_once(
        self,
        run_id: str,
        envelope: ApiEventEnvelope,
        *,
        guard_type: str,
    ) -> ApiEventEnvelope:
        """Append ``envelope`` only if no event of ``guard_type`` exists for ``run_id``."""
        with self._lock:
            exists = self._conn.execute(
                "SELECT 1 FROM run_events WHERE run_id = ? AND type = ? LIMIT 1",
                (run_id, guard_type),
            ).fetchone()
            if exists:
                raise ValueError(f"An event of type {guard_type!r} already exists for this run")

            row = self._conn.execute(
                "SELECT COALESCE(MAX(sequence), -1) FROM run_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            next_sequence = int(row[0]) + 1
            envelope = envelope.model_copy(update={"sequence": next_sequence})
            self._conn.execute(
                """
                INSERT INTO run_events (run_id, sequence, type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    envelope.sequence,
                    envelope.type,
                    json.dumps(envelope.payload),
                    envelope.created_at.isoformat(),
                ),
            )
            self._conn.execute(
                "UPDATE runs SET updated_at = ? WHERE run_id = ?",
                (envelope.created_at.isoformat(), run_id),
            )
            self._conn.commit()
            return envelope

    def list_runs(self, *, limit: int = 20, offset: int = 0) -> tuple[list[RunRecord], int]:
        with self._lock:
            total = int(self._conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0])
            rows = self._conn.execute(
                """
                SELECT run_id, request_json, status, created_at
                FROM runs
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        records = [
            RunRecord(
                run_id=run_id,
                request=CreateRunRequest.model_validate_json(request_json),
                status=status,
                created_at=datetime.fromisoformat(created_at),
            )
            for run_id, request_json, status, created_at in rows
        ]
        return records, total

    def get_latest_event(self, run_id: str, event_type: str) -> ApiEventEnvelope | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT sequence, type, payload_json, created_at
                FROM run_events
                WHERE run_id = ? AND type = ?
                ORDER BY sequence DESC
                LIMIT 1
                """,
                (run_id, event_type),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_envelope(run_id, row)

    def list_events_after(self, run_id: str, after_sequence: int) -> list[ApiEventEnvelope]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT sequence, type, payload_json, created_at
                FROM run_events
                WHERE run_id = ? AND sequence > ?
                ORDER BY sequence
                """,
                (run_id, after_sequence),
            ).fetchall()
        return [self._row_to_envelope(run_id, row) for row in rows]

    def fail_run(
        self,
        run_id: str,
        *,
        message: str = _INTERRUPTED_MESSAGE,
    ) -> ApiEventEnvelope | None:
        """Mark a running run failed and append ``run_failed``. Idempotent for terminal runs."""
        with self._lock:
            row = self._conn.execute(
                "SELECT status FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row is None or row[0] != "running":
                return None

            now = datetime.now(UTC)
            self._conn.execute(
                "UPDATE runs SET status = 'failed', updated_at = ? WHERE run_id = ?",
                (now.isoformat(), run_id),
            )
            seq_row = self._conn.execute(
                "SELECT COALESCE(MAX(sequence), -1) FROM run_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            envelope = run_failed_envelope(
                run_id=run_id,
                sequence=int(seq_row[0]) + 1,
                message=message,
                recoverable=True,
            )
            self._conn.execute(
                """
                INSERT INTO run_events (run_id, sequence, type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    envelope.sequence,
                    envelope.type,
                    json.dumps(envelope.payload),
                    envelope.created_at.isoformat(),
                ),
            )
            self._conn.commit()
            return envelope

    def recover_stale_runs(self, stale_minutes: int) -> list[str]:
        cutoff = datetime.now(UTC) - timedelta(minutes=stale_minutes)
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT r.run_id
                FROM runs r
                LEFT JOIN (
                    SELECT run_id, MAX(created_at) AS last_event_at
                    FROM run_events
                    GROUP BY run_id
                ) e ON e.run_id = r.run_id
                WHERE r.status = 'running'
                  AND COALESCE(e.last_event_at, r.updated_at) < ?
                """,
                (cutoff.isoformat(),),
            ).fetchall()
            run_ids = [run_id for (run_id,) in rows]

        recovered: list[str] = []
        for run_id in run_ids:
            if self.fail_run(run_id) is not None:
                recovered.append(run_id)
        if recovered:
            logger.info(
                "Recovered %d stale running run(s): %s",
                len(recovered),
                ", ".join(recovered),
            )
        return recovered

    @staticmethod
    def _row_to_envelope(run_id: str, row: tuple) -> ApiEventEnvelope:
        sequence, event_type, payload_json, created_at = row
        return ApiEventEnvelope(
            type=event_type,
            run_id=run_id,
            sequence=sequence,
            payload=json.loads(payload_json),
            created_at=datetime.fromisoformat(created_at),
        )

    def close(self) -> None:
        self._conn.close()
