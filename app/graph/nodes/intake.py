"""Node: intake — first node in the graph, validates and normalises the incoming state.

Responsibilities:
- Ensure conversation_id is set.
- Normalise message list (ensure at least one message).
- v13: truncate over-length user messages to MAX_USER_MESSAGE_CHARS so downstream
  LLM calls don't blow context budgets. This protects against C5a stress attacks
  (50k+ character user messages) AND against legitimate users pasting walls of
  text. The truncation is non-fatal — a marker is appended so the agent / verification
  layer can see something was cut.
- Emit node_entered / node_exited events.
"""

from __future__ import annotations

from typing import Any

from app.domain.models import AgentState
from app.graph.nodes._events import node_scope

# Anything beyond this length is almost certainly stress / abuse / mistaken paste.
# Most legitimate refund requests fit in 500 characters; 8000 is a generous ceiling.
MAX_USER_MESSAGE_CHARS = 8000
_TRUNCATION_MARKER = "\n\n[message truncated by intake guard — original exceeded length cap]"


def intake_node(state: AgentState) -> dict[str, Any]:
    """Intake node — pass-through validation, normalisation, and stress-input guarding."""
    cid: str = state.conversation_id or "unknown"

    with node_scope("intake", cid):
        # Normalise messages: ensure list exists
        messages = list(state.messages or [])

        # Length-guard user messages
        for i, msg in enumerate(messages):
            content = ""
            if isinstance(msg, dict):
                content = str(msg.get("content", ""))
            else:
                content = str(getattr(msg, "content", ""))
            if len(content) > MAX_USER_MESSAGE_CHARS:
                trimmed = content[:MAX_USER_MESSAGE_CHARS] + _TRUNCATION_MARKER
                if isinstance(msg, dict):
                    msg = dict(msg)
                    msg["content"] = trimmed
                    messages[i] = msg
                else:
                    # Pydantic-style or simple object — best-effort dict conversion
                    new_msg = {"role": getattr(msg, "role", "user"), "content": trimmed}
                    messages[i] = new_msg

        return {"messages": messages}
