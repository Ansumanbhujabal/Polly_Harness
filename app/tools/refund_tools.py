"""L3 Tools: issue_refund, escalate_to_human.

Both tools write to SQLite (data/state.db). For now the schema is a stub
matching the shape that SPEC_STATE will use when it lands in Wave 1.
The real `app.state.repositories` module will wrap the same tables; callers
can migrate to that interface without changing tool contracts.

Idempotency guarantee for issue_refund:
  INSERT OR IGNORE into `refunds` on (conversation_id, order_id).
  First insert generates the refund_id; subsequent calls look it up.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.models import LayerName, RefundDecisionKind
from app.observability.layer_event_emitter import get_emitter
from app.tools.base import BaseTool

VALID_REASON_CODES = frozenset(
    {
        "ABUSE_FLAG_PRESENT",
        "ACTIVE_CHARGEBACK",
        "AMOUNT_EXCEEDS_CAP",
        "IDENTITY_MISMATCH",
        "THREAT_DETECTED",
        "INJECTION_DETECTED",
        "FRAUD_RISK_HIGH",
        "OUT_OF_SCOPE",
    }
)


def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS refunds (
            refund_id      TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            order_id       TEXT NOT NULL,
            amount_usd     REAL NOT NULL,
            kind           TEXT NOT NULL,
            created_at     TEXT NOT NULL,
            UNIQUE(conversation_id, order_id)
        );

        CREATE TABLE IF NOT EXISTS human_approvals (
            escalation_id   TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            order_id        TEXT NOT NULL,
            reason_code     TEXT NOT NULL,
            notes           TEXT,
            created_at      TEXT NOT NULL
        );
        """
    )
    conn.commit()


# --------------------------------------------------------------------------- #
# IssueRefund
# --------------------------------------------------------------------------- #


class IssueRefund(BaseTool):
    """Write a refund record to SQLite and emit a LayerEvent.

    Idempotent on (conversation_id, order_id): if the same pair is submitted
    again, the existing refund_id is returned without writing a second row.
    Generated ID format: REF-{conversation_id}-{n} where n is a sequence suffix.
    """

    name = "issue_refund"
    description = (
        "Write a confirmed refund to the durable state database and emit an event. "
        "Idempotent: submitting the same (conversation_id, order_id) pair returns the "
        "same refund_id without creating a duplicate. "
        "Returns {refund_id, status='issued', amount_usd}."
    )

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            from app.config import settings

            db_path = str(settings.sqlite_full_path)
        self._db_path = db_path

    class Input(BaseTool.Input):
        conversation_id: str
        order_id: str
        amount_usd: float
        kind: RefundDecisionKind = RefundDecisionKind.APPROVE_FULL

    class Output(BaseTool.Output):
        refund_id: str
        status: Literal["issued"] = "issued"
        amount_usd: float

    async def run(self, input: "IssueRefund.Input") -> "IssueRefund.Output":  # noqa: A002
        emitter = get_emitter()
        conn = _get_conn(self._db_path)
        _ensure_schema(conn)

        # Idempotency check
        existing = conn.execute(
            "SELECT refund_id FROM refunds WHERE conversation_id=? AND order_id=?",
            (input.conversation_id, input.order_id),
        ).fetchone()

        if existing:
            refund_id = existing["refund_id"]
            conn.close()
            emitter.emit(
                conversation_id=input.conversation_id,
                layer=LayerName.TOOLS,
                event_type="tool_invoked",
                payload={
                    "tool": self.name,
                    "refund_id": refund_id,
                    "idempotent_hit": True,
                },
            )
            return self.Output(refund_id=refund_id, amount_usd=input.amount_usd)

        # Count existing refunds for this conversation to create a sequence suffix
        count = conn.execute(
            "SELECT COUNT(*) FROM refunds WHERE conversation_id=?",
            (input.conversation_id,),
        ).fetchone()[0]
        refund_id = f"REF-{input.conversation_id}-{count + 1}"

        conn.execute(
            """
            INSERT OR IGNORE INTO refunds
                (refund_id, conversation_id, order_id, amount_usd, kind, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                refund_id,
                input.conversation_id,
                input.order_id,
                input.amount_usd,
                input.kind.value if hasattr(input.kind, "value") else str(input.kind),
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        conn.close()

        emitter.emit(
            conversation_id=input.conversation_id,
            layer=LayerName.TOOLS,
            event_type="tool_invoked",
            payload={
                "tool": self.name,
                "refund_id": refund_id,
                "amount_usd": input.amount_usd,
                "order_id": input.order_id,
            },
        )

        return self.Output(refund_id=refund_id, amount_usd=input.amount_usd)


# --------------------------------------------------------------------------- #
# EscalateToHuman
# --------------------------------------------------------------------------- #


class EscalateToHuman(BaseTool):
    """Mark a conversation for human review by writing to the human_approvals table.

    Valid reason codes:
    ABUSE_FLAG_PRESENT, ACTIVE_CHARGEBACK, AMOUNT_EXCEEDS_CAP, IDENTITY_MISMATCH,
    THREAT_DETECTED, INJECTION_DETECTED, FRAUD_RISK_HIGH, OUT_OF_SCOPE.
    """

    name = "escalate_to_human"
    description = (
        "Mark the current conversation for human review by writing an escalation record "
        "to the durable state database. Callers must supply a valid reason_code from the "
        "enum: ABUSE_FLAG_PRESENT, ACTIVE_CHARGEBACK, AMOUNT_EXCEEDS_CAP, IDENTITY_MISMATCH, "
        "THREAT_DETECTED, INJECTION_DETECTED, FRAUD_RISK_HIGH, OUT_OF_SCOPE. "
        "Returns {escalation_id, reason_code}."
    )

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            from app.config import settings

            db_path = str(settings.sqlite_full_path)
        self._db_path = db_path

    class Input(BaseTool.Input):
        conversation_id: str
        order_id: str
        reason_code: str
        notes: str = ""

    class Output(BaseTool.Output):
        escalation_id: str
        reason_code: str

    async def run(self, input: "EscalateToHuman.Input") -> "EscalateToHuman.Output":  # noqa: A002
        emitter = get_emitter()

        if input.reason_code not in VALID_REASON_CODES:
            raise ValueError(
                f"Invalid reason_code {input.reason_code!r}. "
                f"Must be one of: {sorted(VALID_REASON_CODES)}"
            )

        conn = _get_conn(self._db_path)
        _ensure_schema(conn)

        escalation_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"

        conn.execute(
            """
            INSERT INTO human_approvals
                (escalation_id, conversation_id, order_id, reason_code, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                escalation_id,
                input.conversation_id,
                input.order_id,
                input.reason_code,
                input.notes,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        conn.close()

        emitter.emit(
            conversation_id=input.conversation_id,
            layer=LayerName.TOOLS,
            event_type="tool_invoked",
            payload={
                "tool": self.name,
                "escalation_id": escalation_id,
                "reason_code": input.reason_code,
                "order_id": input.order_id,
            },
        )

        return self.Output(escalation_id=escalation_id, reason_code=input.reason_code)
