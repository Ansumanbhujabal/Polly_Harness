"""L9 Verification check #1 — Prompt injection detection.

Two-layer strategy:
1. Regex first (cheap, synchronous): covers literal injection patterns.
2. LLM-judge fallback (async, injectable stub for tests): catches paraphrased attempts.

The check accepts an optional `llm_judge` callable so unit tests never need a real LLM.
Default judge is a no-op pass (returns detected=False) for safety-in-tests posture.
"""

from __future__ import annotations

import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.domain.models import AgentState, VerificationCheck

CHECK_NAME = "injection_check"

# Compiled regex covering known literal injection patterns (SPEC §Injection check)
_INJECTION_REGEX = re.compile(
    r"(?i)"
    r"ignore\s+previous"
    r"|you are now"
    r"|system:"
    r"|disregard\s+(?:above|prior)"
    r"|act\s+as"
    r"|<\|system\|>"
)

LLMJudge = Callable[[str], Awaitable[dict[str, Any]]]


async def _default_llm_judge(message: str) -> dict[str, Any]:  # noqa: ARG001
    """No-op judge — used when no judge is injected. Passes everything."""
    return {"detected": False, "confidence": 0.0, "reason": "stub: no judge provided"}


async def check_injection(
    state: AgentState,
    *,
    llm_judge: LLMJudge | None = None,
) -> VerificationCheck:
    """Check whether the latest user message is a prompt-injection attempt.

    Returns a block-severity VerificationCheck if injection is detected.
    Never raises — all exceptions become a block-severity failure.
    """
    start = time.monotonic()
    try:
        if not state.messages:
            return VerificationCheck(
                check_name=CHECK_NAME,
                passed=True,
                detail="no messages to check",
                severity="block",
            )

        last_message = state.messages[-1]
        content: str = ""
        if isinstance(last_message, dict):
            content = str(last_message.get("content", ""))
        else:
            content = str(getattr(last_message, "content", ""))

        # Layer 1: regex
        match = _INJECTION_REGEX.search(content)
        if match:
            matched_text = match.group(0)
            return VerificationCheck(
                check_name=CHECK_NAME,
                passed=False,
                detail=f"injection pattern matched: '{matched_text}' in message",
                severity="block",
            )

        # Layer 2: LLM judge fallback
        judge = llm_judge or _default_llm_judge
        judge_result = await judge(content)
        detected: bool = bool(judge_result.get("detected", False))
        confidence: float = float(judge_result.get("confidence", 0.0))
        reason: str = str(judge_result.get("reason", ""))

        if detected and confidence >= 0.7:
            return VerificationCheck(
                check_name=CHECK_NAME,
                passed=False,
                detail=(
                    f"LLM judge detected injection: confidence={confidence:.2f}, reason={reason}"
                ),
                severity="block",
            )

        return VerificationCheck(
            check_name=CHECK_NAME,
            passed=True,
            detail="no injection pattern detected",
            severity="block",
        )

    except Exception as exc:  # noqa: BLE001
        return VerificationCheck(
            check_name=CHECK_NAME,
            passed=False,
            detail=f"check raised: {exc}",
            severity="block",
        )
