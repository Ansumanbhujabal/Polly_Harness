"""Tests for Layer 8 — Skill Layer.

8 required tests as per SPEC_SKILLS.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.models import LayerEvent
from app.skills import get_skill, load_skills, route_skills_for_intent
from app.skills.models import Skill, SkillValidationError


# ---------------------------------------------------------------------------
# Helper: build a minimal valid skill markdown string
# ---------------------------------------------------------------------------

def _make_skill_md(
    *,
    id: str = "test_skill",
    name: str = "Test Skill",
    intents: str = "[refund_request]",
    triggers_on: str | None = None,
    description: str = "A test skill.",
    priority: int = 0,
    body: str = "## When to use\nUse this.\n## The pattern\nDo that.\n## Pitfalls\nAvoid this.",
) -> str:
    triggers_line = f'triggers_on: {triggers_on}\n' if triggers_on is not None else ""
    return (
        f"---\n"
        f"id: {id}\n"
        f"name: {name}\n"
        f"intents: {intents}\n"
        f"{triggers_line}"
        f"description: {description}\n"
        f"priority: {priority}\n"
        f"---\n"
        f"{body}\n"
    )


# ---------------------------------------------------------------------------
# 1. test_loader_reads_all_skill_markdowns
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_loader_reads_all_skill_markdowns(repo_root: Path) -> None:
    """Loader pointed at production skills/ dir should return exactly 3 Skill objects."""
    from app.skills.loader import load_skills_from_dir

    skills = load_skills_from_dir(repo_root / "skills")
    assert len(skills) == 3
    ids = {s.id for s in skills}
    assert "verify_identity" in ids
    assert "handle_emotional_escalation" in ids
    assert "explain_denial_with_alternative" in ids


# ---------------------------------------------------------------------------
# 2. test_loader_rejects_skill_with_missing_id
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_loader_rejects_skill_with_missing_id(tmp_path: Path) -> None:
    """A skill markdown missing the `id` field raises SkillValidationError naming the file."""
    from app.skills.loader import load_skills_from_dir

    bad_md = (
        "---\n"
        "name: No Id Skill\n"
        "intents: [refund_request]\n"
        "description: Missing id field.\n"
        "---\n"
        "Some body content here.\n"
    )
    skill_file = tmp_path / "no_id.md"
    skill_file.write_text(bad_md)

    with pytest.raises(SkillValidationError, match="no_id.md"):
        load_skills_from_dir(tmp_path)


# ---------------------------------------------------------------------------
# 3. test_loader_rejects_skill_with_empty_body
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_loader_rejects_skill_with_empty_body(tmp_path: Path) -> None:
    """A skill markdown with no body (frontmatter only) raises SkillValidationError."""
    from app.skills.loader import load_skills_from_dir

    empty_body_md = (
        "---\n"
        "id: empty_body_skill\n"
        "name: Empty Body\n"
        "intents: [refund_request]\n"
        "description: No body.\n"
        "---\n"
        # intentionally empty body
        "   \n"
    )
    skill_file = tmp_path / "empty_body.md"
    skill_file.write_text(empty_body_md)

    with pytest.raises(SkillValidationError, match="empty_body.md"):
        load_skills_from_dir(tmp_path)


# ---------------------------------------------------------------------------
# 4. test_loader_rejects_duplicate_ids
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    """Two skill files with the same id → SkillValidationError naming both files."""
    from app.skills.loader import load_skills_from_dir

    md_content = _make_skill_md(id="duplicate_skill")
    (tmp_path / "first.md").write_text(md_content)
    (tmp_path / "second.md").write_text(md_content)

    with pytest.raises(SkillValidationError, match="duplicate_skill"):
        load_skills_from_dir(tmp_path)


# ---------------------------------------------------------------------------
# 5. test_route_for_refund_request_intent_returns_verify_identity_when_not_identified
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_route_for_refund_request_intent_returns_verify_identity_when_not_identified(
    repo_root: Path,
) -> None:
    """route_skills_for_intent('refund_request', customer_identified=False) includes verify_identity."""
    from app.skills.loader import load_skills_from_dir
    from app.skills.registry import SkillRegistry

    skills = load_skills_from_dir(repo_root / "skills")
    registry = SkillRegistry(skills)
    result = registry.route_skills_for_intent(
        "refund_request",
        customer_identified=False,
    )
    ids = [s.id for s in result]
    assert "verify_identity" in ids


# ---------------------------------------------------------------------------
# 6. test_route_for_complaint_returns_handle_emotional_escalation
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_route_for_complaint_returns_handle_emotional_escalation(repo_root: Path) -> None:
    """route_skills_for_intent('complaint') returns handle_emotional_escalation."""
    from app.skills.loader import load_skills_from_dir
    from app.skills.registry import SkillRegistry

    skills = load_skills_from_dir(repo_root / "skills")
    registry = SkillRegistry(skills)
    result = registry.route_skills_for_intent("complaint")
    ids = [s.id for s in result]
    assert "handle_emotional_escalation" in ids


# ---------------------------------------------------------------------------
# 7. test_route_respects_max_skills_limit
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_route_respects_max_skills_limit(tmp_path: Path) -> None:
    """With many matching skills and max_skills=1, only 1 result returned."""
    from app.skills.loader import load_skills_from_dir
    from app.skills.registry import SkillRegistry

    # Write 3 skills all matching the same intent, no triggers
    for i in range(3):
        md = _make_skill_md(
            id=f"skill_{i}",
            name=f"Skill {i}",
            intents="[refund_request]",
            description=f"Skill number {i}.",
        )
        (tmp_path / f"skill_{i}.md").write_text(md)

    skills = load_skills_from_dir(tmp_path)
    registry = SkillRegistry(skills)
    result = registry.route_skills_for_intent("refund_request", max_skills=1)
    assert len(result) == 1


# ---------------------------------------------------------------------------
# 8. test_skill_loaded_event_emitted_per_skill
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_skill_loaded_event_emitted_per_skill(repo_root: Path) -> None:
    """Loading skills emits exactly 3 skill_loaded L8_SKILLS events."""
    from app.domain.models import LayerName
    from app.observability.layer_event_emitter import get_emitter
    from app.skills.loader import load_skills_from_dir

    emitter = get_emitter()
    captured: list[LayerEvent] = []

    def sink(event: LayerEvent) -> None:
        if (
            event.layer == LayerName.SKILLS
            and event.event_type == "skill_loaded"
        ):
            captured.append(event)

    emitter.subscribe(sink)
    try:
        load_skills_from_dir(repo_root / "skills")
    finally:
        emitter.unsubscribe(sink)

    assert len(captured) == 3
    emitted_ids = {e.payload["id"] for e in captured}
    assert emitted_ids == {
        "verify_identity",
        "handle_emotional_escalation",
        "explain_denial_with_alternative",
    }
