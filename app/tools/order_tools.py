"""L3 Tool: get_order.

Fetches an order by order_id, verifying it belongs to the given customer_id.
Returns None on mismatch — this is the IDENTITY_MISMATCH precursor guard.
"""

from __future__ import annotations

from typing import Optional

from app.domain.models import LayerName, Order
from app.observability.layer_event_emitter import get_emitter
from app.tools.base import BaseTool


class GetOrder(BaseTool):
    """Fetch an order by order_id, scoped to a specific customer.

    The customer_id scope is a security gate: if the order exists but belongs to
    a different customer, None is returned. The caller (graph orchestration) is
    responsible for escalating with reason code IDENTITY_MISMATCH.
    """

    name = "get_order"
    description = (
        "Retrieve an order record by order_id, verifying it belongs to the specified customer_id. "
        "Returns the full Order object, or None if the order is not found or belongs to a "
        "different customer. A None result on a mismatch should trigger IDENTITY_MISMATCH escalation."
    )

    def __init__(self, orders: list[Order]) -> None:
        self._orders = orders

    class Input(BaseTool.Input):
        order_id: str
        customer_id: str

    class Output(BaseTool.Output):
        order: Optional[Order] = None

    async def run(self, input: "GetOrder.Input") -> "GetOrder.Output":  # noqa: A002
        emitter = get_emitter()

        order = next((o for o in self._orders if o.order_id == input.order_id), None)

        if order is not None and order.customer_id != input.customer_id:
            # Exists but belongs to a different customer — mismatch
            emitter.emit(
                conversation_id="unknown",
                layer=LayerName.TOOLS,
                event_type="tool_invoked",
                payload={
                    "tool": self.name,
                    "order_id": input.order_id,
                    "mismatch": True,
                },
            )
            return self.Output(order=None)

        emitter.emit(
            conversation_id="unknown",
            layer=LayerName.TOOLS,
            event_type="tool_invoked",
            payload={
                "tool": self.name,
                "order_id": input.order_id,
                "found": order is not None,
            },
        )

        return self.Output(order=order)
