"""sqlite-vector extension helpers for IdeaStore."""

from __future__ import annotations

import importlib.resources
import sqlite3
import struct


def serialize_float32(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def load_vector_extension(conn: sqlite3.Connection) -> None:
    """Load the sqlite-vector extension into a SQLite connection."""
    ext_path = importlib.resources.files("sqlite_vector.binaries") / "vector"
    conn.enable_load_extension(True)
    conn.load_extension(str(ext_path))
    conn.enable_load_extension(False)


def init_vector_table(
    conn: sqlite3.Connection,
    *,
    table: str,
    column: str,
    dimension: int,
) -> None:
    conn.execute(
        f"SELECT vector_init('{table}', '{column}', "
        f"'dimension={dimension},type=FLOAT32,distance=COSINE')"
    )
