"""L5 Durable State — SqliteSaver checkpointer singleton.

Wraps LangGraph's SqliteSaver so the agent graph can resume mid-conversation
across process restarts. The same SQLite file is used by both the checkpointer
and the Repository; LangGraph owns its own tables (checkpoints, writes) and
the Repository never touches those directly.

WAL journal mode is enabled at connection time for concurrent-write safety.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from app.config import settings

_saver: SqliteSaver | None = None
_conn: sqlite3.Connection | None = None


def get_checkpointer() -> SqliteSaver:
    """Process-global SqliteSaver singleton backed by settings.sqlite_full_path.

    On first call:
    1. Opens the SQLite connection with check_same_thread=False.
    2. Sets WAL journal mode.
    3. Calls SqliteSaver.setup() to ensure LangGraph's own tables exist.
    """
    global _saver, _conn
    if _saver is None:
        db_path = settings.sqlite_full_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = _open_wal_connection(db_path)
        _saver = SqliteSaver(_conn)
        _saver.setup()
    return _saver


def get_connection() -> sqlite3.Connection:
    """Return the shared SQLite connection (used by get_repository())."""
    if _conn is None:
        get_checkpointer()  # ensures _conn is initialised
    assert _conn is not None
    return _conn


def _open_wal_connection(db_path: Path) -> sqlite3.Connection:
    """Open an SQLite connection with WAL mode and a sensible busy timeout."""
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.commit()
    return conn


def close() -> None:
    """Close the connection (called by app lifespan on shutdown)."""
    global _saver, _conn
    if _conn is not None:
        _conn.close()
        _conn = None
        _saver = None
