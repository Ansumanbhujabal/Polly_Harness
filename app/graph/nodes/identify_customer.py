"""Node: identify_customer — resolves Customer and Order from CRM.

Uses state.customer and state.order if already set (injected by test or
multi-turn context). Otherwise, extracts identifiers from the latest
user message and calls the lookup_customer + get_order tools.

Identity mismatch: if the resolved order belongs to a different customer
than the one identified, sets state.intent = 'identity_mismatch' to trigger
the escalate edge.
"""

from __future__ import annotations

import re
from typing import Any

from app.domain.models import AgentState
from app.graph.nodes._events import async_node_scope
from app.tools import get_tool_by_name
from app.tools.executor import run_tool


async def identify_customer_node(state: AgentState) -> dict[str, Any]:
    """Identify the customer and order. Escalates on identity mismatch."""
    cid: str = state.conversation_id or "unknown"

    async with async_node_scope("identify_customer", cid):
        customer = state.customer
        order = state.order

        # If both are present, validate ownership
        if customer is not None and order is not None:
            if customer.customer_id != order.customer_id:
                return {"intent": "identity_mismatch"}
            return {}

        # Extract identifiers from the last user message
        messages = state.messages or []
        last_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                last_msg = msg.get("content", "")
                break

        # Extract order_id pattern
        order_id_match = re.search(r"(ORD-\d+)", last_msg, re.IGNORECASE)
        order_id = order_id_match.group(1).upper() if order_id_match else None

        # Extract email
        email_match = re.search(r"[\w.+-]+@[\w-]+\.\w+", last_msg)
        stated_email = email_match.group(0) if email_match else state.stated_email

        updates: dict[str, Any] = {}

        # Look up customer by email if no customer in state
        if customer is None and stated_email:
            lookup_tool = get_tool_by_name("lookup_customer")
            if lookup_tool is not None:
                result = await run_tool(
                    lookup_tool,
                    {"email": stated_email},
                    conversation_id=cid,
                )
                if result["ok"] and result["output"] and result["output"].get("customer"):
                    customer = result["output"]["customer"]
                    updates["customer"] = customer
                    updates["stated_email"] = stated_email

        # Look up order
        if order is None and order_id and customer is not None:
            get_order_tool = get_tool_by_name("get_order")
            if get_order_tool is not None:
                cust_id = (
                    customer.customer_id
                    if hasattr(customer, "customer_id")
                    else customer.get("customer_id", "")
                )
                result = await run_tool(
                    get_order_tool,
                    {"order_id": order_id, "customer_id": cust_id},
                    conversation_id=cid,
                )
                if result["ok"] and result["output"]:
                    order_data = result["output"].get("order")
                    if order_data is None:
                        # Mismatch — order exists but belongs to different customer
                        updates["intent"] = "identity_mismatch"
                    else:
                        updates["order"] = order_data

        return updates
