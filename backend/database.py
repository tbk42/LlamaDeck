from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from backend.config import DB_PATH

_local = threading.local()


def get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH))
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


@contextmanager
def get_db():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS instances (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                type        TEXT NOT NULL CHECK(type IN ('docker','local','remote')),
                url         TEXT NOT NULL DEFAULT 'http://localhost:11434',
                api_key     TEXT,
                container_id TEXT,
                gguf_dir    TEXT,
                container_gguf_dir TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        # Add column for existing databases
        try:
            conn.execute("ALTER TABLE instances ADD COLUMN container_gguf_dir TEXT")
        except Exception:
            pass
