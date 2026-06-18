"""L9 Verification pipeline — parallel runner, aggregator, incident emitter.

Public contract:
    async run_verification_pipeline(state: AgentState) -> VerificationResult

All 6 checks run concurrently via asyncio.gather. Total wall-clock = slowest check.
The pipeline is fail-closed: it never raises. Check exceptions are captured as
block-severity VerificationChecks.

Block semantics:
  - severity="block" AND passed=False → VerificationResult.blocked = True
  - incident written via app.learning.write_incident
  - event: L9_VERIFICATION / check_failed

Warn semantics:
  - severity="warn" AND passed=False → logged + Langfuse-scored (dashboard yellow chip)
  - NO incident written, pipeline continues
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.domain.models import AgentState, LayerName, VerificationCheck, VerificationResult
from app.observability import get_emitter
from app.verification.checks.hallucinated_refund_id_check import check_hallucinated_refund_id
from app.verification.checks.injection_check import check_injection
from app.verification.checks.pii_leak_check import check_pii_leak
from app.verification.checks.policy_assertion_amount import check_policy_assertion_amount
from app.verification.checks.policy_assertion_return_window import (
    check_policy_assertion_return_window,
)
from app.verification.checks.tone_appropriateness_check import check_tone_appropriateness


async def _run_check_with_events(
    coro: Any,
    check_name: str,
    conversation_id: str,
) -> VerificationCheck:
    """Wrap a check coroutine with check_started / check_passed / check_failed events."""
    emitter = get_emitter()

    emitter.emit(
        conversation_id=conversation_id,
        layer=LayerName.VERIFICATION,
        event_type="check_started",
        payload={"check_name": check_name, "conversation_id": conversation_id},
    )

    start = time.monotonic()
    try:
        result: VerificationCheck = await coro
    except Exception as exc:  # noqa: BLE001
        result = VerificationCheck(
            check_name=check_name,
            passed=False,
            detail=f"check raised: {exc}",
            severity="block",
        )

    latency_ms = (time.monotonic() - start) * 1000

    if result.passed:
        emitter.emit(
            conversation_id=conversation_id,
            layer=LayerName.VERIFICATION,
            event_type="check_passed",
            payload={
                "check_name": check_name,
                "conversation_id": conversation_id,
                "latency_ms": latency_ms,
            },
        )
    else:
        emitter.emit(
            conversation_id=conversation_id,
            layer=LayerName.VERIFICATION,
            event_type="check_failed",
            payload={
                "check_name": check_name,
                "detail": result.detail,
                "severity": result.severity,
                "conversation_id": conversation_id,
            },
        )

    return result


def _write_block_incident(check: VerificationCheck, state: AgentState) -> None:
    """Write an incident for a block-severity failure. Ignores all errors."""
    try:
        # Lazy import to respect monkeypatching in tests
        from app.learning.incident_logger import write_incident

        write_incident(
            triggered_by="verification_failure",
            layer=LayerName.VERIFICATION,
            summary=f"{check.check_name}: {check.detail}",
            detail={
                "check_name": check.check_name,
                "detail": check.detail,
                "severity": check.severity,
                "passed": check.passed,
            },
            conversation_id=state.conversation_id,
        )
    except Exception:  # noqa: BLE001
        pass


async def run_verification_pipeline(state: AgentState) -> VerificationResult:
    """Run all 6 verification checks in parallel and return the aggregated result.

    Never raises. Each check failure is captured as a VerificationCheck.
    Block-severity failures trigger incident emission.
    """
    conversation_id = state.conversation_id

    # Launch all 6 checks concurrently
    checks_and_names: list[tuple[Any, str]] = [
        (check_injection(state), "injection_check"),
        (check_policy_assertion_return_window(state), "policy_assertion_return_window"),
        (check_policy_assertion_amount(state), "policy_assertion_amount"),
        (check_hallucinated_refund_id(state), "hallucinated_refund_id_check"),
        (check_pii_leak(state), "pii_leak_check"),
        (check_tone_appropriateness(state), "tone_appropriateness_check"),
    ]

    wrapped = [
        _run_check_with_events(coro, name, conversation_id)
        for coro, name in checks_and_names
    ]

    results: list[VerificationCheck] = await asyncio.gather(*wrapped)

    # Aggregate
    verification_result = VerificationResult(checks=list(results))

    # Write incidents for every block-severity failure
    for check in results:
        if check.severity == "block" and not check.passed:
            _write_block_incident(check, state)

    # Emit pipeline_completed
    num_failures = sum(1 for c in results if not c.passed)
    get_emitter().emit(
        conversation_id=conversation_id,
        layer=LayerName.VERIFICATION,
        event_type="pipeline_completed",
        payload={
            "blocked": verification_result.blocked,
            "num_failures": num_failures,
            "conversation_id": conversation_id,
        },
    )

    return verification_result
