"""Verification check functions — one module per check.

Each exports a single async function:
    async def check_<name>(state: AgentState, **kwargs) -> VerificationCheck
"""
