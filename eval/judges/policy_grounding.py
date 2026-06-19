"""Judge: policy_grounding.

Deterministic refinement of policy_correctness for axis A1.

Catches a failure mode that policy_correctness cannot detect on its own:
the LLM cited a clause ID that *sounds* plausible but was never retrieved
from the policy vector store in this run.

Two independent signals:

  SIGNAL-1  Coverage: every clause listed in expected.expected_cited_clauses
             appears in state.final_decision.cited_clause_ids.

  SIGNAL-2  Grounding: every clause cited by the agent appears in
             state.relevant_clauses[*].clause_id (i.e., it was actually
             retrieved, not hallucinated by the LLM).

Score = jaccard(expected_clauses, actual_cited_clauses)
          × (1.0 if all cited clauses were retrieved else 0.5)

Where jaccard = |intersection| / |union|.
The 0.5 multiplier is a grounding penalty — a correct-looking citation that
was never retrieved is half as trustworthy as one that was.

Pass = score >= 0.9.

When expected_cited_clauses is empty (e.g., refusal / escalation cases),
the judge trivially passes (no clause to verify).

Langfuse judge prompt name: "eval.policy_grounding.v1"
"""

from __future__ import annotations

import logging
from typing import Any

from app.domain.models import AgentState

logger = logging.getLogger(__name__)

LANGFUSE_PROMPT_NAME = "eval.policy_grounding.v1"
PASS_THRESHOLD: float = 0.9


def _jaccard(set_a: set[str], set_b: set[str]) -> float:
    """Jaccard similarity: |intersection| / |union|. Returns 1.0 when both sets empty."""
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 1.0
    return len(set_a & set_b) / len(union)


def score(state: AgentState | dict, expected: dict, *, llm: Any = None) -> dict:  # noqa: ARG001
    """Score policy clause grounding deterministically (no LLM needed).

    Returns {"score": float, "passed": bool, "reason": str, "metadata": {...}}.

    state: AgentState (or dict projection) from a completed run.
    expected: ground-truth record; "expected_cited_clauses" drives this judge.
    llm: ignored (deterministic judge; parameter kept for interface parity).
    """
    # Normalise state
    if isinstance(state, AgentState):
        conversation_id = state.conversation_id
        final_decision = state.final_decision
        relevant_clauses = state.relevant_clauses
    else:
        conversation_id = state.get("conversation_id", "unknown")
        final_decision = state.get("final_decision")
        relevant_clauses = state.get("relevant_clauses", [])

    expected_clauses: set[str] = set(expected.get("expected_cited_clauses", []))

    # Trivial pass: no clauses expected (refusal / escalation cases)
    if not expected_clauses:
        logger.debug(
            "policy_grounding: no expected clauses — trivial pass (conv=%s)", conversation_id
        )
        result_payload = {
            "score": 1.0,
            "passed": True,
            "reason": "No expected clauses; grounding check not applicable for this case.",
            "metadata": {
                "expected_clauses": [],
                "actual_cited": [],
                "retrieved_clause_ids": [],
                "jaccard": 1.0,
                "grounding_penalty_applied": False,
            },
        }
        _try_post_to_langfuse(state, 1.0, conversation_id)
        return result_payload

    # Extract actual cited clauses from the decision
    if final_decision is None:
        actual_cited: set[str] = set()
    elif hasattr(final_decision, "cited_clause_ids"):
        actual_cited = set(final_decision.cited_clause_ids)
    else:
        actual_cited = set(final_decision.get("cited_clause_ids", []))

    # Extract retrieved clause IDs from state.relevant_clauses
    retrieved_ids: set[str] = set()
    for clause in relevant_clauses:
        if hasattr(clause, "clause_id"):
            retrieved_ids.add(clause.clause_id)
        elif isinstance(clause, dict):
            cid = clause.get("clause_id")
            if cid:
                retrieved_ids.add(cid)

    # SIGNAL-1: Jaccard between expected and actual cited clauses
    jaccard_val = _jaccard(expected_clauses, actual_cited)

    # SIGNAL-2: Grounding check — any cited clause not in retrieved set is hallucinated
    ungrounded = actual_cited - retrieved_ids
    grounding_penalty = 0.5 if ungrounded else 1.0

    score_val = round(jaccard_val * grounding_penalty, 4)
    passed = score_val >= PASS_THRESHOLD

    # Build reason string
    parts: list[str] = []
    missing_from_actual = expected_clauses - actual_cited
    extra_in_actual = actual_cited - expected_clauses

    if missing_from_actual:
        parts.append(f"expected clauses not cited: {sorted(missing_from_actual)}")
    if extra_in_actual:
        parts.append(f"extra clauses cited beyond expected: {sorted(extra_in_actual)}")
    if ungrounded:
        parts.append(
            f"cited clauses not in retrieved set (hallucinated?): {sorted(ungrounded)}"
        )
    reason = "; ".join(parts) if parts else "all cited clauses match expected and are grounded"

    logger.debug(
        "policy_grounding: jaccard=%.4f grounding_penalty=%.1f score=%.4f (conv=%s)",
        jaccard_val,
        grounding_penalty,
        score_val,
        conversation_id,
    )
    if ungrounded:
        logger.warning(
            "policy_grounding: ungrounded clause IDs in conv=%s: %s",
            conversation_id,
            sorted(ungrounded),
        )

    result_payload = {
        "score": score_val,
        "passed": passed,
        "reason": reason,
        "metadata": {
            "expected_clauses": sorted(expected_clauses),
            "actual_cited": sorted(actual_cited),
            "retrieved_clause_ids": sorted(retrieved_ids),
            "missing_from_actual": sorted(missing_from_actual),
            "extra_in_actual": sorted(extra_in_actual),
            "ungrounded_citations": sorted(ungrounded),
            "jaccard": jaccard_val,
            "grounding_penalty_applied": bool(ungrounded),
            "grounding_multiplier": grounding_penalty,
        },
    }

    _try_post_to_langfuse(state, score_val, conversation_id)
    return result_payload


def _try_post_to_langfuse(
    state: AgentState | dict, result: float, conversation_id: str
) -> None:
    try:
        from app.observability import get_langfuse_client

        client = get_langfuse_client()
        if client is None:
            return
        client.score(
            name=LANGFUSE_PROMPT_NAME,
            value=result,
            trace_id=conversation_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("policy_grounding: langfuse post failed (non-fatal): %s", exc)


def get_langfuse_judge_config() -> dict:
    """Return Langfuse judge config for this evaluator."""
    return {
        "name": LANGFUSE_PROMPT_NAME,
        "type": "heuristic",
        "description": (
            "Jaccard similarity between expected and actual cited clauses, "
            "multiplied by 0.5 grounding penalty when any cited clause was not "
            "in the retrieved set. Pass threshold: score >= 0.9."
        ),
    }
