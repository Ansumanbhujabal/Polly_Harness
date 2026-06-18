"""L9 Verification check #6 — Tone appropriateness (warn severity).

LLM-judge: asserts the response is professional, non-confrontational, non-flippant.

Accepts an injectable `llm_judge` callable for deterministic unit testing.
Default judge is a no-op pass (returns appropriate=True) to keep tests safe.

This is warn severity: a tone failure surfaces a dashboard alert and Langfuse score
but does NOT block the pipeline.

Never raises — all exceptions become a warn-severity failure.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.domain.models import AgentState, VerificationCheck

CHECK_NAME = "tone_appropriateness_check"

LLMJudge = Callable[[str], Awaitable[dict[str, Any]]]


async def _default_llm_judge(response_text: str) -> dict[str, Any]:  # noqa: ARG001
    """No-op judge — used when no judge is injected. Passes everything."""
    return {
        "appropriate": True,
        "confidence": 1.0,
        "reason": "stub: no judge provided — defaulting to pass",
    }


async def check_tone_appropriateness(
    state: AgentState,
    *,
    llm_judge: LLMJudge | None = None,
) -> VerificationCheck:
    """LLM-judge check: assert the response is appropriately toned.

    Returns warn-severity failure if the judge flags the response as inappropriate.
    """
    try:
        response_text = state.response_text or ""

        if not response_text:
            return VerificationCheck(
                check_name=CHECK_NAME,
                passed=True,
                detail="no response_text — skip tone check",
                severity="warn",
            )

        judge = llm_judge or _default_llm_judge
        result = await judge(response_text)

        appropriate: bool = bool(result.get("appropriate", True))
        confidence: float = float(result.get("confidence", 0.0))
        reason: str = str(result.get("reason", ""))

        if not appropriate:
            return VerificationCheck(
                check_name=CHECK_NAME,
                passed=False,
                detail=f"tone judge flagged response: confidence={confidence:.2f}, reason={reason}",
                severity="warn",
            )

        return VerificationCheck(
            check_name=CHECK_NAME,
            passed=True,
            detail=f"tone judge approved: confidence={confidence:.2f}, reason={reason}",
            severity="warn",
        )

    except Exception as exc:  # noqa: BLE001
        return VerificationCheck(
            check_name=CHECK_NAME,
            passed=False,
            detail=f"check raised: {exc}",
            severity="warn",
        )
