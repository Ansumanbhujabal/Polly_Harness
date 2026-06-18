"""Node: retrieve_policy — retrieves relevant policy clauses for the conversation."""

from __future__ import annotations

from typing import Any

from app.domain.models import AgentState
from app.graph.nodes._events import async_node_scope
from app.tools import get_tool_by_name
from app.tools.executor import run_tool


async def retrieve_policy_node(state: AgentState) -> dict[str, Any]:
    """Retrieve relevant policy clauses for the current refund context."""
    cid: str = state.conversation_id or "unknown"

    async with async_node_scope("retrieve_policy", cid):
        # If policy already loaded, skip
        if state.relevant_clauses:
            return {}

        # Build query from latest user message
        messages = state.messages or []
        query = "refund policy return window eligibility"
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                query = msg.get("content", query)
                break

        search_tool = get_tool_by_name("search_policy")
        if search_tool is None:
            return {"relevant_clauses": []}

        result = await run_tool(
            search_tool,
            {"query": query, "top_k": 5},
            conversation_id=cid,
        )

        clauses = []
        if result["ok"] and result["output"]:
            clauses = result["output"].get("clauses", [])

        return {"relevant_clauses": clauses}
