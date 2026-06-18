"""L9 Verification check #3 — Policy assertion: amount cap (POLICY-012).

Asserts:
    decision.amount_usd ≤ customer.auto_approval_cap_usd
    OR decision.requires_human_approval is True

If the amount exceeds the cap AND requires_human_approval is False, this is a block:
the agent is about to autonomously issue a refund it is not authorised to issue.

Never raises — all exceptions become a block-severity failure.
"""

from __future__ import annotations

from app.domain.models import AgentState, VerificationCheck

CHECK_NAME = "policy_assertion_amount"


async def check_policy_assertion_amount(state: AgentState) -> VerificationCheck:
    """Assert refund amount is within cap or human approval is required.

    Returns block-severity failure if amount exceeds cap without approval flag.
    """
    try:
        if state.customer is None:
            return VerificationCheck(
                check_name=CHECK_NAME,
                passed=False,
                detail="no customer in state — cannot validate amount cap",
                severity="block",
            )

        if state.candidate_decision is None:
            return VerificationCheck(
                check_name=CHECK_NAME,
                passed=True,
                detail="no candidate decision — skip amount assertion",
                severity="block",
            )

        cap = state.customer.auto_approval_cap_usd
        amount = state.candidate_decision.amount_usd
        requires_approval = state.candidate_decision.requires_human_approval

        if amount <= cap or requires_approval:
            return VerificationCheck(
                check_name=CHECK_NAME,
                passed=True,
                detail=(
                    f"amount={amount:.2f} cap={cap:.2f} "
                    f"requires_human_approval={requires_approval} — OK"
                ),
                severity="block",
            )

        return VerificationCheck(
            check_name=CHECK_NAME,
            passed=False,
            detail=(
                f"amount_usd={amount:.2f} exceeds auto_approval_cap_usd={cap:.2f} "
                f"and requires_human_approval=False — POLICY-012 violation"
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
