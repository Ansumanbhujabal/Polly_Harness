"""L3 Tool: lookup_customer.

Looks up a customer from the in-memory CRM list by customer_id or email.
If both are provided, customer_id takes precedence.
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from app.domain.models import Customer, LayerName
from app.observability.layer_event_emitter import get_emitter
from app.tools.base import BaseTool


class LookupCustomer(BaseTool):
    """Find a customer by customer_id OR by email (case-insensitive).

    Behaviour:
    - If both customer_id and email are provided, customer_id wins.
    - Returns None (not raises) when no match — caller decides whether that's an error.
    - Emits a L3_TOOLS/tool_invoked event (additional to what executor emits).
    """

    name = "lookup_customer"
    description = (
        "Find a customer record in the CRM by customer_id or email address. "
        "Returns the full Customer object or None if not found. "
        "When both identifiers are supplied, customer_id takes precedence. "
        "Email matching is case-insensitive."
    )

    def __init__(self, customers: list[Customer]) -> None:
        self._customers = customers

    class Input(BaseTool.Input):
        customer_id: Optional[str] = Field(None, description="CRM customer ID e.g. CUST-001")
        email: Optional[str] = Field(None, description="Customer email address")

    class Output(BaseTool.Output):
        customer: Optional[Customer] = None

    async def run(self, input: "LookupCustomer.Input") -> "LookupCustomer.Output":  # noqa: A002
        emitter = get_emitter()

        if input.customer_id:
            match = next(
                (c for c in self._customers if c.customer_id == input.customer_id),
                None,
            )
        elif input.email:
            needle = input.email.lower()
            match = next(
                (c for c in self._customers if c.email.lower() == needle),
                None,
            )
        else:
            match = None

        emitter.emit(
            conversation_id="unknown",
            layer=LayerName.TOOLS,
            event_type="tool_invoked",
            payload={
                "tool": self.name,
                "found": match is not None,
                "lookup_by": "id" if input.customer_id else "email",
            },
        )

        return self.Output(customer=match)
