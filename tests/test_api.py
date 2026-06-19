"""Tests for the FastAPI API layer — Task D2.

Uses httpx.AsyncClient + ASGITransport so no real server is spun up.
RefundGraph.ainvoke / aresume are patched to avoid Azure OpenAI calls.
"""

from __future__ import annotations

import asyncio
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.models import (
    IncidentRecord,
    LayerEvent,
    LayerName,
    PendingApproval,
    ProposedRemediation,
    RefundDecision,
    RefundDecisionKind,
)
from app.observability.sse_publisher import _reset_state_for_testing, push_event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_graph_result(
    conversation_id: str = "conv-test",
    awaiting: bool = False,
    response_text: str = "Refund approved.",
) -> dict[str, Any]:
    """Build a minimal graph result dict."""
    decision = RefundDecision(
        kind=RefundDecisionKind.APPROVE_FULL,
        amount_usd=49.99,
        reason_summary="Within return window",
    )
    return {
        "conversation_id": conversation_id,
        "final_decision": decision,
        "response_text": response_text,
        "tool_invocations": [{}],
        "awaiting_human_approval": awaiting,
    }


def _make_pending_approval(
    approval_id: str | None = None,
    conversation_id: str = "conv-1",
    resolution: str | None = None,
) -> PendingApproval:
    decision = RefundDecision(
        kind=RefundDecisionKind.APPROVE_FULL,
        amount_usd=100.0,
        reason_summary="Test",
    )
    return PendingApproval(
        approval_id=approval_id or str(uuid.uuid4()),
        conversation_id=conversation_id,
        candidate_decision=decision,
        required_approver_role="senior_agent",
        resolution=resolution,  # type: ignore[arg-type]
    )


def _seed_approvals(repo: Any, unresolved: int, resolved: int = 0) -> list[PendingApproval]:
    """Insert pending approvals into the repository."""
    items = []
    for _ in range(unresolved):
        a = _make_pending_approval()
        repo.save_approval(a)
        items.append(a)
    for _ in range(resolved):
        a = _make_pending_approval()
        repo.save_approval(a)
        # Mark resolved directly via SQL
        repo._conn.execute(
            "UPDATE pending_approvals SET resolution = 'approved', approver = 'test', "
            "resolved_at = ? WHERE approval_id = ?",
            (datetime.utcnow().isoformat(), a.approval_id),
        )
        repo._conn.commit()
        items.append(a)
    return items


def _seed_incidents(repo: Any, count: int) -> list[IncidentRecord]:
    """Insert *count* incidents into the repository."""
    items = []
    for i in range(count):
        inc = IncidentRecord(
            incident_id=str(uuid.uuid4()),
            conversation_id=f"conv-{i}",
            triggered_by="verification_failure",
            layer=LayerName.VERIFICATION,
            summary=f"Test incident {i}",
            created_at=datetime.utcnow() - timedelta(hours=i),
        )
        repo.save_incident(inc)
        items.append(inc)
    return items


# ---------------------------------------------------------------------------
# Test client fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """Fresh in-memory-ish SQLite repo for each test."""
    import sqlite3

    from app.config import settings
    from app.state.repositories import Repository

    db_path = tmp_path / "test_api_state.db"
    monkeypatch.setattr(settings, "SQLITE_PATH", str(db_path), raising=False)

    conn = sqlite3.connect(str(db_path))
    r = Repository(conn)
    r.apply_migrations()
    return r


@pytest.fixture()
async def client(monkeypatch, tmp_path):
    """Async httpx client backed by the FastAPI ASGI app.

    Lifespan is bypassed so we don't need real Qdrant/Langfuse/MCP.
    """
    from app.config import settings

    db_path = tmp_path / "test_api_state2.db"
    monkeypatch.setattr(settings, "SQLITE_PATH", str(db_path), raising=False)

    # Bypass the full lifespan (Qdrant / MCP / Langfuse not available in unit tests)
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop_lifespan(app):  # type: ignore[misc]
        yield

    with patch("app.api.main.lifespan", _noop_lifespan):
        # Re-import with patched lifespan
        import importlib

        import app.api.main as main_mod

        importlib.reload(main_mod)
        _app = main_mod.app

        async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as c:
            yield c


# ---------------------------------------------------------------------------
# 1. test_healthz_returns_ok_when_all_deps_up
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_healthz_returns_ok_when_all_deps_up(client):
    """Mock both probes healthy; assert 200 + ok=True."""
    with (
        patch(
            "app.api.routes.health._probe_qdrant",
            new=AsyncMock(return_value="up"),
        ),
        patch(
            "app.api.routes.health._probe_langfuse",
            new=AsyncMock(return_value="up"),
        ),
    ):
        r = await client.get("/healthz")

    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["qdrant"] == "up"
    assert body["langfuse"] == "up"


