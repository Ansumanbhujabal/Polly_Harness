"""Node: compute_decision — computes the candidate RefundDecision."""

from __future__ import annotations

from typing import Any

from app.domain.models import AgentState, CustomerTier, RefundDecision, RefundDecisionKind
from app.graph.nodes._events import async_node_scope
from app.tools import get_tool_by_name
from app.tools.executor import run_tool


def _get_tool_output(tool_invocations: list[Any], tool_name: str) -> dict[str, Any] | None:
    """Find the output of the most recent invocation of tool_name."""
    for inv in reversed(tool_invocations):
        if isinstance(inv, dict):
            if inv.get("tool_name") == tool_name:
                return inv.get("output")
        elif hasattr(inv, "tool_name") and inv.tool_name == tool_name:
            return inv.output if hasattr(inv, "output") else None
    return None


async def compute_decision_node(state: AgentState) -> dict[str, Any]:
    """Compute candidate RefundDecision from eligibility + fraud data."""
    cid: str = state.conversation_id or "unknown"

    async with async_node_scope("compute_decision", cid):
        customer = state.customer
        order = state.order
        tool_invocations: list[Any] = list(state.tool_invocations or [])
        fraud_risk_score: float = state.fraud_risk_score or 0.0

        if customer is None or order is None:
            decision = RefundDecision(
                kind=RefundDecisionKind.ESCALATE,
                amount_usd=0.0,
                reason_summary="Cannot compute decision: missing customer or order data.",
                escalation_code="MISSING_DATA",
            )
            return {"candidate_decision": decision}

        # --- Fraud escalation check (must match fraud_check_node threshold) ---
        if fraud_risk_score >= 0.5:
            decision = RefundDecision(
                kind=RefundDecisionKind.ESCALATE,
                amount_usd=0.0,
                reason_summary=f"Fraud risk score {fraud_risk_score:.2f} exceeds threshold.",
                escalation_code="FRAUD_RISK_HIGH",
            )
            return {"candidate_decision": decision}

        # --- Gather eligibility results ---
        rw_output = _get_tool_output(tool_invocations, "check_return_window")
        ic_output = _get_tool_output(tool_invocations, "check_item_condition")

        within_window: bool = True
        item_condition: str = "new_unopened"
        eligibility: str = "full_refund"

        if rw_output:
            within_window = rw_output.get("within_window", True)
        if ic_output:
            item_condition = ic_output.get("condition", "new_unopened")
            eligibility = ic_output.get("eligibility", "full_refund")

        # --- Compute refund amount ---
        ca_tool = get_tool_by_name("compute_refund_amount")
        if ca_tool is not None:
            ca_result = await run_tool(
                ca_tool,
                {
                    "order": order.model_dump(),
                    "customer": customer.model_dump(),
                    "within_window": within_window,
                    "item_condition": item_condition,
                    "eligibility": eligibility,
                },
                conversation_id=cid,
            )
            tool_invocations.append({
                "tool_name": "compute_refund_amount",
                "input": {"order_id": order.order_id, "within_window": within_window},
                "output": ca_result.get("output"),
                "error": ca_result.get("error_code"),
                "latency_ms": ca_result.get("latency_ms", 0.0),
            })

            if ca_result["ok"] and ca_result["output"]:
                out = ca_result["output"]
                kind_raw = out.get("kind", "approve_full")
                kind = RefundDecisionKind(kind_raw) if isinstance(kind_raw, str) else kind_raw
                amount = out.get("amount_usd", 0.0)
                cited = list(out.get("cited_clauses", []))
            else:
                kind = RefundDecisionKind.ESCALATE
                amount = 0.0
                cited = []
        else:
            kind = RefundDecisionKind.APPROVE_FULL if within_window else RefundDecisionKind.DENY
            amount = order.total_usd if within_window else 0.0
            cited = []

        # Augment cited_clause_ids with the return-window clause from rw_output
        if rw_output and rw_output.get("applied_clause"):
            # applied_clause may be like "POLICY-002" or "POLICY-002 + POLICY-010"
            rw_clause_str = rw_output["applied_clause"]
            for part in rw_clause_str.split("+"):
                clause_id = part.strip()
                if clause_id and clause_id not in cited:
                    cited.append(clause_id)

        # Determine auto-approval cap (POLICY-012)
        cap = customer.auto_approval_cap_usd

        requires_approval = (
            kind in (RefundDecisionKind.APPROVE_FULL, RefundDecisionKind.APPROVE_PARTIAL)
            and amount > cap
        )

        decision = RefundDecision(
            kind=kind,
            amount_usd=amount,
            reason_summary=(
                f"Refund computed: {kind.value}, ${amount:.2f}. "
                f"Within window: {within_window}. "
                f"Condition: {item_condition}."
            ),
            cited_clause_ids=cited,
            requires_human_approval=requires_approval,
        )

        return {
            "candidate_decision": decision,
            "tool_invocations": tool_invocations,
        }
