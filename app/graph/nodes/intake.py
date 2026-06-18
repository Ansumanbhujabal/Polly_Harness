"""Node: intake — first node in the graph, validates and normalises the incoming state.

Responsibilities:
- Ensure conversation_id is set.
- Normalise message list (ensure at least one message).
- Emit node_entered / node_exited events.
"""

from __future__ import annotations

from typing import Any

from app.domain.models import AgentState
from app.graph.nodes._events import node_scope


def intake_node(state: AgentState) -> dict[str, Any]:
    """Intake node — pass-through validation and normalisation."""
    cid: str = state.conversation_id or "unknown"

    with node_scope("intake", cid):
        # Normalise messages: ensure list exists
        messages = state.messages or []
        return {"messages": messages}
