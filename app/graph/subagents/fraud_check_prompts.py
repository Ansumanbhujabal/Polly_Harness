"""Prompt loader for the fraud-check sub-agent.

Tries to load from app.instructions (C4); falls back to a hardcoded baseline prompt
when C4 hasn't been built yet (parallel branch).
"""

from __future__ import annotations


def load_fraud_check_prompt() -> str:
    """Return the system prompt for the fraud-check summary narration step."""
    try:
        from app.instructions import load_system_prompt  # type: ignore[import]

        return load_system_prompt("fraud_check_subagent")
    except ImportError:
        # C4 not yet built; fall back to a hardcoded baseline prompt
        return "Summarize the fraud signals in 1-2 sentences for the audit log."
