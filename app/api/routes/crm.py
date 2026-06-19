"""GET /api/v1/crm/context — return enriched customer+order context for the chat UI.

Returns the customer record + the order summary in one shot, so the chat
sidebar can render a CRM-style ticket without two round trips.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.tools import get_tool_by_name
from app.tools.executor import run_tool

router = APIRouter()


class CRMContextResponse(BaseModel):
    customer: dict[str, Any] | None
    order: dict[str, Any] | None


@router.get("/api/v1/crm/context")
async def get_crm_context(customer_id: str, order_id: str | None = None) -> CRMContextResponse:
    """Look up customer + (optional) order for the chat sidebar."""
    customer_payload = None
    order_payload = None

    lookup = get_tool_by_name("lookup_customer")
    if lookup is not None:
        r = await run_tool(lookup, {"customer_id": customer_id}, conversation_id="crm-context")
        if r["ok"] and r["output"] and r["output"].get("customer"):
            cust = r["output"]["customer"]
            customer_payload = cust.model_dump() if hasattr(cust, "model_dump") else dict(cust)

    if order_id and customer_payload:
        get_order = get_tool_by_name("get_order")
        if get_order is not None:
            r = await run_tool(
                get_order,
                {"order_id": order_id, "customer_id": customer_payload.get("customer_id", customer_id)},
                conversation_id="crm-context",
            )
            if r["ok"] and r["output"] and r["output"].get("order"):
                order = r["output"]["order"]
                order_payload = order.model_dump() if hasattr(order, "model_dump") else dict(order)

    if customer_payload is None:
        raise HTTPException(status_code=404, detail=f"customer {customer_id} not found")

    return CRMContextResponse(customer=customer_payload, order=order_payload)
