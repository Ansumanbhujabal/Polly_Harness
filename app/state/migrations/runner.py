"""Migration runner for L5 Durable State.

Applies SQL migration files in lexicographic order. Already-applied versions
(recorded in schema_versions) are skipped — idempotent by design.

No ORM. No Alembic. Just SQL files and a 30-line runner.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.domain.models import LayerName
from app.observability.layer_event_emitter import get_emitter

_MIGRATIONS_DIR = Path(__file__).parent


def apply_all(conn: sqlite3.Connection) -> None:
    """Apply all pending migrations from the migrations directory.

    Bootstraps the schema_versions table itself if it does not yet exist,
    then applies each *.sql file in lexicographic order that is not already
    recorded in schema_versions.
    """
    # Ensure the tracking table exists before anything else
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_versions ("
        "version TEXT NOT NULL PRIMARY KEY, "
        "applied_at TEXT NOT NULL"
        ")"
    )
    conn.commit()

    # Collect already-applied versions
    cursor = conn.execute("SELECT version FROM schema_versions")
    applied: set[str] = {row[0] for row in cursor.fetchall()}

    sql_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    emitter = get_emitter()

    for sql_file in sql_files:
        version = sql_file.stem  # e.g. "0001_initial"
        if version in applied:
            continue

        sql = sql_file.read_text(encoding="utf-8")
        conn.executescript(sql)

        conn.execute(
            "INSERT INTO schema_versions (version, applied_at) VALUES (?, ?)",
            (version, datetime.utcnow().isoformat()),
        )
        conn.commit()

        emitter.emit(
            conversation_id="system",
            layer=LayerName.STATE,
            event_type="migration_applied",
            payload={"version": version},
        )
