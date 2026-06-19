"""Node: classify_intent — classifies the user's intent from the latest message.

If state.intent is already set (injected by test or prior turn), uses that.
Otherwise, asks the LLM to classify into one of:
  refund_request | exchange_request | inquiry | off_topic
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.domain.models import AgentState
from app.graph.nodes._events import async_node_scope
from app.instructions import load_skill_router_prompt


async def classify_intent_node(
    state: AgentState,
    llm: BaseLanguageModel,
) -> dict[str, Any]:
    """Classify user intent. Skips LLM if state.intent is pre-set."""
    cid: str = state.conversation_id or "unknown"

    async with async_node_scope("classify_intent", cid):
        # If intent already set (e.g. in tests or multi-turn), trust it
        if state.intent:
            return {"intent": state.intent}

        # Use LLM to classify
        messages = state.messages or []
        last_user_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                break
            elif hasattr(msg, "type") and msg.type == "human":
                last_user_msg = msg.content
                break

        if not last_user_msg:
            return {"intent": "inquiry"}

        try:
            system_prompt = load_skill_router_prompt()
        except Exception:
            system_prompt = (
                "Classify the user message as one of: "
                "refund_request, exchange_request, inquiry, off_topic. "
                "Reply with ONLY the classification label."
            )

        response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(
                    content=f"Classify this customer message: {last_user_msg}"
                ),
            ]
        )
        raw = str(response.content).strip().lower()

        # Map to canonical intent. Order matters — check the strongest signals
        # first. "return this" is a refund_request in our taxonomy (we use
        # refunds-and-returns interchangeably for the e-commerce policy).
        if "injection" in raw:
            intent = "injection_attempt"
        elif "refund" in raw or "return" in raw or "money back" in raw:
            intent = "refund_request"
        elif "exchange" in raw or "swap" in raw or "replace" in raw:
            intent = "exchange_request"
        elif "off_topic" in raw or "off-topic" in raw:
            intent = "off_topic"
        elif "complaint" in raw or "frustrat" in raw or "angry" in raw:
            intent = "complaint"
        else:
            # Defensive default: route through identify_customer rather than
            # short-circuiting to respond. Lets the policy layer make the
            # decision instead of the classifier guessing.
            intent = "refund_request"

        return {"intent": intent}
