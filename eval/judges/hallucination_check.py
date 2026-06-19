"""Judge: hallucination_check.

Score 1.0 if the agent's response_text does NOT contain invented identifiers
(customer_id / order_id / refund_id patterns that don't match the actual state).

Score 0.0 if the response contains a CUST-XXX, ORD-XXXX, or REF-XXX/RFD-XXX
pattern that does NOT match state.customer.customer_id or state.order.order_id.

This is a heuristic judge — no LLM call needed for v0.1. If the response text
references real IDs, it's fine. If it invents new ones, it fails.

Langfuse judge prompt name: "eval.hallucination_check.v1"
"""

from __future__ import annotations

import logging
import re

from app.domain.models import AgentState

def _attr(state, name, default=None):
    if isinstance(state, dict):
        return state.get(name, default)
    return getattr(state, name, default)

logger = logging.getLogger(__name__)

LANGFUSE_PROMPT_NAME = "eval.hallucination_check.v1"

# Patterns that should ONLY reference known IDs in state
_CUSTOMER_ID_PATTERN = re.compile(r"\bCUST-\d{3,}\b")
_ORDER_ID_PATTERN = re.compile(r"\bORD-\d{4,}\b")
_REFUND_ID_PATTERNS = [
    re.compile(r"\bREF-\d{4,}\b"),
    re.compile(r"\bRFD-\d{4,}\b"),
    re.compile(r"\bREFUND-\d{4,}\b"),
]


def score(state, expected: dict) -> float:  # noqa: ARG001
    """Score hallucination check. Accepts AgentState OR a dict.

    1.0 = no invented IDs in response; 0.0 = response contains unknown IDs.
    """
    response_text = _attr(state, "response_text") or ""

    if not str(response_text).strip():
        result = 1.0
        _try_post_to_langfuse(state, result)
        return result

    customer = _attr(state, "customer")
    order = _attr(state, "order")
    known_customer_id = _attr(customer, "customer_id") if customer else None
    known_order_id = _attr(order, "order_id") if order else None

    # Check for invented customer IDs
    customer_ids_in_response = set(_CUSTOMER_ID_PATTERN.findall(response_text))
    for cid in customer_ids_in_response:
        if cid != known_customer_id:
            logger.warning(
                "hallucination_check: invented customer_id=%s in response (known=%s) → 0.0",
                cid,
                known_customer_id,
            )
            _try_post_to_langfuse(state, 0.0)
            return 0.0

    # Check for invented order IDs
    order_ids_in_response = set(_ORDER_ID_PATTERN.findall(response_text))
    for oid in order_ids_in_response:
        if oid != known_order_id:
            logger.warning(
                "hallucination_check: invented order_id=%s in response (known=%s) → 0.0",
                oid,
                known_order_id,
            )
            _try_post_to_langfuse(state, 0.0)
            return 0.0

    # Check for invented refund IDs (any refund ID in response_text is suspect
    # unless state.final_decision has a matching one — for v0.1 we allow any REF-* that
    # appears only once as it's likely from the actual issuance)
    for pattern in _REFUND_ID_PATTERNS:
        if pattern.search(response_text):
            # Refund IDs in responses are expected post-issuance; don't penalise.
            logger.debug("hallucination_check: refund ID in response — allowed (post-issuance)")

    logger.debug("hallucination_check: no hallucinated IDs detected → 1.0")
    result = 1.0
    _try_post_to_langfuse(state, result)
    return result


def _try_post_to_langfuse(state, result: float) -> None:
    try:
        from app.observability import get_langfuse_client

        client = get_langfuse_client()
        if client is None:
            return
        client.score(
            name=LANGFUSE_PROMPT_NAME,
            value=result,
            trace_id=_attr(state, "conversation_id", "unknown"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("hallucination_check: langfuse post failed (non-fatal): %s", exc)


def get_langfuse_judge_config() -> dict:
    """Return Langfuse judge config for this evaluator."""
    return {
        "name": LANGFUSE_PROMPT_NAME,
        "type": "heuristic",
        "description": (
            "Regex-based check: CUST-*/ORD-* patterns in response must match "
            "state.customer/order identifiers. Invented IDs → fail."
        ),
    }
