"""Judge: tone_appropriate.

LLM-based judge that reads state.response_text and scores:
  1.0 — professional, helpful, non-flippant, non-condescending
  0.0 — flippant, dismissive, condescending, or otherwise inappropriate

In test/offline mode (no Azure OpenAI configured), falls back to a simple
heuristic based on presence of known bad-tone markers.

Langfuse judge prompt name: "eval.tone_appropriate.v1"
"""

from __future__ import annotations

import logging
import os
import re

from app.domain.models import AgentState

def _attr(state, name, default=None):
    if isinstance(state, dict):
        return state.get(name, default)
    return getattr(state, name, default)

logger = logging.getLogger(__name__)

LANGFUSE_PROMPT_NAME = "eval.tone_appropriate.v1"

_SYSTEM_PROMPT = """You are a tone evaluator for a customer support AI agent.
Evaluate whether the agent's response is professionally appropriate.

A PASS (score=1) response:
- Is polite and empathetic
- Does not mock, belittle, or dismiss the customer
- Is not sarcastic or flippant
- Explains decisions clearly without being condescending
- Is professional even when denying a refund

A FAIL (score=0) response:
- Is rude, dismissive, or condescending
- Uses sarcastic or flippant language
- Talks down to the customer
- Is unprofessional in any way

Reply ONLY with "1" for PASS or "0" for FAIL."""

_USER_TEMPLATE = """Agent response to evaluate:

{response_text}

Is this response professionally appropriate? Reply ONLY with "1" (pass) or "0" (fail)."""

# Heuristic fallback — bad-tone markers
_BAD_TONE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\btoo\s+bad\b", re.IGNORECASE),
    re.compile(r"\bno\s+way\b", re.IGNORECASE),
    re.compile(r"\bget\s+lost\b", re.IGNORECASE),
    re.compile(r"\bwhatever\b", re.IGNORECASE),
    re.compile(r"\bnot\s+my\s+problem\b", re.IGNORECASE),
    re.compile(r"\byou\s+should\s+have\s+known\b", re.IGNORECASE),
    re.compile(r"\bobviously\b", re.IGNORECASE),
    re.compile(r"\bstupid\b", re.IGNORECASE),
    re.compile(r"\bidiot\b", re.IGNORECASE),
]


def _heuristic_tone_score(response_text: str) -> float:
    """Fallback heuristic when LLM is unavailable."""
    if not response_text or not response_text.strip():
        return 0.0
    for pattern in _BAD_TONE_PATTERNS:
        if pattern.search(response_text):
            logger.debug("tone_appropriate: bad-tone pattern matched → 0.0")
            return 0.0
    return 1.0


def _llm_tone_score(response_text: str) -> float:
    """Use Azure OpenAI to score tone (requires env vars)."""
    try:
        from langchain_openai import AzureChatOpenAI

        llm = AzureChatOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
            temperature=0,
            max_tokens=5,
        )
        prompt = _USER_TEMPLATE.format(response_text=response_text)
        response = llm.invoke([
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
        raw = response.content.strip()
        return 1.0 if raw.startswith("1") else 0.0
    except Exception as exc:  # noqa: BLE001
        logger.debug("tone_appropriate: LLM call failed, using heuristic: %s", exc)
        return _heuristic_tone_score(response_text)


def score(state, expected: dict) -> float:  # noqa: ARG001
    """Score response tone appropriateness. Accepts AgentState OR a dict.

    Uses LLM when Azure OpenAI is configured, heuristic fallback otherwise.
    """
    response_text = _attr(state, "response_text") or ""

    if not response_text.strip():
        logger.warning("tone_appropriate: empty response_text → 0.0")
        result = 0.0
    elif os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT"):
        result = _llm_tone_score(response_text)
    else:
        result = _heuristic_tone_score(response_text)

    logger.debug("tone_appropriate: score=%.1f", result)
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
        logger.debug("tone_appropriate: langfuse post failed (non-fatal): %s", exc)


def get_langfuse_judge_config() -> dict:
    """Return Langfuse judge config for this evaluator."""
    return {
        "name": LANGFUSE_PROMPT_NAME,
        "type": "llm",
        "model": os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
        "system_prompt": _SYSTEM_PROMPT,
        "user_prompt_template": _USER_TEMPLATE,
        "variables": ["response_text"],
    }
