"""L9 Verification check #2 — Policy assertion: return window clause.

Asserts that the cited clause IDs include the policy that governs the return window for
this customer's tier:
- Standard customers → POLICY-001 (14-day window)
- VIP customers → POLICY-002 (60-day window)

If a VIP customer's decision cites only POLICY-001 (the standard clause), that is a
block: the agent is applying the wrong policy to this customer.

Never raises — all exceptions become a block-severity failure.
"""

from __future__ import annotations

import time

from app.domain.models import AgentState, CustomerTier, VerificationCheck

CHECK_NAME = "policy_assertion_return_window"

# Map tier → required clause for the return window decision
_TIER_TO_REQUIRED_CLAUSE: dict[str, str] = {
    CustomerTier.VIP.value: "POLICY-002",
    CustomerTier.PREMIUM.value: "POLICY-001",  # premium uses standard 14d window
    CustomerTier.STANDARD.value: "POLICY-001",
}


async def check_policy_assertion_return_window(state: AgentState) -> VerificationCheck:
    """Assert the cited clause matches the customer's tier return window.

    Returns block-severity failure if the wrong policy clause was cited.
    """
    try:
        if state.customer is None:
            return VerificationCheck(
                check_name=CHECK_NAME,
                passed=False,
                detail="no customer in state — cannot validate return window clause",
                severity="block",
            )

        if state.candidate_decision is None:
            return VerificationCheck(
                check_name=CHECK_NAME,
                passed=True,
                detail="no candidate decision — skip return window assertion",
                severity="block",
            )

        tier_value: str = (
            state.customer.tier.value
            if hasattr(state.customer.tier, "value")
            else str(state.customer.tier)
        )
        required_clause = _TIER_TO_REQUIRED_CLAUSE.get(tier_value, "POLICY-001")
        cited = state.candidate_decision.cited_clause_ids

        if required_clause in cited:
            return VerificationCheck(
                check_name=CHECK_NAME,
                passed=True,
                detail=f"required clause {required_clause} present in cited_clause_ids={cited}",
                severity="block",
            )

        return VerificationCheck(
            check_name=CHECK_NAME,
            passed=False,
            detail=(
                f"tier={tier_value} requires clause {required_clause} "
                f"but cited_clause_ids={cited} does not include it"
            ),
            severity="block",
        )

    except Exception as exc:  # noqa: BLE001
        return VerificationCheck(
            check_name=CHECK_NAME,
            passed=False,
            detail=f"check raised: {exc}",
            severity="block",
        )
