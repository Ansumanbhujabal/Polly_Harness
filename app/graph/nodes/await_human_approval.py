"""Node: await_human_approval — suspends the graph pending human review.

Before calling interrupt():
1. Writes a PendingApproval row to the Repository.
2. Emits L6_ORCHESTRATION / interrupt_raised.
3. Calls interrupt(value) to suspend the graph.

On resume, the value passed to Command(resume=...) is stored in state.approval_resolution.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from langgraph.types import interrupt

from app.domain.models import AgentState, LayerName, PendingApproval
from app.graph.nodes._events import async_node_scope
from app.observability import get_emitter
from app.state import get_repository


async def await_human_approval_node(state: AgentState) -> dict[str, Any]:
    """Suspend the graph and wait for human approval."""
    cid: str = state.conversation_id or "unknown"

    async with async_node_scope("await_human_approval", cid):
        candidate_decision = state.candidate_decision

        if candidate_decision is None:
            return {}

        approval_id = f"APPR-{uuid.uuid4().hex[:8].upper()}"
        amount = candidate_decision.amount_usd

        # Write PendingApproval row BEFORE suspending
        approval = PendingApproval(
            approval_id=approval_id,
            conversation_id=cid,
            candidate_decision=candidate_decision,
            required_approver_role="supervisor",
        )
        try:
            repo = get_repository()
            repo.save_approval(approval)
        except Exception:
            pass  # Non-fatal: best-effort persistence

        # Emit interrupt_raised event
        emitter = get_emitter()
        emitter.emit(
            conversation_id=cid,
            layer=LayerName.ORCHESTRATION,
            event_type="interrupt_raised",
            payload={
                "approval_id": approval_id,
                "reason": "Refund amount exceeds auto-approval cap",
                "amount_usd": amount,
            },
        )

        # Set awaiting flag BEFORE interrupt so it's in the checkpoint
        # (interrupt raises GraphInterrupt and state updates in this return won't
        # be applied on first call — so we emit the event and then interrupt)

        # SUSPEND — raises GraphInterrupt; graph exits here on first call.
        # On resume, interrupt() returns the value passed via Command(resume=...).
        resolution: Literal["approved", "denied"] = interrupt(
            {
                "approval_id": approval_id,
                "amount_usd": amount,
                "message": "Refund requires human approval. Approve or deny.",
            }
        )

        # After resume — store the resolution
        return {
            "approval_resolution": resolution,
            "awaiting_human_approval": False,
        }
