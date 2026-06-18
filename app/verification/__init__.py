"""app.verification — Layer 9 Verification pipeline.

Public contract:
    from app.verification import run_verification_pipeline

    async run_verification_pipeline(state: AgentState) -> VerificationResult
"""

from app.verification.pipeline import run_verification_pipeline

__all__ = ["run_verification_pipeline"]
