"""L9 Verification check #5 — PII leak detection (warn severity).

Asserts that state.response_text does NOT contain the unredacted email or phone
number of the customer.

This is warn severity: a PII leak is logged and surfaced in the dashboard but does
NOT block the pipeline. The agent may have mentioned the email as part of a
confirmation message — warn gives the human reviewer visibility without blocking
legitimate confirmations that cite partial info.

Never raises — all exceptions become a warn-severity failure.
"""

from __future__ import annotations

from app.domain.models import AgentState, VerificationCheck

CHECK_NAME = "pii_leak_check"


async def check_pii_leak(state: AgentState) -> VerificationCheck:
    """Check if the response text leaks unredacted customer PII.

    Returns warn-severity failure if the customer's email or phone appears verbatim
    in the response text.
    """
    try:
        response_text = state.response_text or ""
        customer = state.customer

        if customer is None:
            return VerificationCheck(
                check_name=CHECK_NAME,
                passed=True,
                detail="no customer in state — skip PII check",
                severity="warn",
            )

        leaked_fields: list[str] = []

        if customer.email and customer.email in response_text:
            leaked_fields.append(f"email={customer.email!r}")

        if customer.phone and customer.phone in response_text:
            leaked_fields.append(f"phone={customer.phone!r}")

        if leaked_fields:
            return VerificationCheck(
                check_name=CHECK_NAME,
                passed=False,
                detail=f"PII found in response_text: {', '.join(leaked_fields)}",
                severity="warn",
            )

        return VerificationCheck(
            check_name=CHECK_NAME,
            passed=True,
            detail="no unredacted PII detected in response_text",
            severity="warn",
        )

    except Exception as exc:  # noqa: BLE001
        return VerificationCheck(
            check_name=CHECK_NAME,
            passed=False,
            detail=f"check raised: {exc}",
            severity="warn",
        )
