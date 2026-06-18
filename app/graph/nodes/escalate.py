"""Node: escalate — handles all cases that require human handoff."""

from __future__ import annotations

import uuid
from typing import Any

from app.domain.models import AgentState, EscalationRecord, RefundDecision, RefundDecisionKind
from app.graph.nodes._events import async_node_scope
from app.state import get_repository


async def escalate_node(state: AgentState) -> dict[str, Any]:
    """Escalate the conversation to a human agent."""
    cid: str = state.conversation_id or "unknown"

    async with async_node_scope("escalate", cid):
        candidate_decision = state.candidate_decision
        intent = state.intent or ""

        # Determine reason code
        reason_code = "OUT_OF_SCOPE"

        if intent == "identity_mismatch":
            reason_code = "IDENTITY_MISMATCH"
        elif (state.fraud_risk_score or 0.0) >= 0.5:
            reason_code = "FRAUD_RISK_HIGH"
        elif candidate_decision is not None and candidate_decision.escalation_code:
            reason_code = candidate_decision.escalation_code

        # Check verification blocks
        if state.verification is not None and state.verification.blocked:
            reason_code = "INJECTION_DETECTED"

        # Check approval denied
        if state.approval_resolution == "denied":
            reason_code = "AMOUNT_EXCEEDS_CAP"

        # Write escalation record
        escalation_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"
        try:
            repo = get_repository()
            esc_record = EscalationRecord(
                escalation_id=escalation_id,
                conversation_id=cid,
                reason_code=reason_code,
                severity="medium",
            )
            repo.save_escalation(esc_record)
        except Exception:
            pass  # Non-fatal

        # Build final decision
        final_decision = RefundDecision(
            kind=RefundDecisionKind.ESCALATE,
            amount_usd=0.0,
            reason_summary=f"Escalated to human agent. Reason: {reason_code}.",
            escalation_code=reason_code,
        )

        response = (
            "Your request has been escalated to a human agent who will review your case. "
            "You will receive a response within 1-2 business days."
        )

        return {
            "final_decision": final_decision,
            "response_text": response,
            "awaiting_human_approval": False,
        }
