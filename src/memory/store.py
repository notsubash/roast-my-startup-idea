from collections.abc import Callable
import logging
from pathlib import Path
import sqlite3

from config import PROJECT_ROOT
from memory.models import IdeaRecord
from memory.vectors import init_vector_table, load_vector_extension, serialize_float32

logger = logging.getLogger(__name__)

_EMBEDDINGS_TABLE = "idea_embeddings"


class IdeaStore:
    """Small SQLite-backed store for local, durable idea memory."""

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        embed_fn: Callable[[str], list[float]] | None = None,
        embedding_dimension: int = 768,
        enable_semantic: bool = False,
    ):
        self.db_path = db_path or PROJECT_ROOT / "data" / "ideas.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._embed_fn = embed_fn
        self._embedding_dimension = embedding_dimension
        self._vectors_loaded = False
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
        self._conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_EMBEDDINGS_TABLE} (
                idea_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                embedding BLOB NOT NULL
            )
            """
        )
        self._conn.commit()

        if enable_semantic and embed_fn is not None:
            self._init_vectors()

    @property
    def semantic_search_enabled(self) -> bool:
        return self._vectors_loaded and self._embed_fn is not None

    def _init_vectors(self) -> None:
        # ponytail: sqlite-vector is single-box, file-local; Redis/pgvector is the upgrade path.
        try:
            load_vector_extension(self._conn)
            init_vector_table(
                self._conn,
                table=_EMBEDDINGS_TABLE,
                column="embedding",
                dimension=self._embedding_dimension,
            )
            self._vectors_loaded = True
        except (OSError, sqlite3.Error, AttributeError):
            self._vectors_loaded = False

    def _embed_idea_text(self, idea_text: str) -> list[float] | None:
        if self._embed_fn is None:
            return None
        try:
            vector = self._embed_fn(idea_text)
        except Exception:
            return None
        if len(vector) != self._embedding_dimension:
            return None
        return vector

    def _save_embedding(self, *, idea_id: str, user_id: str, idea_text: str) -> None:
        if not self._vectors_loaded:
            return
        vector = self._embed_idea_text(idea_text)
        if vector is None:
            return
        self._conn.execute(
            f"""
            INSERT OR REPLACE INTO {_EMBEDDINGS_TABLE} (idea_id, user_id, embedding)
            VALUES (?, ?, ?)
            """,
            (idea_id, user_id, serialize_float32(vector)),
        )

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
        self._save_embedding(
            idea_id=record.id,
            user_id=record.user_id,
            idea_text=record.idea_text,
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

    def list_similar(self, user_id: str, query_text: str, *, limit: int = 3) -> list[IdeaRecord]:
        if not self.semantic_search_enabled:
            return []

        query_vector = self._embed_idea_text(query_text)
        if query_vector is None:
            return []

        try:
            rows = self._conn.execute(
                f"""
                SELECT ideas.payload
                FROM vector_full_scan(?, 'embedding', ?) AS scan
                JOIN {_EMBEDDINGS_TABLE} AS embeddings ON embeddings.rowid = scan.rowid
                JOIN ideas ON ideas.id = embeddings.idea_id
                WHERE embeddings.user_id = ? AND ideas.user_id = ?
                ORDER BY scan.distance
                LIMIT ?
                """,
                (
                    _EMBEDDINGS_TABLE,
                    serialize_float32(query_vector),
                    user_id,
                    user_id,
                    limit,
                ),
            ).fetchall()
        except sqlite3.Error:
            logger.warning(
                "Semantic memory search failed for user %s; falling back to recency",
                user_id,
                exc_info=True,
            )
            return []
        return [IdeaRecord.model_validate_json(row[0]) for row in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
