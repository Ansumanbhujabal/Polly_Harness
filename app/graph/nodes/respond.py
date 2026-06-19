"""Node: respond — generates the final response_text for the customer."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.domain.models import AgentState, RefundDecisionKind
from app.graph.nodes._events import async_node_scope

logger = logging.getLogger(__name__)


CONVERSATIONAL_SYSTEM_PROMPT = """You are the customer-facing voice of a refund-decision AI agent.

Your job in this turn is to answer a customer's CONVERSATIONAL message — a question, a complaint, or a follow-up — using ONLY the CRM context the harness has loaded for you. You are NOT in the refund-decision pipeline right now; another node handles that for actual refund requests.

Your scope and limits:
- You can answer questions about your role, capabilities, the customer's loaded order, the customer's approval cap, and your refund policy.
- You can acknowledge a complaint about your tone or escalation with empathy.
- You CANNOT issue, approve, or deny a refund here. If the customer wants a refund decision, tell them to phrase it as a refund request (e.g. "I want to return ORD-XXXX because …").
- Never invent customer or order details that aren't in the CRM JSON below. If a field is missing, say so.
- Be direct and human. No corporate filler. No "I'm sorry for the inconvenience" boilerplate.
- 1-3 short sentences. No emoji.

You will be given a JSON block describing the loaded customer + order + intent, and the customer's message. Reply with only the customer-facing text. No JSON, no labels.
"""


async def _compose_conversational_response(state: AgentState, llm: BaseLanguageModel | None) -> str:
    """Use the LLM to compose an answer for inquiry/complaint intents.

    The LLM gets the customer + order + intent as JSON context. No keyword
    pattern matching — this is the agent reasoning over its own CRM state.
    """
    # Pull the latest user message
    last_msg = ""
    for m in reversed(state.messages or []):
        if isinstance(m, dict) and m.get("role") == "user":
            last_msg = m.get("content") or ""
            break

    customer = state.customer
    order = state.order

    def _dump(o: Any) -> Any:
        if o is None:
            return None
        if hasattr(o, "model_dump"):
            return o.model_dump()
        return o

    context_payload = {
        "intent": state.intent or "inquiry",
        "customer": _dump(customer),
        "order": _dump(order),
    }

    if llm is None:
        # LLM not wired in — give a minimal honest reply instead of a templated lie.
        cust_name = (
            getattr(customer, "name", None)
            or (customer.get("name") if isinstance(customer, dict) else None)
            or None
        ) if customer else None
        greeting = f"Thanks{', ' + cust_name if cust_name else ''}."
        return (
            f"{greeting} I can look at your order, apply our refund policy, and tell you "
            f"what I can do (approve, deny with a cited clause, or route to a human). "
            f"What's the order ID and what's wrong with it?"
        )

    try:
        ctx_json = json.dumps(context_payload, default=str)
        response = await llm.ainvoke(
            [
                SystemMessage(content=CONVERSATIONAL_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Customer message: {last_msg}\n\n"
                        f"CRM context (JSON): {ctx_json}"
                    )
                ),
            ]
        )
        text = str(response.content).strip()
        if text:
            return text
    except Exception as exc:  # noqa: BLE001
        logger.warning("respond_node: conversational LLM call failed: %s", exc)

    return (
        "I can look at your loaded order, apply our refund policy, and tell you what "
        "I can do. What's the order ID and what's the issue?"
    )


def _humanize_deny_reason(internal: str) -> str:
    """Map internal reason_summary into a customer-facing sentence."""
    lower = internal.lower()
    if "delivered_digital" in lower or "digital" in lower:
        return "Digital downloads aren't covered by the refund policy once delivered"
    if "within window: false" in lower or "outside" in lower:
        return "The purchase is outside the return window"
    if "used" in lower or "opened" in lower:
        return "The item has been opened or used, so it doesn't qualify for a full refund"
    return "The order doesn't meet the conditions our policy requires for a refund"


async def respond_node(
    state: AgentState,
    llm: BaseLanguageModel | None = None,
) -> dict[str, Any]:
    """Generate the final customer-facing response.

    For conversational intents (inquiry, complaint, off_topic) the response is
    LLM-composed with the CRM context as input — no keyword routing. For
    decision-bearing intents the response is templated off the final_decision
    so it stays attributable + auditable.
    """
    cid: str = state.conversation_id or "unknown"

    async with async_node_scope("respond", cid):
        # response_text may be pre-composed THIS TURN by an upstream node
        # (escalate, _prepare_approval). Keep it. The chat API entrypoint
        # is responsible for clearing stale response_text from previous turns
        # before re-invoking, so a non-empty value here is from this turn.
        if state.response_text:
            return {}

        intent = state.intent or "inquiry"
        final_decision = state.final_decision

        if intent in ("inquiry", "complaint", "off_topic"):
            response = await _compose_conversational_response(state, llm)
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
                cited = final_decision.cited_clause_ids or []
                reason_human = _humanize_deny_reason(final_decision.reason_summary or "")
                clause_str = f" (policy {', '.join(cited[:2])})" if cited else ""
                response = (
                    f"I'm sorry — I can't approve this refund. {reason_human}{clause_str}. "
                    "If you think there's something specific I missed, reply here and I'll "
                    "route it to a human teammate."
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
