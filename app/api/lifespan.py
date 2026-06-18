"""FastAPI lifespan — L4 Execution Environment boot / shutdown sequencer.

Boot order (SPEC_EXECUTION §boot order):
    1. _check_qdrant_health()       — HTTP GET /healthz probe
    2. _apply_sqlite_migrations()   — idempotent migration runner
    3. _langfuse_handshake()        — confirm API key is live (fail-open)
    4. _start_mcp_server()          — in-process MCP server task (via mcp_lifespan_task)

Shutdown runs in the exact reverse:
    1. mcp_lifespan_task context exits  — cancels the MCP background task
    2. _flush_langfuse()                — flush pending spans (timeout=5 s)
    3. _close_sqlite()                  — close the connection pool

One ``L4_EXECUTION / boot_step_completed`` event is emitted per step with
``{step: <name>, latency_ms: <float>}`` in the payload.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI

from app.config import settings
from app.domain.models import LayerName
from app.mcp.server import mcp_lifespan_task
from app.observability.layer_event_emitter import get_emitter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Boot step helpers
# ---------------------------------------------------------------------------


async def _check_qdrant_health() -> None:
    """Issue a single GET /healthz to the configured Qdrant URL.

    Raises RuntimeError if the response status is not 2xx.
    A "collection missing" situation (404 on a specific collection endpoint) is
    treated as a WARN — seeding is a developer concern, not a runtime crash.
    """
    url = settings.QDRANT_URL.rstrip("/") + "/healthz"
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(url)
            if response.status_code >= 300:
                raise RuntimeError(f"Qdrant unreachable at {settings.QDRANT_URL}")
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Qdrant unreachable at {settings.QDRANT_URL}") from exc
    logger.info("qdrant_health_ok", extra={"url": settings.QDRANT_URL})


async def _apply_sqlite_migrations() -> None:
    """Run all pending SQL migrations via the durable-state runner (idempotent)."""
    import sqlite3

    from app.state.migrations.runner import apply_all

    conn = sqlite3.connect(str(settings.sqlite_full_path))
    try:
        apply_all(conn)
    finally:
        conn.close()
    logger.info("sqlite_migrations_applied")


async def _langfuse_handshake() -> None:
    """Confirm that the Langfuse API key is valid by issuing a no-op span.

    Fails open: if ``settings.langfuse_configured`` is False, logs WARN and
    continues — the system runs without Langfuse.
    """
    from app.observability import get_langfuse_client

    if not settings.langfuse_configured:
        logger.warning("langfuse_not_configured: skipping handshake")
        return

    client = get_langfuse_client()
    if client is None:
        logger.warning("langfuse_client_unavailable: skipping handshake")
        return

    # Issue a no-op trace to confirm the key is valid.
    try:
        trace = client.trace(name="boot_handshake")
        trace.generation(name="noop", model="system", input="ping", output="pong")
        logger.info("langfuse_handshake_ok")
    except Exception as exc:  # noqa: BLE001
        logger.warning("langfuse_handshake_error", extra={"error": str(exc)})


# ---------------------------------------------------------------------------
# Shutdown helpers
# ---------------------------------------------------------------------------


async def _flush_langfuse() -> None:
    """Flush pending Langfuse spans with a 5-second timeout."""
    from app.observability import get_langfuse_client

    client = get_langfuse_client()
    if client is None:
        return
    try:
        client.flush(timeout=5.0)
        logger.info("langfuse_flushed")
    except Exception as exc:  # noqa: BLE001
        logger.warning("langfuse_flush_error", extra={"error": str(exc)})


async def _close_sqlite() -> None:
    """Close the SQLite connection pool (no-op when using per-request connections)."""
    # The current implementation in app.state uses per-request sqlite3.connect() calls
    # so there is no persistent pool to close.  This hook exists so that if a connection
    # pool is introduced later (e.g. aiosqlite pool) the shutdown contract is already wired.
    logger.info("sqlite_connection_pool_closed")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


def _emit_boot_step(step: str, latency_ms: float) -> None:
    """Emit one L4_EXECUTION/boot_step_completed event."""
    get_emitter().emit(
        conversation_id="system",
        layer=LayerName.EXECUTION,
        event_type="boot_step_completed",
        payload={"step": step, "latency_ms": latency_ms},
    )


async def _run_step(name: str, coro_fn) -> None:  # noqa: ANN001
    """Run *coro_fn()*, measure wall-clock latency, and emit the step event."""
    t0 = time.monotonic()
    await coro_fn()
    latency_ms = (time.monotonic() - t0) * 1000.0
    _emit_boot_step(name, latency_ms)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan context manager — ordered boot + reverse-order shutdown.

    Pass to ``FastAPI(lifespan=lifespan)`` in ``app/api/main.py``.
    """
    # -----------------------------------------------------------------------
    # Boot sequence (steps 1-3 run before entering the MCP context manager)
    # -----------------------------------------------------------------------
    await _run_step("qdrant_health", _check_qdrant_health)
    await _run_step("sqlite_migrate", _apply_sqlite_migrations)
    await _run_step("langfuse_handshake", _langfuse_handshake)

    # Step 4: MCP server start — the context manager handles its own shutdown
    t0 = time.monotonic()
    async with mcp_lifespan_task():
        latency_ms = (time.monotonic() - t0) * 1000.0
        _emit_boot_step("mcp_server_start", latency_ms)

        # Hand control to FastAPI; HTTP traffic begins.
        yield

        # -----------------------------------------------------------------------
        # Shutdown sequence (reverse order):
        # 1. mcp_lifespan_task.__aexit__ fires when 'async with' exits (MCP stop)
        # 2. _flush_langfuse
        # 3. _close_sqlite
        # (Qdrant check is read-only — no shutdown step needed.)
        # -----------------------------------------------------------------------

    # Steps 2 and 3 of shutdown (step 1 handled by mcp_lifespan_task exit above)
    await _flush_langfuse()
    await _close_sqlite()
