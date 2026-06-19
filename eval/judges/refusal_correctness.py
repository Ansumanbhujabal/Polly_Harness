"""Judge: refusal_correctness.

LLM-as-judge for axis A2.

A refusal response PASSES when it:
  (a) acknowledges the customer's request,
  (b) cites the correct reason for refusal,
  (c) offers a legitimate alternative (store credit, exchange, or escalation).

Structured LLM output (JSON):
  {"acknowledges": bool, "cites_reason": bool, "offers_alternative": bool,
   "alternatives_listed": [...]}

Pass = all three booleans are true.
Score = fraction of true values (0.33, 0.67, or 1.0) when partial; 0.0 when all fail.

Langfuse judge prompt name: "eval.refusal_correctness.v1"
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from app.domain.models import AgentState

logger = logging.getLogger(__name__)

LANGFUSE_PROMPT_NAME = "eval.refusal_correctness.v1"

_SYSTEM_PROMPT = """You are a refusal-quality evaluator for an AI refund agent.

You will receive:
- The agent's response text
- The expected reason for refusal (from the ground-truth record)

Evaluate whether the refusal is well-formed on three independent dimensions:
1. acknowledges: Does the response clearly acknowledge the customer's request
   (e.g., "I understand you're requesting a refund for...")?
2. cites_reason: Does the response cite the correct reason for the refusal
   (matching or semantically equivalent to the expected_reason_code)?
3. offers_alternative: Does the response offer at least one legitimate alternative
   (store credit, exchange, escalation to human, or future eligibility)?

Reply ONLY with valid JSON, no prose, no markdown fences:
{"acknowledges": true/false, "cites_reason": true/false, "offers_alternative": true/false, "alternatives_listed": ["..."]}
"""

_USER_TEMPLATE = """Expected reason code: {expected_reason_code}

Agent response:
{response_text}

Evaluate and return ONLY the JSON object."""


def _parse_llm_response(raw: str) -> dict[str, Any]:
    """Parse structured JSON from the LLM judge, tolerating minor formatting."""
    raw = raw.strip()
    # Strip accidental markdown fences
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(
            ln for ln in lines if not ln.startswith("```")
        ).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("refusal_correctness: failed to parse LLM JSON: %r", raw)
        return {}


def _llm_score(
    response_text: str,
    expected_reason_code: str,
    llm: Any,
) -> dict[str, Any]:
    """Invoke the LLM judge and return its structured output."""
    prompt = _USER_TEMPLATE.format(
        expected_reason_code=expected_reason_code,
        response_text=response_text,
    )
    result = llm.invoke([
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    raw = result.content if hasattr(result, "content") else str(result)
    return _parse_llm_response(raw)


def _build_llm(deployment: str | None = None) -> Any:
    """Lazily create an AzureChatOpenAI instance for LLM judging."""
    from langchain_openai import AzureChatOpenAI

    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        azure_deployment=deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT_CHAT", "gpt-4o"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        temperature=0,
        max_tokens=256,
    )


def score(state: AgentState | dict, expected: dict, *, llm: Any = None) -> dict:
    """Score refusal correctness using an LLM judge.

    Returns {"score": float, "passed": bool, "reason": str, "metadata": {...}}.

    state: AgentState (or dict projection) from a completed run.
    expected: ground-truth record; must contain "expected_reason_code".
    llm: optional injectable LLM; if None, creates one lazily via AzureChatOpenAI.
    """
    # Normalise state
    if isinstance(state, dict):
        response_text = state.get("response_text") or ""
        conversation_id = state.get("conversation_id", "unknown")
    else:
        response_text = state.response_text or ""
        conversation_id = state.conversation_id

    expected_reason_code = expected.get("expected_reason_code", "")

    if not response_text.strip():
        logger.warning("refusal_correctness: empty response_text — scoring 0.0 (conv=%s)", conversation_id)
        return {
            "score": 0.0,
            "passed": False,
            "reason": "Agent produced no response text; cannot evaluate refusal quality.",
            "metadata": {"acknowledges": False, "cites_reason": False, "offers_alternative": False},
        }

    # Obtain LLM (injectable for tests; lazy Azure init otherwise)
    if llm is None:
        try:
            llm = _build_llm()
        except Exception as exc:
            logger.warning("refusal_correctness: cannot build LLM (%s) — scoring 0.0", exc)
            return {
                "score": 0.0,
                "passed": False,
                "reason": f"LLM unavailable: {exc}",
                "metadata": {},
            }

    try:
        parsed = _llm_score(response_text, expected_reason_code, llm)
    except Exception as exc:
        logger.warning("refusal_correctness: LLM invocation failed (%s) — scoring 0.0", exc)
        return {
            "score": 0.0,
            "passed": False,
            "reason": f"LLM call failed: {exc}",
            "metadata": {},
        }

    acknowledges = bool(parsed.get("acknowledges", False))
    cites_reason = bool(parsed.get("cites_reason", False))
    offers_alternative = bool(parsed.get("offers_alternative", False))
    alternatives_listed: list[str] = parsed.get("alternatives_listed", [])

    passed = acknowledges and cites_reason and offers_alternative
    # Partial credit: fraction of three checks that are true
    score_val = round(sum([acknowledges, cites_reason, offers_alternative]) / 3, 4)

    reason_parts = []
    if not acknowledges:
        reason_parts.append("response does not acknowledge the customer's request")
    if not cites_reason:
        reason_parts.append(f"response does not cite expected reason '{expected_reason_code}'")
    if not offers_alternative:
        reason_parts.append("response offers no alternative (store credit / exchange / escalation)")
    reason = "; ".join(reason_parts) if reason_parts else "all three refusal quality criteria met"

    logger.debug(
        "refusal_correctness: acknowledges=%s cites_reason=%s offers_alternative=%s score=%.4f (conv=%s)",
        acknowledges,
        cites_reason,
        offers_alternative,
        score_val,
        conversation_id,
    )

    result_payload = {
        "score": score_val,
        "passed": passed,
        "reason": reason,
        "metadata": {
            "acknowledges": acknowledges,
            "cites_reason": cites_reason,
            "offers_alternative": offers_alternative,
            "alternatives_listed": alternatives_listed,
            "expected_reason_code": expected_reason_code,
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
        logger.debug("refusal_correctness: langfuse post failed (non-fatal): %s", exc)


def get_langfuse_judge_config() -> dict:
    """Return the Langfuse judge YAML configuration for this evaluator."""
    return {
        "name": LANGFUSE_PROMPT_NAME,
        "type": "llm",
        "model": os.getenv("AZURE_OPENAI_DEPLOYMENT_CHAT", "gpt-4o"),
        "system_prompt": _SYSTEM_PROMPT,
        "user_prompt_template": _USER_TEMPLATE,
        "variables": ["expected_reason_code", "response_text"],
    }
