"""Tests for L4 Execution Environment — boot order, shutdown order, events, Dockerfile.

All tests run against a fully mocked dependency surface: no real Qdrant, no real
Langfuse, no real MCP server.  The call-log technique verifies that each boot step
fires exactly once AND in the documented order.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import LayerEvent, LayerName


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_async_noop(call_log: list[str], name: str):
    """Return a coroutine function that appends *name* to *call_log*."""

    async def _fn(*args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        call_log.append(name)

    _fn.__name__ = name
    return _fn


# ---------------------------------------------------------------------------
# Test 1: qdrant_health runs before sqlite_migrate
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_lifespan_runs_qdrant_health_before_migrations():
    """Boot step 1 (qdrant_health) must complete before step 2 (sqlite_migrate)."""
    call_log: list[str] = []

    async def fake_qdrant_health() -> None:
        call_log.append("qdrant_health")

    async def fake_sqlite_migrate() -> None:
        call_log.append("sqlite_migrate")

    async def fake_langfuse_handshake() -> None:
        call_log.append("langfuse_handshake")

    @asynccontextmanager
    async def fake_mcp_lifespan():
        call_log.append("mcp_server_start")
        yield
        call_log.append("mcp_server_stop")

    fake_app = MagicMock()
    fake_app.state = MagicMock()

    with (
        patch("app.api.lifespan._check_qdrant_health", fake_qdrant_health),
        patch("app.api.lifespan._apply_sqlite_migrations", fake_sqlite_migrate),
        patch("app.api.lifespan._langfuse_handshake", fake_langfuse_handshake),
        patch("app.api.lifespan.mcp_lifespan_task", fake_mcp_lifespan),
    ):
        from app.api.lifespan import lifespan

        async with lifespan(fake_app):
            pass

    qdrant_idx = call_log.index("qdrant_health")
    migrate_idx = call_log.index("sqlite_migrate")
    assert qdrant_idx < migrate_idx, (
        f"qdrant_health must run before sqlite_migrate; got order {call_log}"
    )


# ---------------------------------------------------------------------------
# Test 2: sqlite_migrate runs before langfuse_handshake
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_lifespan_runs_migrations_before_langfuse_handshake():
    """Boot step 2 (sqlite_migrate) must complete before step 3 (langfuse_handshake)."""
    call_log: list[str] = []

    async def fake_qdrant_health() -> None:
        call_log.append("qdrant_health")

    async def fake_sqlite_migrate() -> None:
        call_log.append("sqlite_migrate")

    async def fake_langfuse_handshake() -> None:
        call_log.append("langfuse_handshake")

    @asynccontextmanager
    async def fake_mcp_lifespan():
        call_log.append("mcp_server_start")
        yield
        call_log.append("mcp_server_stop")

    fake_app = MagicMock()
    fake_app.state = MagicMock()

    with (
        patch("app.api.lifespan._check_qdrant_health", fake_qdrant_health),
        patch("app.api.lifespan._apply_sqlite_migrations", fake_sqlite_migrate),
        patch("app.api.lifespan._langfuse_handshake", fake_langfuse_handshake),
        patch("app.api.lifespan.mcp_lifespan_task", fake_mcp_lifespan),
    ):
        from app.api.lifespan import lifespan

        async with lifespan(fake_app):
            pass

    migrate_idx = call_log.index("sqlite_migrate")
    langfuse_idx = call_log.index("langfuse_handshake")
    assert migrate_idx < langfuse_idx, (
        f"sqlite_migrate must run before langfuse_handshake; got order {call_log}"
    )


# ---------------------------------------------------------------------------
# Test 3: 4 boot_step_completed events emitted with correct step names
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_lifespan_emits_boot_step_completed_per_stage():
    """Lifespan must emit one L4_EXECUTION/boot_step_completed per boot step (4 total)."""
    emitted: list[LayerEvent] = []

    def fake_emit(
        *,
        conversation_id: str,
        layer: LayerName,
        event_type: str,
        payload: dict | None = None,
    ) -> None:
        emitted.append(
            LayerEvent(
                conversation_id=conversation_id,
                layer=layer,
                event_type=event_type,
                payload=payload or {},
            )
        )

    async def fake_qdrant_health() -> None:
        pass

    async def fake_sqlite_migrate() -> None:
        pass

    async def fake_langfuse_handshake() -> None:
        pass

    @asynccontextmanager
    async def fake_mcp_lifespan():
        yield

    fake_app = MagicMock()
    fake_app.state = MagicMock()

    with (
        patch("app.api.lifespan._check_qdrant_health", fake_qdrant_health),
        patch("app.api.lifespan._apply_sqlite_migrations", fake_sqlite_migrate),
        patch("app.api.lifespan._langfuse_handshake", fake_langfuse_handshake),
        patch("app.api.lifespan.mcp_lifespan_task", fake_mcp_lifespan),
        patch("app.api.lifespan.get_emitter") as mock_get_emitter,
    ):
        mock_emitter = MagicMock()
        mock_emitter.emit.side_effect = fake_emit
        mock_get_emitter.return_value = mock_emitter

        from app.api.lifespan import lifespan

        async with lifespan(fake_app):
            pass

    boot_events = [
        e for e in emitted
        if e.layer == LayerName.EXECUTION and e.event_type == "boot_step_completed"
    ]
    assert len(boot_events) == 4, (
        f"Expected 4 boot_step_completed events, got {len(boot_events)}: {boot_events}"
    )

    step_names = [e.payload.get("step") for e in boot_events]
    expected_steps = ["qdrant_health", "sqlite_migrate", "langfuse_handshake", "mcp_server_start"]
    assert step_names == expected_steps, (
        f"Expected steps {expected_steps}, got {step_names}"
    )

    for e in boot_events:
        assert "latency_ms" in e.payload, f"Missing latency_ms in payload: {e.payload}"
        assert isinstance(e.payload["latency_ms"], float), (
            f"latency_ms must be float, got {type(e.payload['latency_ms'])}"
        )


# ---------------------------------------------------------------------------
# Test 4: shutdown runs in reverse order of startup
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_lifespan_shutdown_reverses_order():
    """Shutdown must reverse the startup order: mcp_stop → langfuse_flush → sqlite_close."""
    call_log: list[str] = []

    async def fake_qdrant_health() -> None:
        call_log.append("startup:qdrant_health")

    async def fake_sqlite_migrate() -> None:
        call_log.append("startup:sqlite_migrate")

    async def fake_langfuse_handshake() -> None:
        call_log.append("startup:langfuse_handshake")

    @asynccontextmanager
    async def fake_mcp_lifespan():
        call_log.append("startup:mcp_server_start")
        yield
        call_log.append("shutdown:mcp_server_stop")

    async def fake_langfuse_flush() -> None:
        call_log.append("shutdown:langfuse_flush")

    async def fake_sqlite_close() -> None:
        call_log.append("shutdown:sqlite_close")

    fake_app = MagicMock()
    fake_app.state = MagicMock()

    with (
        patch("app.api.lifespan._check_qdrant_health", fake_qdrant_health),
        patch("app.api.lifespan._apply_sqlite_migrations", fake_sqlite_migrate),
        patch("app.api.lifespan._langfuse_handshake", fake_langfuse_handshake),
        patch("app.api.lifespan.mcp_lifespan_task", fake_mcp_lifespan),
        patch("app.api.lifespan._flush_langfuse", fake_langfuse_flush),
        patch("app.api.lifespan._close_sqlite", fake_sqlite_close),
    ):
        from app.api.lifespan import lifespan

        async with lifespan(fake_app):
            pass  # everything after yield is shutdown

    startup_steps = [e for e in call_log if e.startswith("startup:")]
    shutdown_steps = [e for e in call_log if e.startswith("shutdown:")]

    # Startup order
    assert startup_steps == [
        "startup:qdrant_health",
        "startup:sqlite_migrate",
        "startup:langfuse_handshake",
        "startup:mcp_server_start",
    ], f"Unexpected startup order: {startup_steps}"

    # Shutdown: mcp_stop first, then langfuse_flush, then sqlite_close
    assert shutdown_steps == [
        "shutdown:mcp_server_stop",
        "shutdown:langfuse_flush",
        "shutdown:sqlite_close",
    ], f"Unexpected shutdown order: {shutdown_steps}"


# ---------------------------------------------------------------------------
# Test 5: Dockerfile structure — non-root user + HEALTHCHECK present
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dockerfile_uses_non_root_user():
    """Dockerfile must have USER appuser after the final FROM line, and a HEALTHCHECK."""
    dockerfile_path = Path(__file__).resolve().parent.parent / "Dockerfile"
    assert dockerfile_path.exists(), f"Dockerfile not found at {dockerfile_path}"

    lines = dockerfile_path.read_text(encoding="utf-8").splitlines()

    # Find the index of the last FROM line (the runtime stage)
    last_from_idx = max(
        (i for i, line in enumerate(lines) if line.strip().upper().startswith("FROM")),
        default=-1,
    )
    assert last_from_idx >= 0, "No FROM line found in Dockerfile"

    # Lines after the last FROM
    post_runtime_lines = lines[last_from_idx:]
    post_runtime_text = "\n".join(post_runtime_lines)

    # USER appuser must appear after the final FROM
    assert any(
        line.strip().startswith("USER appuser") for line in post_runtime_lines
    ), f"'USER appuser' not found after final FROM line. Runtime stage:\n{post_runtime_text}"

    # CMD must appear after USER appuser
    user_idx = next(
        i for i, line in enumerate(post_runtime_lines) if line.strip().startswith("USER appuser")
    )
    cmd_idx = next(
        (i for i, line in enumerate(post_runtime_lines) if line.strip().startswith("CMD")),
        -1,
    )
    assert cmd_idx > user_idx, (
        "CMD must appear after USER appuser in the runtime stage"
    )

    # HEALTHCHECK directive must be present somewhere in the Dockerfile
    full_text = "\n".join(lines)
    assert "HEALTHCHECK" in full_text, "HEALTHCHECK directive not found in Dockerfile"
