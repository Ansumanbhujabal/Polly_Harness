"""Node: respond — generates the final response_text for the customer."""

from __future__ import annotations

from typing import Any

from app.domain.models import AgentState, RefundDecisionKind
from app.graph.nodes._events import async_node_scope


async def respond_node(state: AgentState) -> dict[str, Any]:
    """Generate the final customer-facing response."""
    cid: str = state.conversation_id or "unknown"

    async with async_node_scope("respond", cid):
        # If response_text already set (e.g. by escalate_node), keep it
        if state.response_text:
            return {}

        intent = state.intent or "inquiry"
        final_decision = state.final_decision

        if intent in ("off_topic",):
            response = (
                "I'm a customer support specialist focused on refund and order requests. "
                "I'm not able to help with that topic. "
                "If you have a question about a refund or return, I'm happy to assist!"
            )
        elif intent == "inquiry":
            response = (
                "Thank you for reaching out. "
                "I can help you with refund requests, return policies, and order status. "
                "Could you please provide more details about your request?"
            )
        elif final_decision is not None:
            kind = final_decision.kind
            kind_str = kind.value if hasattr(kind, "value") else str(kind)
            amount = final_decision.amount_usd

            if kind_str in ("approve_full", "approve_partial"):
                response = (
                    f"Your refund of ${amount:.2f} has been approved and processed. "
                    "Please allow 3-5 business days for the amount to appear on your statement."
                )
            elif kind_str == "approve_store_credit":
                response = (
                    f"We have applied ${amount:.2f} in store credit to your account. "
                    "This credit can be used on your next purchase."
                )
            elif kind_str == "deny":
                reason = final_decision.reason_summary or ""
                response = (
                    f"We are unable to process your refund request at this time. "
                    f"Reason: {reason}. "
                    "If you believe this is in error, please contact our support team."
                )
            else:
                response = (
                    "Your request has been received and is being processed. "
                    "A support agent will follow up with you shortly."
                )
        else:
            response = (
                "Thank you for contacting support. "
                "A member of our team will review your request shortly."
            )

        return {"response_text": response}
