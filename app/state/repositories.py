"""L5 Durable State — Repository facade.

Single writer to the SQLite database (except LangGraph's own checkpointer tables).
No business logic. No derivation. No merge semantics.

All SQL is parameterized — no f-strings in SQL statements.
Every successful write emits a L5_STATE / write_performed LayerEvent.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from typing import Literal

from app.domain.models import (
    EscalationRecord,
    IncidentRecord,
    LayerName,
    PendingApproval,
    RefundDecision,
    RefundRecord,
)
from app.observability.layer_event_emitter import get_emitter
from app.state.migrations.runner import apply_all


class Repository:
    """Thin facade over the SQLite durable-state tables.

    Instantiated once per process (singleton via get_repository()).
    Thread-safe: a module-level lock serializes all writes so that concurrent
    callers sharing the same sqlite3.Connection object don't race.
    WAL mode is still enabled at connection time for OS-level durability.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Migration
    # ------------------------------------------------------------------

    def apply_migrations(self) -> None:
        """Apply all pending migrations. Called once at startup."""
        apply_all(self._conn)

    # ------------------------------------------------------------------
    # Refunds
    # ------------------------------------------------------------------

    def save_refund(self, refund: RefundRecord) -> RefundRecord:
        """Insert-or-noop on (conversation_id, order_id).

        If the business key already exists, returns the existing record
        unchanged (preserving the original refund_id). Safe for retry.
        """
        with self._lock:
            existing = self._find_refund_locked(refund.conversation_id, refund.order_id)
            if existing is not None:
                return existing

            self._conn.execute(
                "INSERT INTO refunds "
                "(refund_id, conversation_id, order_id, customer_id, amount_usd, "
                " kind, cited_clauses, reasoning, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    refund.refund_id,
                    refund.conversation_id,
                    refund.order_id,
                    refund.customer_id,
                    refund.amount_usd,
                    str(refund.kind),
                    json.dumps(refund.cited_clauses),
                    refund.reasoning,
                    refund.created_at.isoformat(),
                ),
            )
            self._conn.commit()

        self._emit_write("refunds", f"{refund.conversation_id}:{refund.order_id}")
        return refund

    def find_refund(self, conversation_id: str, order_id: str) -> RefundRecord | None:
        """Return the refund for (conversation_id, order_id), or None."""
        with self._lock:
            return self._find_refund_locked(conversation_id, order_id)

    def _find_refund_locked(self, conversation_id: str, order_id: str) -> RefundRecord | None:
        """Like find_refund but must be called with self._lock already held."""
        cursor = self._conn.execute(
            "SELECT refund_id, conversation_id, order_id, customer_id, amount_usd, "
            "kind, cited_clauses, reasoning, created_at "
            "FROM refunds WHERE conversation_id = ? AND order_id = ?",
            (conversation_id, order_id),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return RefundRecord(
            refund_id=row[0],
            conversation_id=row[1],
            order_id=row[2],
            customer_id=row[3],
            amount_usd=row[4],
            kind=row[5],
            cited_clauses=json.loads(row[6]),
            reasoning=row[7],
            created_at=datetime.fromisoformat(row[8]),
        )

    # ------------------------------------------------------------------
    # Escalations
    # ------------------------------------------------------------------

    def save_escalation(self, esc: EscalationRecord) -> EscalationRecord:
        """Insert escalation record. No deduplication — every escalation is distinct."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO escalations "
                "(escalation_id, conversation_id, reason_code, severity, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    esc.escalation_id,
                    esc.conversation_id,
                    esc.reason_code,
                    esc.severity,
                    esc.created_at.isoformat(),
                ),
            )
            self._conn.commit()
        self._emit_write("escalations", esc.escalation_id)
        return esc

    # ------------------------------------------------------------------
    # Incidents
    # ------------------------------------------------------------------

    def save_incident(self, inc: IncidentRecord) -> IncidentRecord:
        """Insert-or-noop on incident_id. Safe under distiller replay."""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT incident_id FROM incidents WHERE incident_id = ?",
                (inc.incident_id,),
            )
            if cursor.fetchone() is not None:
                return inc  # already present — noop

            self._conn.execute(
                "INSERT INTO incidents "
                "(incident_id, conversation_id, triggered_by, layer, summary, "
                " detail, proposed_remediation, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    inc.incident_id,
                    inc.conversation_id,
                    inc.triggered_by,
                    inc.layer.value if hasattr(inc.layer, "value") else str(inc.layer),
                    inc.summary,
                    json.dumps(inc.detail),
                    inc.proposed_remediation,
                    inc.created_at.isoformat(),
                ),
            )
            self._conn.commit()
        self._emit_write("incidents", inc.incident_id)
        return inc

    # ------------------------------------------------------------------
    # Pending approvals
    # ------------------------------------------------------------------

    def save_approval(self, approval: PendingApproval) -> PendingApproval:
        """Insert a new pending approval row."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO pending_approvals "
                "(approval_id, conversation_id, candidate_decision, "
                " required_approver_role, created_at, resolution, approver, resolved_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    approval.approval_id,
                    approval.conversation_id,
                    approval.candidate_decision.model_dump_json(),
                    approval.required_approver_role,
                    approval.created_at.isoformat(),
                    approval.resolution,
                    approval.approver,
                    approval.resolved_at.isoformat() if approval.resolved_at else None,
                ),
            )
            self._conn.commit()
        self._emit_write("pending_approvals", approval.approval_id)
        return approval

    def list_pending_approvals(self) -> list[PendingApproval]:
        """Return all rows where resolution IS NULL."""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT approval_id, conversation_id, candidate_decision, "
                "required_approver_role, created_at, resolution, approver, resolved_at "
                "FROM pending_approvals WHERE resolution IS NULL"
            )
            rows = cursor.fetchall()
        return [self._row_to_approval(row) for row in rows]

    def resolve_approval(
        self,
        approval_id: str,
        resolution: Literal["approved", "denied"],
        approver: str,
    ) -> PendingApproval:
        """Conditional-update: only updates rows where resolution IS NULL.

        Raises ValueError if the row is already resolved.
        """
        with self._lock:
            cursor = self._conn.execute(
                "SELECT resolution FROM pending_approvals WHERE approval_id = ?",
                (approval_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError(f"approval {approval_id!r} not found")
            if row[0] is not None:
                raise ValueError(f"approval {approval_id!r} already resolved")

            resolved_at = datetime.utcnow()
            self._conn.execute(
                "UPDATE pending_approvals "
                "SET resolution = ?, approver = ?, resolved_at = ? "
                "WHERE approval_id = ? AND resolution IS NULL",
                (resolution, approver, resolved_at.isoformat(), approval_id),
            )
            self._conn.commit()
            self._emit_write("pending_approvals", approval_id)

            cursor2 = self._conn.execute(
                "SELECT approval_id, conversation_id, candidate_decision, "
                "required_approver_role, created_at, resolution, approver, resolved_at "
                "FROM pending_approvals WHERE approval_id = ?",
                (approval_id,),
            )
            return self._row_to_approval(cursor2.fetchone())

    # ------------------------------------------------------------------
    # Processed incidents
    # ------------------------------------------------------------------

    def mark_incident_processed(self, incident_id: str, batch_id: str = "") -> None:
        """Insert a processed_incidents row. Noop if already present.

        Args:
            incident_id: The incident to mark as processed.
            batch_id: Optional batch identifier for grouping runs.
        """
        with self._lock:
            cursor = self._conn.execute(
                "SELECT incident_id FROM processed_incidents WHERE incident_id = ?",
                (incident_id,),
            )
            if cursor.fetchone() is not None:
                return  # already marked — idempotent

            self._conn.execute(
                "INSERT INTO processed_incidents (incident_id, processed_at, batch_id) "
                "VALUES (?, ?, ?)",
                (incident_id, datetime.utcnow().isoformat(), batch_id),
            )
            self._conn.commit()
        self._emit_write("processed_incidents", incident_id)

    def list_unprocessed_incidents(self, min_age_minutes: int = 60) -> list[IncidentRecord]:
        """Return incidents older than min_age_minutes that have not been processed.

        Incidents are ordered by created_at ascending (oldest first).
        """
        from datetime import timedelta

        cutoff = (datetime.utcnow() - timedelta(minutes=min_age_minutes)).isoformat()
        with self._lock:
            cursor = self._conn.execute(
                "SELECT incident_id, conversation_id, triggered_by, layer, "
                "summary, detail, proposed_remediation, created_at "
                "FROM incidents "
                "WHERE created_at <= ? "
                "AND incident_id NOT IN (SELECT incident_id FROM processed_incidents) "
                "ORDER BY created_at ASC",
                (cutoff,),
            )
            rows = cursor.fetchall()

        result: list[IncidentRecord] = []
        for row in rows:
            result.append(
                IncidentRecord(
                    incident_id=row[0],
                    conversation_id=row[1],
                    triggered_by=row[2],  # type: ignore[arg-type]
                    layer=LayerName(row[3]),
                    summary=row[4],
                    detail=json.loads(row[5]) if row[5] else {},
                    proposed_remediation=row[6],
                    created_at=datetime.fromisoformat(row[7]),
                )
            )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_approval(row: tuple) -> PendingApproval:  # type: ignore[type-arg]
        return PendingApproval(
            approval_id=row[0],
            conversation_id=row[1],
            candidate_decision=RefundDecision.model_validate_json(row[2]),
            required_approver_role=row[3],
            created_at=datetime.fromisoformat(row[4]),
            resolution=row[5],
            approver=row[6],
            resolved_at=datetime.fromisoformat(row[7]) if row[7] else None,
        )

    def _emit_write(self, table: str, business_key: str) -> None:
        get_emitter().emit(
            conversation_id="system",
            layer=LayerName.STATE,
            event_type="write_performed",
            payload={"table": table, "business_key": business_key},
        )
