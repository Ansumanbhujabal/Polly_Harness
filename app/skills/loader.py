"""Skill Layer loader — parses and validates skills/*.md files.

Called once at lifespan start. Returns a list of validated Skill objects.
Emits L8_SKILLS / skill_loaded per skill at boot.

Predicate grammar supported in triggers_on:
  - "not customer_identified"
  - "candidate_decision.kind == <value>"

Anything else raises SkillValidationError at load time.
"""

from __future__ import annotations

import re
from pathlib import Path

import frontmatter

from app.domain.models import LayerName
from app.observability.layer_event_emitter import get_emitter
from app.skills.models import Skill, SkillValidationError

# ---------------------------------------------------------------------------
# Predicate validation regex
# Allowed: dotted-path predicates OR the literal "not customer_identified"
# ---------------------------------------------------------------------------
_PREDICATE_PATTERN = re.compile(
    r"^[a-z_.]+\s*(==|!=)\s*[a-z_0-9\"]+$|^not customer_identified$"
)


def _validate_predicate(predicate: str, source_path: Path) -> None:
    """Raise SkillValidationError if the predicate doesn't match the allowed grammar."""
    if not _PREDICATE_PATTERN.match(predicate.strip()):
        raise SkillValidationError(
            f"{source_path.name}: invalid predicate '{predicate}'. "
            "Only 'not customer_identified' and 'candidate_decision.kind == <value>' are supported."
        )


def _parse_skill(md_path: Path) -> Skill:
    """Parse and validate a single skill markdown file."""
    try:
        post = frontmatter.load(str(md_path))
    except Exception as exc:
        raise SkillValidationError(
            f"{md_path.name}: failed to parse frontmatter — {exc}"
        ) from exc

    meta = post.metadata
    body: str = post.content.strip() if post.content else ""

    # -- id -------------------------------------------------------------------
    raw_id = meta.get("id", "")
    if not raw_id or not str(raw_id).strip():
        raise SkillValidationError(
            f"{md_path.name}: missing or empty 'id' field in frontmatter."
        )
    skill_id = str(raw_id).strip()

    # -- name -----------------------------------------------------------------
    raw_name = meta.get("name", "")
    if not raw_name or not str(raw_name).strip():
        raise SkillValidationError(
            f"{md_path.name}: missing or empty 'name' field in frontmatter."
        )
    skill_name = str(raw_name).strip()

    # -- intents --------------------------------------------------------------
    raw_intents = meta.get("intents", [])
    if not raw_intents or not isinstance(raw_intents, list) or len(raw_intents) == 0:
        raise SkillValidationError(
            f"{md_path.name}: 'intents' must be a non-empty list."
        )
    intents: list[str] = [str(i).strip() for i in raw_intents]

    # -- description ----------------------------------------------------------
    raw_desc = meta.get("description", "")
    if not raw_desc or not str(raw_desc).strip():
        raise SkillValidationError(
            f"{md_path.name}: missing or empty 'description' field in frontmatter."
        )
    description = str(raw_desc).strip()

    # -- body -----------------------------------------------------------------
    if not body:
        raise SkillValidationError(
            f"{md_path.name}: skill body (post-frontmatter content) must not be empty."
        )

    # -- triggers_on ----------------------------------------------------------
    raw_triggers = meta.get("triggers_on", [])
    triggers_on: list[str] = []
    if raw_triggers:
        if isinstance(raw_triggers, list):
            triggers_on = [str(t).strip() for t in raw_triggers]
        else:
            triggers_on = [str(raw_triggers).strip()]

    for predicate in triggers_on:
        _validate_predicate(predicate, md_path)

    # -- priority -------------------------------------------------------------
    priority: int = int(meta.get("priority", 0))

    return Skill(
        id=skill_id,
        name=skill_name,
        intents=intents,
        triggers_on=triggers_on,
        description=description,
        body=body,
        priority=priority,
        source_path=md_path,
    )


def load_skills_from_dir(skills_dir: Path) -> list[Skill]:
    """Parse all *.md files under skills_dir; return validated list of Skills.

    Emits one L8_SKILLS / skill_loaded event per skill.
    Raises SkillValidationError on any validation failure (missing field, empty body,
    duplicate id, invalid predicate).
    """
    md_files = sorted(skills_dir.glob("*.md"))
    skills: list[Skill] = []
    seen_ids: dict[str, Path] = {}

    emitter = get_emitter()

    for md_path in md_files:
        skill = _parse_skill(md_path)

        # Duplicate id check
        if skill.id in seen_ids:
            raise SkillValidationError(
                f"Duplicate skill id '{skill.id}' found in both "
                f"'{seen_ids[skill.id].name}' and '{md_path.name}'."
            )
        seen_ids[skill.id] = md_path
        skills.append(skill)

        emitter.emit(
            conversation_id="__boot__",
            layer=LayerName.SKILLS,
            event_type="skill_loaded",
            payload={"id": skill.id, "source_path": str(skill.source_path)},
        )

    return skills
