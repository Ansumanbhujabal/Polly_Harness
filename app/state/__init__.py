"""L5 Durable State public API.

Two singletons, one contract:

    from app.state import get_checkpointer, get_repository, Repository

- get_checkpointer() -> SqliteSaver  — for LangGraph node wiring
- get_repository()   -> Repository   — for all domain writes / reads
"""

from __future__ import annotations

from app.state.checkpointer import get_checkpointer, get_connection
from app.state.repositories import Repository

__all__ = ["Repository", "get_checkpointer", "get_repository"]

_repo: Repository | None = None


def get_repository() -> Repository:
    """Process-global Repository singleton backed by the shared SQLite connection.

    Migrations are applied on first call so the schema is always up-to-date
    before any read/write attempt.
    """
    global _repo
    if _repo is None:
        conn = get_connection()
        _repo = Repository(conn)
        _repo.apply_migrations()
    return _repo
