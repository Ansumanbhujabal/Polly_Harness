"""Node: verification — runs the L9 verification pipeline."""

from __future__ import annotations

from typing import Any

from app.domain.models import AgentState
from app.graph.nodes._events import async_node_scope
from app.verification import run_verification_pipeline


async def verification_node(state: AgentState) -> dict[str, Any]:
    """Run the L9 verification pipeline and store the result."""
    cid: str = state.conversation_id or "unknown"

    async with async_node_scope("verification", cid):
        # If verification already has block result (injected for testing), respect it
        existing = state.verification
        if existing is not None and existing.checks:
            return {"verification": existing}

        verification_result = await run_verification_pipeline(state)
        return {"verification": verification_result}
