"""Layer 1: Instructions — single source of truth for all prompt strings.

Public contract (SPEC_INSTRUCTIONS §Contract):
    load_system_prompt(version)       — system prompt, Langfuse-first with local fallback
    load_skill_router_prompt(version) — intent classifier prompt, same resolution logic
    get_prompt_version()              — last-resolved version string for trace tagging

No other symbols are exported. Internal helpers live in loader.py and langfuse_sync.py.
"""

from __future__ import annotations

from app.instructions.loader import (
    get_last_resolved_version,
    load_skill_router_prompt,
    load_system_prompt,
)

__all__ = [
    "load_system_prompt",
    "load_skill_router_prompt",
    "get_prompt_version",
]


def get_prompt_version() -> str:
    """Return the version string resolved by the last loader call.

    Returns "local-unversioned" if no prompt has been loaded in this process.
    """
    return get_last_resolved_version()
