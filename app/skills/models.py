"""Skill domain models for Layer 8 — Skill Layer.

`Skill` is the parsed + validated representation of a skills/*.md file.
`SkillValidationError` is raised by the loader when a markdown file fails validation.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class SkillValidationError(Exception):
    """Raised when a skill markdown file fails frontmatter validation."""


class Skill(BaseModel):
    id: str
    name: str
    intents: list[str]  # non-empty
    triggers_on: list[str] = Field(default_factory=list)  # simple predicate strings
    description: str  # one-paragraph description for the prompt-router LLM
    body: str  # post-frontmatter markdown body
    priority: int = 0
    source_path: Path
