"""L9 Verification check #4 — Hallucinated refund ID detection.

Any refund ID appearing in state.response_text must match the canonical format:
    ^REF-{conversation_id}-\\d+$

If the response contains a REF-... token that does NOT match this pattern,
the agent has hallucinated a refund ID and we must block.

Never raises — all exceptions become a block-severity failure.
"""

from __future__ import annotations

import re

from app.domain.models import AgentState, VerificationCheck

CHECK_NAME = "hallucinated_refund_id_check"

# Matches any token starting with REF- (our refund ID prefix)
_REF_TOKEN_PATTERN = re.compile(r"\bREF-\S+")


async def check_hallucinated_refund_id(state: AgentState) -> VerificationCheck:
    """Assert any refund ID in response_text matches the canonical format.

    Returns block-severity failure if any REF- token is found that does not match
    the expected pattern for this conversation.
    """
    try:
        response_text = state.response_text or ""
        conversation_id = state.conversation_id

        # Build the valid pattern for this conversation
        # e.g., conversation_id="abc" → valid = REF-abc-<digits>
        valid_pattern = re.compile(rf"^REF-{re.escape(conversation_id)}-\d+$")

        tokens = _REF_TOKEN_PATTERN.findall(response_text)

        if not tokens:
            # No refund IDs in response — nothing to validate
            return VerificationCheck(
                check_name=CHECK_NAME,
                passed=True,
                detail="no refund ID tokens found in response_text",
                severity="block",
            )

        bad_tokens = [t for t in tokens if not valid_pattern.match(t)]
        if bad_tokens:
            return VerificationCheck(
                check_name=CHECK_NAME,
                passed=False,
                detail=(
                    f"hallucinated refund ID(s) detected: {bad_tokens!r} — "
                    f"expected pattern REF-{conversation_id}-<digits>"
                ),
                severity="block",
            )

        return VerificationCheck(
            check_name=CHECK_NAME,
            passed=True,
            detail=f"all refund ID tokens match expected pattern: {tokens!r}",
            severity="block",
        )

    except Exception as exc:  # noqa: BLE001
        return VerificationCheck(
            check_name=CHECK_NAME,
            passed=False,
            detail=f"check raised: {exc}",
            severity="block",
        )
