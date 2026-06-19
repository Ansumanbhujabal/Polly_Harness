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


_QUERY_REWRITE_PROMPT = """You normalize raw customer chat messages so a downstream classifier and retriever can work reliably.

Apply ALL of these:
1. Fix typos (e.g. "polc" → "POLICY", "shipmnt" → "shipment", "tomro" → "tomorrow", "fkin" → "").
2. Expand chat abbreviations to standard English ("u" → "you", "r" → "are", "ur" → "your", "thx" → "thanks", "wat" → "what").
3. Normalize policy / order references to canonical form:
   - "polc 4", "policy 4", "rule four" → "POLICY-004"
   - "order 1001", "ORD 1001", "#1001" → "ORD-1001"
4. Keep the customer's intent and meaning exactly the same. Do NOT add facts or apologize.
5. Strip profanity but keep the underlying request.

Output ONLY the rewritten message. No quotes, no labels, no explanation. If the message is already clean, return it unchanged.

Raw message: {message}

Rewritten:"""


async def _rewrite_user_message(raw_msg: str, llm: BaseLanguageModel) -> str:
    """UltraDoc-inspired query rewriter — fix typos + normalize references.

    Single fast LLM call before the classifier sees the message. Falls back
    to the original on any error so the pipeline never breaks on rewrite
    failures.
    """
    if not raw_msg or len(raw_msg) > 800:
        # Don't waste a call on giant messages; classifier handles them as-is.
        return raw_msg
    try:
        response = await llm.ainvoke(
            [HumanMessage(content=_QUERY_REWRITE_PROMPT.format(message=raw_msg))]
        )
        rewritten = str(response.content).strip().strip('"').strip()
        if not rewritten:
            return raw_msg
        return rewritten
    except Exception:  # noqa: BLE001 — never let the rewriter break classification
        return raw_msg


async def classify_intent_node(
    state: AgentState,
    llm: BaseLanguageModel,
) -> dict[str, Any]:
    """Classify the user intent for THIS turn.

    Always re-classifies from the latest user message. The previous
    short-circuit on `state.intent` was unsafe under LangGraph's
    SqliteSaver — when a thread is resumed across turns, the previous
    turn's intent is replayed and the LLM is skipped, so every follow-up
    reuses the same decision-bearing intent and produces the same canned
    response. Tests inject intent via a different code path.
    """
    cid: str = state.conversation_id or "unknown"

    async with async_node_scope("classify_intent", cid):
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

        # UltraDoc-style: rewrite/normalize before classification so typos +
        # abbreviations ("polc 4", "u", "fkin") don't throw off the classifier.
        normalized_msg = await _rewrite_user_message(last_user_msg, llm)

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
                    content=f"Classify this customer message: {normalized_msg}"
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


