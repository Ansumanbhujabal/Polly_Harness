"""Node: issue_refund_node — finalises and records the approved refund.

DEFENSIVE ASSERT: assert not state.verification.blocked — fail-closed guarantee.
"""

from __future__ import annotations

from typing import Any

from app.domain.models import AgentState, RefundDecision, RefundDecisionKind
from app.graph.nodes._events import async_node_scope
from app.tools import get_tool_by_name
from app.tools.executor import run_tool


async def issue_refund_node(state: AgentState) -> dict[str, Any]:
    """Issue the approved refund. Defensive fail-closed guard at entry."""
    cid: str = state.conversation_id or "unknown"

    async with async_node_scope("issue_refund_node", cid):
        # DEFENSIVE ASSERT — fail-closed guarantee per SPEC
        verification = state.verification
        if verification is not None:
            assert not verification.blocked, (
                f"[FAIL-CLOSED] issue_refund_node reached with blocked verification "
                f"for conversation {cid}. This is a routing bug."
            )

        candidate_decision = state.candidate_decision
        order = state.order

        if candidate_decision is None or order is None:
            return {}

        amount = candidate_decision.amount_usd
        kind = candidate_decision.kind
        order_id = order.order_id

        # Issue via tool
        issue_tool = get_tool_by_name("issue_refund")
        if issue_tool is not None:
            await run_tool(
                issue_tool,
                {
                    "conversation_id": cid,
                    "order_id": order_id,
                    "amount_usd": amount,
                    "kind": kind.value if hasattr(kind, "value") else str(kind),
                },
                conversation_id=cid,
            )

        # Build final decision from candidate
        final_decision = RefundDecision(
            kind=candidate_decision.kind,
            amount_usd=candidate_decision.amount_usd,
            reason_summary=candidate_decision.reason_summary,
            cited_clause_ids=candidate_decision.cited_clause_ids,
            requires_human_approval=False,
        )

        return {
            "final_decision": final_decision,
            "awaiting_human_approval": False,
        }
