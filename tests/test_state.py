"""Tests for L5 Durable State — SQLite repositories, migrations, and checkpointer.

All 12 tests per SPEC_STATE.md.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.domain.models import (
    EscalationRecord,
    IncidentRecord,
    LayerEvent,
    LayerName,
    PendingApproval,
    RefundDecision,
    RefundDecisionKind,
    RefundRecord,
)
from app.observability.layer_event_emitter import LayerEventEmitter


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_repo(db_path: Path):
    """Build a fresh Repository backed by a tmp_path DB."""
    from app.state.repositories import Repository

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    repo = Repository(conn)
    repo.apply_migrations()
    return repo, conn


def _sample_refund(
    *,
    refund_id: str = "RFD-001",
    conversation_id: str = "CONV-A",
    order_id: str = "ORD-1001",
    customer_id: str = "CUST-001",
    amount_usd: float = 49.99,
    kind: str = RefundDecisionKind.APPROVE_FULL,
) -> RefundRecord:
    return RefundRecord(
        refund_id=refund_id,
        conversation_id=conversation_id,
        order_id=order_id,
        customer_id=customer_id,
        amount_usd=amount_usd,
        kind=kind,
        cited_clauses=["POLICY-001", "POLICY-002"],
        reasoning="Within return window, item as described",
    )


def _sample_escalation(
    *,
    escalation_id: str = "ESC-001",
    conversation_id: str = "CONV-B",
) -> EscalationRecord:
    return EscalationRecord(
        escalation_id=escalation_id,
        conversation_id=conversation_id,
        reason_code="ABUSE_FLAG_PRESENT",
        severity="high",
    )


def _sample_incident(
    *,
    incident_id: str = "INC-UUID-001",
    conversation_id: str = "CONV-C",
) -> IncidentRecord:
    return IncidentRecord(
        incident_id=incident_id,
        conversation_id=conversation_id,
        triggered_by="verification_failure",
        layer=LayerName.VERIFICATION,
        summary="Injection detected",
    )


def _sample_approval(
    *,
    approval_id: str = "APR-001",
    conversation_id: str = "CONV-D",
) -> PendingApproval:
    decision = RefundDecision(
        kind=RefundDecisionKind.APPROVE_PARTIAL,
        amount_usd=250.0,
        reason_summary="Partial refund for late delivery",
        cited_clause_ids=["POLICY-003"],
    )
    return PendingApproval(
        approval_id=approval_id,
        conversation_id=conversation_id,
        candidate_decision=decision,
        required_approver_role="senior_agent",
    )


# ---------------------------------------------------------------------------
# Test 1 — migrations create all 6 tables
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_migrations_apply_on_clean_db(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    from app.state.migrations.runner import apply_all

    apply_all(conn)

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in cursor.fetchall()}
    expected = {
        "refunds",
        "escalations",
        "incidents",
        "pending_approvals",
        "processed_incidents",
        "schema_versions",
    }
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"
    conn.close()


# ---------------------------------------------------------------------------
# Test 2 — migrations are idempotent
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_migrations_idempotent_on_rerun(tmp_path: Path) -> None:
    db_path = tmp_path / "idempotent.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    from app.state.migrations.runner import apply_all

    apply_all(conn)
    apply_all(conn)  # must not raise

    cursor = conn.execute("SELECT count(*) FROM schema_versions")
    count = cursor.fetchone()[0]
    # Exactly one row per migration file — not doubled
    assert count >= 1, "schema_versions should have at least one entry"
    # No duplicates
    cursor2 = conn.execute("SELECT count(DISTINCT version) FROM schema_versions")
    distinct = cursor2.fetchone()[0]
    assert count == distinct, "Duplicate migration entries found"
    conn.close()


# ---------------------------------------------------------------------------
# Test 3 — save_refund insert and find_refund round-trip
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_save_refund_inserts_new(tmp_path: Path) -> None:
    repo, conn = _make_repo(tmp_path / "t3.db")
    record = _sample_refund()
    saved = repo.save_refund(record)

    fetched = repo.find_refund(record.conversation_id, record.order_id)
    assert fetched is not None
    assert fetched.refund_id == saved.refund_id
    assert fetched.amount_usd == pytest.approx(49.99)
    assert "POLICY-001" in fetched.cited_clauses
    conn.close()


# ---------------------------------------------------------------------------
# Test 4 — save_refund is insert-or-noop on duplicate (conversation_id, order_id)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_save_refund_returns_existing_id_on_duplicate(tmp_path: Path) -> None:
    repo, conn = _make_repo(tmp_path / "t4.db")
    first = _sample_refund(refund_id="RFD-FIRST", amount_usd=99.00)
    saved_first = repo.save_refund(first)

    # Same business key, different refund_id and amount — should be noop
    second = _sample_refund(refund_id="RFD-SECOND", amount_usd=150.00)
    saved_second = repo.save_refund(second)

    # The second call must return the FIRST record's id and amount
    assert saved_second.refund_id == saved_first.refund_id == "RFD-FIRST"
    assert saved_second.amount_usd == pytest.approx(99.00)

    # Only one row in DB
    cursor = conn.execute("SELECT count(*) FROM refunds")
    assert cursor.fetchone()[0] == 1
    conn.close()


# ---------------------------------------------------------------------------
# Test 5 — find_refund returns None for unknown key
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_find_refund_returns_none_when_missing(tmp_path: Path) -> None:
    repo, conn = _make_repo(tmp_path / "t5.db")
    result = repo.find_refund("CONV-GHOST", "ORD-GHOST")
    assert result is None
    conn.close()


# ---------------------------------------------------------------------------
# Test 6 — save_escalation round-trip
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_save_escalation_writes_row(tmp_path: Path) -> None:
    repo, conn = _make_repo(tmp_path / "t6.db")
    esc = _sample_escalation()
    saved = repo.save_escalation(esc)

    cursor = conn.execute(
        "SELECT escalation_id, reason_code, severity FROM escalations WHERE escalation_id = ?",
        (esc.escalation_id,),
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == esc.escalation_id
    assert row[1] == "ABUSE_FLAG_PRESENT"
    assert row[2] == "high"
    conn.close()


# ---------------------------------------------------------------------------
# Test 7 — save_incident is idempotent on incident_id (UUID)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_save_incident_idempotent_on_uuid(tmp_path: Path) -> None:
    repo, conn = _make_repo(tmp_path / "t7.db")
    inc = _sample_incident()
    repo.save_incident(inc)
    repo.save_incident(inc)  # same incident_id — must be noop

    cursor = conn.execute("SELECT count(*) FROM incidents WHERE incident_id = ?", (inc.incident_id,))
    assert cursor.fetchone()[0] == 1
    conn.close()


# ---------------------------------------------------------------------------
# Test 8 — list_pending_approvals returns only unresolved rows
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_list_pending_approvals_returns_unresolved_only(tmp_path: Path) -> None:
    repo, conn = _make_repo(tmp_path / "t8.db")

    apr1 = _sample_approval(approval_id="APR-001", conversation_id="CONV-1")
    apr2 = _sample_approval(approval_id="APR-002", conversation_id="CONV-2")
    apr3 = _sample_approval(approval_id="APR-003", conversation_id="CONV-3")

    repo.save_approval(apr1)
    repo.save_approval(apr2)
    repo.save_approval(apr3)

    # Resolve one
    repo.resolve_approval("APR-003", "denied", "agent-007")

    pending = repo.list_pending_approvals()
    pending_ids = {a.approval_id for a in pending}
    assert len(pending) == 2
    assert "APR-001" in pending_ids
    assert "APR-002" in pending_ids
    assert "APR-003" not in pending_ids
    conn.close()


# ---------------------------------------------------------------------------
# Test 9 — resolve_approval marks resolved; second resolve raises ValueError
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_resolve_approval_marks_resolved_with_approver(tmp_path: Path) -> None:
    repo, conn = _make_repo(tmp_path / "t9.db")
    apr = _sample_approval()
    repo.save_approval(apr)

    resolved = repo.resolve_approval(apr.approval_id, "approved", "senior-alice")
    assert resolved.resolution == "approved"
    assert resolved.approver == "senior-alice"
    assert resolved.resolved_at is not None

    # Second resolve must raise
    with pytest.raises(ValueError, match="already resolved"):
        repo.resolve_approval(apr.approval_id, "denied", "someone-else")
    conn.close()


# ---------------------------------------------------------------------------
# Test 10 — checkpointer resumes LangGraph state across "session" (conn close/reopen)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_checkpointer_resumes_state_across_session(tmp_path: Path) -> None:
    from langgraph.checkpoint.sqlite import SqliteSaver

    db_path = tmp_path / "ckpt.db"

    # Session 1 — write a checkpoint
    with SqliteSaver.from_conn_string(str(db_path)) as saver1:
        config = {"configurable": {"thread_id": "t1", "checkpoint_ns": "", "checkpoint_id": None}}
        checkpoint: dict[str, Any] = {
            "v": 1,
            "ts": "2026-01-01T00:00:00+00:00",
            "id": "ckpt-1",
            "channel_values": {"messages": ["hello"]},
            "channel_versions": {"messages": 1},
            "versions_seen": {},
            "pending_sends": [],
        }
        metadata: dict[str, Any] = {"source": "input", "step": 0, "writes": {}}
        saver1.put(config, checkpoint, metadata, {})

    # Session 2 — reopen and read
    with SqliteSaver.from_conn_string(str(db_path)) as saver2:
        result = saver2.get_tuple({"configurable": {"thread_id": "t1", "checkpoint_ns": ""}})
        assert result is not None
        assert result.checkpoint["channel_values"]["messages"] == ["hello"]


# ---------------------------------------------------------------------------
# Test 11 — write_performed LayerEvent emitted per write
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_write_performed_event_emitted_per_write(tmp_path: Path) -> None:
    captured: list[LayerEvent] = []

    fake_emitter = LayerEventEmitter()
    fake_emitter.subscribe(lambda ev: captured.append(ev))

    # Patch the global emitter
    import app.observability.layer_event_emitter as emitter_mod

    original = emitter_mod._global_emitter
    emitter_mod._global_emitter = fake_emitter

    try:
        repo, conn = _make_repo(tmp_path / "t11.db")
        repo.save_refund(_sample_refund())
        repo.save_escalation(_sample_escalation())
        repo.save_incident(_sample_incident())
        repo.save_approval(_sample_approval())
    finally:
        emitter_mod._global_emitter = original
        conn.close()

    write_events = [
        ev
        for ev in captured
        if ev.event_type == "write_performed" and ev.layer == LayerName.STATE
    ]
    assert len(write_events) >= 4, f"Expected >=4 write_performed events, got {len(write_events)}"


# ---------------------------------------------------------------------------
# Test 12 — concurrent save_refund calls serialize without corruption
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_concurrent_writes_serialize(tmp_path: Path) -> None:
    """5 threads writing distinct refund rows concurrently — all land, no OperationalError."""
    import concurrent.futures

    repo, conn = _make_repo(tmp_path / "t12.db")

    def _do_save(i: int) -> RefundRecord:
        return repo.save_refund(
            _sample_refund(
                refund_id=f"RFD-{i:03d}",
                conversation_id=f"CONV-{i}",
                order_id=f"ORD-{i:04d}",
            )
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(_do_save, i) for i in range(5)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 5
    cursor = conn.execute("SELECT count(*) FROM refunds")
    count = cursor.fetchone()[0]
    assert count == 5, f"Expected 5 rows, got {count}"
    conn.close()
