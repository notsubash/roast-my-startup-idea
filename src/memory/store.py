from pathlib import Path
import sqlite3

from config import PROJECT_ROOT
from memory.models import IdeaRecord


class IdeaStore:
    """Small SQLite-backed store for local, durable idea memory."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or PROJECT_ROOT / "data" / "ideas.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ideas (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ideas_user_created_at ON ideas (user_id, created_at DESC)"
        )
        self._conn.commit()

    def save(self, record: IdeaRecord) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO ideas (id, user_id, payload, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                record.id,
                record.user_id,
                record.model_dump_json(),
                record.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def list_recent(self, user_id: str, limit: int = 3) -> list[IdeaRecord]:
        rows = self._conn.execute(
            """
            SELECT payload
            FROM ideas
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [IdeaRecord.model_validate_json(row[0]) for row in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
