"""L6 Orchestration — conditional edge functions.

ALL functions here are PURE: no I/O, no LLM calls, no side effects.
They receive an AgentState object and return the next node name as a string.

These are used as conditional_edge routing functions in refund_graph.py.
"""

from __future__ import annotations

from typing import Literal

from app.domain.models import AgentState, RefundDecisionKind


# ---------------------------------------------------------------------------
# Edge: classify_intent → {identify_customer | respond}
# ---------------------------------------------------------------------------

def route_after_classify_intent(
    state: AgentState,
) -> Literal["identify_customer", "respond", "escalate"]:
    """Branch out of classify_intent.

    - Conversational intents (off_topic, inquiry, complaint) → respond.
      They're not refund actions, so they MUST NOT enter the eligibility /
      fraud / decision pipeline.
    - Safety classes (injection_attempt, emotional_pressure) → escalate.
      Per the intent_classifier prompt: refunds-under-pressure undermine
      policy integrity, so these always route to a human regardless of
      eligibility. The graph treats this as a non-negotiable invariant —
      not a heuristic.
    - Everything else → identify_customer (the normal refund path).
    """
    intent = state.intent or "refund_request"
    if intent in ("off_topic", "inquiry", "complaint"):
        return "respond"
    if intent in ("emotional_pressure", "injection_attempt"):
        return "escalate"
    return "identify_customer"


# ---------------------------------------------------------------------------
# Edge: identify_customer → {retrieve_policy | escalate}
# ---------------------------------------------------------------------------

def route_after_identify_customer(
    state: AgentState,
) -> Literal["retrieve_policy", "escalate"]:
    """Identity mismatch → escalate; otherwise → retrieve_policy."""
    if state.intent == "identity_mismatch":
        return "escalate"
    return "retrieve_policy"


# ---------------------------------------------------------------------------
# Edge: compute_decision → {verification | escalate}
# ---------------------------------------------------------------------------

def route_after_compute_decision(
    state: AgentState,
) -> Literal["verification", "escalate"]:
    """If compute_decision produced an immediate escalation, skip verification."""
    candidate = state.candidate_decision
    if candidate is not None:
        kind = candidate.kind
        kind_str = kind.value if hasattr(kind, "value") else str(kind)
        if kind_str == RefundDecisionKind.ESCALATE.value:
            return "escalate"
    return "verification"


# ---------------------------------------------------------------------------
# Edge: verification → {issue_refund_node | await_human_approval | escalate}
# ---------------------------------------------------------------------------

def route_after_verification(
    state: AgentState,
) -> Literal["issue_refund_node", "await_human_approval", "escalate"]:
    """
    - blocked verification → escalate
    - verified + requires_human_approval → await_human_approval
    - verified + within cap → issue_refund_node
    """
    # Blocked verification → escalate (fail-closed)
    if state.verification is not None and state.verification.blocked:
        return "escalate"

    candidate = state.candidate_decision
    if candidate is not None:
        kind = candidate.kind
        kind_str = kind.value if hasattr(kind, "value") else str(kind)

        # Explicit escalate kind
        if kind_str == RefundDecisionKind.ESCALATE.value:
            return "escalate"

        # Requires human approval (above cap, verified OK)
        if candidate.requires_human_approval:
            return "await_human_approval"

    return "issue_refund_node"


# ---------------------------------------------------------------------------
# Edge: await_human_approval → {issue_refund_node | escalate}
# ---------------------------------------------------------------------------

def route_after_human_approval(
    state: AgentState,
) -> Literal["issue_refund_node", "escalate"]:
    """approved → issue_refund_node; denied → escalate."""
    if state.approval_resolution == "approved":
        return "issue_refund_node"
    return "escalate"
