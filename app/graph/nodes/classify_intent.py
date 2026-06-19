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

        # Map the LLM's label onto the canonical intent set. The prompt asks
        # for one word; this is a defensive lookup that tolerates trailing
        # punctuation or extra whitespace. Safety classes are checked first
        # because they MUST override the others (the LLM occasionally folds an
        # injection request into a nominal refund_request envelope).
        if "injection" in raw:
            intent = "injection_attempt"
        elif "emotional_pressure" in raw or "emotional pressure" in raw:
            intent = "emotional_pressure"
        elif "exchange" in raw:
            intent = "exchange_request"
        elif "refund_request" in raw:
            intent = "refund_request"
        elif "complaint" in raw:
            intent = "complaint"
        elif "off_topic" in raw or "off-topic" in raw:
            intent = "off_topic"
        elif "inquiry" in raw or "question" in raw:
            intent = "inquiry"
        else:
            # Ambiguous classification → default to inquiry (non-escalatory).
            # The prompt explicitly says: "If the intent is genuinely ambiguous
            # between inquiry and complaint, prefer inquiry."
            intent = "inquiry"

        return {"intent": intent}


