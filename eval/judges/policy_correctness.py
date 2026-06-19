"""Judge: policy_correctness.

Score 1.0 if:
  - final_decision.kind matches expected_decision_kind, AND
  - every expected_cited_clause appears in final_decision.cited_clause_ids.

Score 0.0 otherwise.

Langfuse judge prompt name: "eval.policy_correctness.v1"
"""

from __future__ import annotations

import logging
import os

from app.domain.models import AgentState

# Runner serializes state to dict before passing to judges; helper unifies access.
def _attr(state, name, default=None):
    if isinstance(state, dict):
        return state.get(name, default)
    return getattr(state, name, default)

logger = logging.getLogger(__name__)

# Langfuse judge prompt name — registered once, stable across eval runs.
LANGFUSE_PROMPT_NAME = "eval.policy_correctness.v1"

_SYSTEM_PROMPT = """You are a strict policy-compliance evaluator for an AI refund agent.
Your job is to verify that the agent's final decision:
1. Matches the expected decision kind exactly.
2. Cites every required policy clause.

You receive the agent state and the expected outcome. Return ONLY "1" (pass) or "0" (fail).
"""

_USER_TEMPLATE = """Expected decision kind: {expected_decision_kind}
Expected cited clauses: {expected_cited_clauses}

Agent final decision kind: {actual_decision_kind}
Agent cited clause IDs: {actual_cited_clauses}

Does the agent's decision EXACTLY match the expected outcome (decision kind + all cited clauses)?
Reply ONLY with "1" for pass or "0" for fail."""


def score(state, expected: dict) -> float:
    """Score policy correctness deterministically (no LLM needed for binary check).

    Accepts AgentState OR a dict (the runner passes a serialized dict).
    """
    expected_kind = expected.get("expected_decision_kind", "")
    expected_clauses: list[str] = expected.get("expected_cited_clauses", [])

    final_decision = _attr(state, "final_decision")
    if final_decision is None:
        logger.warning("policy_correctness: no final_decision in state — scoring 0.0")
        return 0.0

    actual_kind = _attr(final_decision, "kind") or (final_decision.get("kind") if isinstance(final_decision, dict) else None)
    actual_kind_str = actual_kind.value if hasattr(actual_kind, "value") else str(actual_kind) if actual_kind else ""
    raw_clauses = _attr(final_decision, "cited_clause_ids") or (final_decision.get("cited_clause_ids") if isinstance(final_decision, dict) else []) or []
    actual_clauses = set(raw_clauses)

    kind_matches = actual_kind_str == expected_kind
    clauses_covered = all(c in actual_clauses for c in expected_clauses)

    result = 1.0 if (kind_matches and clauses_covered) else 0.0
    logger.debug(
        "policy_correctness: kind_matches=%s clauses_covered=%s score=%.1f",
        kind_matches,
        clauses_covered,
        result,
    )

    # Optional: post score to Langfuse when client is available.
    _try_post_to_langfuse(state, expected, result)

    return result


def _try_post_to_langfuse(state, expected: dict, result: float) -> None:
    """Post the judge score to Langfuse if the client is configured."""
    try:
        from app.observability import get_langfuse_client

        client = get_langfuse_client()
        if client is None:
            return
        client.score(
            name=LANGFUSE_PROMPT_NAME,
            value=result,
            trace_id=_attr(state, "conversation_id", "unknown"),
            comment=f"expected_kind={expected.get('expected_decision_kind')}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("policy_correctness: langfuse post failed (non-fatal): %s", exc)


def _build_llm_judge_prompt(state: AgentState, expected: dict) -> str:
    """Build the prompt for LLM-assisted scoring (used in future iterations)."""
    actual_kind = state.final_decision.kind if state.final_decision else "NONE"
    actual_kind_str = actual_kind.value if hasattr(actual_kind, "value") else str(actual_kind)
    actual_clauses = state.final_decision.cited_clause_ids if state.final_decision else []

    return _USER_TEMPLATE.format(
        expected_decision_kind=expected.get("expected_decision_kind", ""),
        expected_cited_clauses=expected.get("expected_cited_clauses", []),
        actual_decision_kind=actual_kind_str,
        actual_cited_clauses=actual_clauses,
    )


def get_langfuse_judge_config() -> dict:
    """Return the Langfuse judge YAML configuration for this evaluator."""
    return {
        "name": LANGFUSE_PROMPT_NAME,
        "type": "llm",
        "model": os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
        "system_prompt": _SYSTEM_PROMPT,
        "user_prompt_template": _USER_TEMPLATE,
        "variables": ["expected_decision_kind", "expected_cited_clauses", "actual_decision_kind", "actual_cited_clauses"],
    }