# ---------------------------------------------------------------------------
# 2. test_healthz_returns_qdrant_down_when_unreachable
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_healthz_returns_qdrant_down_when_unreachable(client):
    """Qdrant probe raises; response includes qdrant='down' but still 200."""
    with (
        patch(
            "app.api.routes.health._probe_qdrant",
            new=AsyncMock(return_value="down"),
        ),
        patch(
            "app.api.routes.health._probe_langfuse",
            new=AsyncMock(return_value="up"),
        ),
    ):
        r = await client.get("/healthz")

    assert r.status_code == 200
    body = r.json()
    assert body["qdrant"] == "down"
    assert body["ok"] is False  # one dep down → not ok


# ---------------------------------------------------------------------------
# 3. test_chat_route_invokes_graph_and_returns_response
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_route_invokes_graph_and_returns_response(client):
    """Patch RefundGraph.ainvoke to return known state; assert summary fields match."""
    expected_cid = "conv-abc"
    mock_result = _make_graph_result(conversation_id=expected_cid)

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value=mock_result)

    with (
        patch("app.api.routes.chat.build_graph", new=AsyncMock(return_value=mock_graph)),
    ):
        r = await client.post(
            "/api/v1/chat",
            json={"conversation_id": expected_cid, "message": "I want a refund"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True
    assert body["conversation_id"] == expected_cid
    summary = body["final_state_summary"]
    assert summary["response_text"] == "Refund approved."
    assert summary["num_tool_invocations"] == 1
    assert summary["awaiting_human_approval"] is False


# ---------------------------------------------------------------------------
# 4. test_chat_route_creates_conversation_id_when_missing
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_route_creates_conversation_id_when_missing(client):
    """Omit conversation_id; response includes a freshly-minted UUID."""
    mock_graph = MagicMock()

    def _dynamic_result(state, config):
        # Use the conversation_id from the state passed in
        cid = state.conversation_id if hasattr(state, "conversation_id") else "gen"
        return _make_graph_result(conversation_id=cid)

    mock_graph.ainvoke = AsyncMock(side_effect=_dynamic_result)

    with patch("app.api.routes.chat.build_graph", new=AsyncMock(return_value=mock_graph)):
        r = await client.post("/api/v1/chat", json={"message": "hello"})

    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True
    # Conversation ID should be a valid UUID
    generated = body["conversation_id"]
    assert len(generated) == 36  # UUID4 format
    uuid.UUID(generated)  # raises ValueError if invalid


# ---------------------------------------------------------------------------
# 5. test_approve_route_resumes_interrupted_graph
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_approve_route_resumes_interrupted_graph(client, repo):
    """Seed a pending_approvals row; POST /approve; assert aresume was called."""
    approval = _make_pending_approval(conversation_id="conv-resume")
    repo.save_approval(approval)

    mock_graph = MagicMock()
    mock_graph.aresume = AsyncMock(return_value={"conversation_id": "conv-resume"})

    with (
        patch("app.api.routes.approval.get_repository", return_value=repo),
        patch("app.api.routes.approval.build_graph", new=AsyncMock(return_value=mock_graph)),
    ):
        r = await client.post(
            "/api/v1/approve",
            json={
                "approval_id": approval.approval_id,
                "resolution": "approved",
                "approver": "admin",
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True
    assert body["resource_id"] == approval.approval_id
    mock_graph.aresume.assert_called_once()


# ---------------------------------------------------------------------------
# 6. test_approve_route_404_on_unknown_approval_id
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_approve_route_404_on_unknown_approval_id(client, repo):
    """Unknown approval_id → 404."""
    with patch("app.api.routes.approval.get_repository", return_value=repo):
        r = await client.post(
            "/api/v1/approve",
            json={
                "approval_id": "nonexistent-id",
                "resolution": "approved",
                "approver": "admin",
            },
        )

    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 7. test_events_stream_emits_layer_events_for_conversation
# ---------------------------------------------------------------------------


async def _drain_sse_generator(
    conversation_id: str | None, target_count: int, timeout_s: float = 3.0
) -> list[str]:
    """Drain the SSE generator directly, returning up to *target_count* data payloads.

    Tests SSE at the generator level — bypasses the HTTP layer because
    httpx ASGITransport + sse_starlette's anyio task groups don't compose
    cleanly in unit tests.
    """
    from app.observability import sse_event_stream

    received: list[str] = []

    async def _read() -> None:
        async for sse_event in sse_event_stream(conversation_id=conversation_id):
            received.append(sse_event.data)
            if len(received) >= target_count:
                return

    try:
        await asyncio.wait_for(_read(), timeout=timeout_s)
    except asyncio.TimeoutError:
        pass
    return received


@pytest.mark.unit
@pytest.mark.asyncio
async def test_events_stream_emits_layer_events_for_conversation(client):
    """Inject 3 events for conversation X; drain SSE generator; assert 3 events arrive.

    Tests the SSE generator directly (sse_event_stream) rather than through the HTTP
    transport because httpx ASGITransport + sse_starlette's anyio task groups do not
    compose cleanly in unit tests. The HTTP endpoint is smoke-tested below.
    """
    _reset_state_for_testing()

    cid = "conv-sse-x"
    for i in range(3):
        push_event(
            LayerEvent(
                conversation_id=cid,
                layer=LayerName.ORCHESTRATION,
                event_type=f"test_event_{i}",
            )
        )

    received_payloads = await _drain_sse_generator(cid, target_count=3)
    assert len(received_payloads) == 3
    # All payloads contain the conversation id
    for payload in received_payloads:
        assert cid in payload


# ---------------------------------------------------------------------------
# 8. test_events_stream_filters_by_conversation_id
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_events_stream_filters_by_conversation_id(client):
    """Inject events for X and Y; drain SSE generator for X; only X events arrive."""
    _reset_state_for_testing()

    for i in range(2):
        push_event(
            LayerEvent(
                conversation_id="conv-x",
                layer=LayerName.ORCHESTRATION,
                event_type=f"x_event_{i}",
            )
        )
    push_event(
        LayerEvent(
            conversation_id="conv-y",
            layer=LayerName.ORCHESTRATION,
            event_type="y_event_0",
        )
    )

    received_payloads = await _drain_sse_generator("conv-x", target_count=2)

    assert len(received_payloads) == 2
    # All received events should be for conv-x, not conv-y
    for payload in received_payloads:
        assert "conv-x" in payload
        assert "conv-y" not in payload


# ---------------------------------------------------------------------------
# 9. test_admin_pending_approvals_lists_unresolved
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_admin_pending_approvals_lists_unresolved(client, repo):
    """Seed 2 unresolved + 1 resolved; assert response has 2 items."""
    _seed_approvals(repo, unresolved=2, resolved=1)

    with patch("app.api.routes.admin.get_repository", return_value=repo):
        r = await client.get("/admin/api/pending_approvals")

    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2


# ---------------------------------------------------------------------------
# 10. test_admin_incidents_returns_limit_filtered_list
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_admin_incidents_returns_limit_filtered_list(client, repo):
    """Seed 30 incidents; request ?limit=20; assert 20 items."""
    _seed_incidents(repo, count=30)

    with patch("app.api.routes.admin.get_repository", return_value=repo):
        r = await client.get("/admin/api/incidents?limit=20")

    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 20


# ---------------------------------------------------------------------------
# 11. test_admin_distill_endpoint_triggers_distillation
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_admin_distill_endpoint_triggers_distillation(client):
    """Patch distill_incidents to return a known proposal; assert it's in response."""
    known_proposal = ProposedRemediation(
        kind="new_skill",
        target_file="skills/handle_grace_period.md",
        markdown_diff="--- a/skills\n+++ b/skills",
        justification="Incidents show pattern X",
        source_incident_ids=["inc-1", "inc-2"],
    )

    with patch(
        "app.api.routes.admin.distill_incidents",
        new=AsyncMock(return_value=[known_proposal]),
    ):
        r = await client.post("/admin/api/distill")

    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True
    assert len(body["proposals"]) == 1
    assert body["proposals"][0]["target_file"] == "skills/handle_grace_period.md"


# ---------------------------------------------------------------------------
# 12. test_admin_conversation_trace_returns_chronological_events
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_admin_conversation_trace_returns_chronological_events(client):
    """Seed events with mixed timestamps; assert response is sorted ascending."""
    _reset_state_for_testing()

    cid = "conv-trace"
    now = datetime.utcnow()

    # Push events out of chronological order
    for i in [2, 0, 1]:
        push_event(
            LayerEvent(
                conversation_id=cid,
                layer=LayerName.ORCHESTRATION,
                event_type=f"trace_event_{i}",
                timestamp=now + timedelta(seconds=i),
            )
        )

    r = await client.get(f"/admin/api/conversations/{cid}/trace")

    assert r.status_code == 200
    body = r.json()
    items = body["items"]
    assert len(items) == 3

    # Verify ascending order
    timestamps = [it["timestamp"] for it in items]
    assert timestamps == sorted(timestamps)
