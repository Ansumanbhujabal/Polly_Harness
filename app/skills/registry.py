"""Skill registry — caches the skill list and provides get + route operations.

The registry is loaded once at boot (idempotent: subsequent load_skills() calls
return the same list by object identity). The router evaluates triggers_on predicates
and selects up to max_skills skills per call.

Emits L8_SKILLS / skill_routed on every route_skills_for_intent call.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.models import LayerName
from app.observability.layer_event_emitter import get_emitter
from app.skills.loader import load_skills_from_dir
from app.skills.models import Skill

# ---------------------------------------------------------------------------
# Predicate evaluation
# ---------------------------------------------------------------------------


def _evaluate_predicate(
    predicate: str,
    *,
    customer_identified: bool,
    candidate_decision_kind: str | None,
) -> bool:
    """Evaluate a single triggers_on predicate string against call-site context.

    Supported forms:
      - "not customer_identified"
      - "candidate_decision.kind == <value>"
    """
    pred = predicate.strip()
    if pred == "not customer_identified":
        return not customer_identified

    if pred.startswith("candidate_decision.kind =="):
        _, _, rhs = pred.partition("==")
        expected = rhs.strip().strip('"').strip("'")
        return candidate_decision_kind == expected

    # Unsupported predicates are treated as False (safe default)
    return False


# ---------------------------------------------------------------------------
# SkillRegistry
# ---------------------------------------------------------------------------


class SkillRegistry:
    """Holds a parsed skill list and provides lookup + routing."""

    def __init__(self, skills: list[Skill]) -> None:
        self._skills: list[Skill] = skills
        self._index: dict[str, Skill] = {s.id: s for s in skills}

    def get_skill(self, skill_id: str) -> Skill:
        """Return the Skill by id; raises KeyError if not found."""
        return self._index[skill_id]

    def route_skills_for_intent(
        self,
        intent: str,
        max_skills: int = 2,
        *,
        customer_identified: bool = True,
        candidate_decision_kind: str | None = None,
        conversation_id: str = "__route__",
    ) -> list[Skill]:
        """Return up to max_skills skills matching intent + all triggers_on predicates.

        Sorting: highest priority first, then alphabetical by id as tiebreaker.
        Emits L8_SKILLS / skill_routed with the selected ids.
        """
        matched: list[Skill] = []
        for skill in self._skills:
            if intent not in skill.intents:
                continue
            # All triggers must evaluate True
            all_triggers_pass = all(
                _evaluate_predicate(
                    pred,
                    customer_identified=customer_identified,
                    candidate_decision_kind=candidate_decision_kind,
                )
                for pred in skill.triggers_on
            )
            if not all_triggers_pass:
                continue
            matched.append(skill)

        # Sort: priority descending, id ascending (stable for ties)
        matched.sort(key=lambda s: (-s.priority, s.id))
        selected = matched[:max_skills]

        emitter = get_emitter()
        emitter.emit(
            conversation_id=conversation_id,
            layer=LayerName.SKILLS,
            event_type="skill_routed",
            payload={
                "conversation_id": conversation_id,
                "intent": intent,
                "selected_ids": [s.id for s in selected],
            },
        )

        return selected


# ---------------------------------------------------------------------------
# Module-level cached registry (idempotent load)
# ---------------------------------------------------------------------------

_registry: SkillRegistry | None = None
_cached_skills: list[Skill] | None = None


def _ensure_registry(skills_dir: Path | None = None) -> SkillRegistry:
    """Return the module-level registry, loading from disk if needed."""
    global _registry, _cached_skills
    if _registry is not None:
        return _registry

    if skills_dir is None:
        from app.config import settings
        skills_dir = settings.SKILLS_DIR

    skills = load_skills_from_dir(skills_dir)
    _cached_skills = skills
    _registry = SkillRegistry(skills)
    return _registry


def get_cached_skills() -> list[Skill] | None:
    """Return the cached skill list (None if not yet loaded)."""
    return _cached_skills
