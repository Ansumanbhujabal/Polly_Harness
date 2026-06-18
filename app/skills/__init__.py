"""Layer 8 — Skill Layer public API.

Usage:
    from app.skills import load_skills, get_skill, route_skills_for_intent, Skill
"""

from __future__ import annotations

from pathlib import Path

from app.skills.models import Skill, SkillValidationError
from app.skills.registry import SkillRegistry, _ensure_registry

__all__ = [
    "Skill",
    "SkillValidationError",
    "load_skills",
    "get_skill",
    "route_skills_for_intent",
]

# ---------------------------------------------------------------------------
# Module-level _cached list — idempotent (second call returns same list object)
# ---------------------------------------------------------------------------

_loaded_skills: list[Skill] | None = None


def load_skills(skills_dir: Path | None = None) -> list[Skill]:
    """Load and cache all skills from SKILLS_DIR (or a custom path).

    Idempotent: subsequent calls return the same list by identity.
    Emits L8_SKILLS / skill_loaded per skill on first call.
    """
    global _loaded_skills
    if _loaded_skills is not None:
        return _loaded_skills

    registry = _ensure_registry(skills_dir)
    _loaded_skills = registry._skills  # same list object, no copy
    return _loaded_skills


def get_skill(skill_id: str) -> Skill:
    """Return skill by id from the cached registry. Raises KeyError if unknown."""
    registry = _ensure_registry()
    return registry.get_skill(skill_id)


def route_skills_for_intent(
    intent: str,
    max_skills: int = 2,
    *,
    customer_identified: bool = True,
    candidate_decision_kind: str | None = None,
    conversation_id: str = "__route__",
) -> list[Skill]:
    """Route to up to max_skills skills for the given intent + context.

    Emits L8_SKILLS / skill_routed.
    """
    registry = _ensure_registry()
    return registry.route_skills_for_intent(
        intent,
        max_skills,
        customer_identified=customer_identified,
        candidate_decision_kind=candidate_decision_kind,
        conversation_id=conversation_id,
    )
