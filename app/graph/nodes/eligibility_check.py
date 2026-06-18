"""Node: eligibility_check — runs check_return_window and check_item_condition tools."""

from __future__ import annotations

from typing import Any

from app.domain.models import AgentState
from app.graph.nodes._events import async_node_scope
from app.tools import get_tool_by_name
from app.tools.executor import run_tool


async def eligibility_check_node(state: AgentState) -> dict[str, Any]:
    """Run return-window and item-condition checks."""
    cid: str = state.conversation_id or "unknown"

    async with async_node_scope("eligibility_check", cid):
        customer = state.customer
        order = state.order

        if customer is None or order is None:
            return {}

        tool_invocations: list[Any] = list(state.tool_invocations or [])

        # --- check_return_window ---
        rw_tool = get_tool_by_name("check_return_window")
        if rw_tool is not None:
            rw_result = await run_tool(
                rw_tool,
                {
                    "order": order.model_dump(),
                    "customer": customer.model_dump(),
                },
                conversation_id=cid,
            )
            tool_invocations.append({
                "tool_name": "check_return_window",
                "input": {"order_id": order.order_id, "customer_id": customer.customer_id},
                "output": rw_result.get("output"),
                "error": rw_result.get("error_code"),
                "latency_ms": rw_result.get("latency_ms", 0.0),
            })

        # --- check_item_condition ---
        ic_tool = get_tool_by_name("check_item_condition")
        if ic_tool is not None:
            ic_result = await run_tool(
                ic_tool,
                {"order": order.model_dump()},
                conversation_id=cid,
            )
            tool_invocations.append({
                "tool_name": "check_item_condition",
                "input": {"order_id": order.order_id},
                "output": ic_result.get("output"),
                "error": ic_result.get("error_code"),
                "latency_ms": ic_result.get("latency_ms", 0.0),
            })

        return {"tool_invocations": tool_invocations}
