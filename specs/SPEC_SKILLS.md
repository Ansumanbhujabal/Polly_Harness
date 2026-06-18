# SPEC: Skill Layer

**Layer:** L8 — Skill Layer
**Owner:** `app/skills/` (Python loader/registry) + `skills/*.md` (the playbook markdowns)

The Skill Layer is the agent's playbook library: small, intent-routed pieces of procedural guidance the agent injects into its system prompt when a matching situation arises. Skills are markdown files with frontmatter; the loader parses them at boot, the registry caches them, and the router selects up to two per turn based on the classified intent (and optional `triggers_on` predicates).

Three skills ship with v0.1 — explicitly not five, per the design's scope-trim discipline. Three deep skills demo better than five shallow ones.

## Contract

```python
from app.skills import load_skills, get_skill, route_skills_for_intent
```

- `load_skills() -> list[Skill]` — reads every `*.md` under `settings.SKILLS_DIR`, parses frontmatter, validates, returns the list. Called once at lifespan start; the registry caches the result.
- `get_skill(skill_id: str) -> Skill` — registry lookup by id; raises `KeyError` if unknown.
- `route_skills_for_intent(intent: str, max_skills: int = 2, *, customer_identified: bool = True, candidate_decision_kind: str | None = None) -> list[Skill]` — returns up to `max_skills` skills whose frontmatter `intents` includes `intent` and whose optional `triggers_on` predicates evaluate True. Order is the markdown's natural alphabetical order; if there are ties, the higher-priority skill wins (priority frontmatter field, default 0).

The `Skill` Pydantic model lives in `app/skills/models.py`:

```python
class Skill(BaseModel):
    id: str
    name: str
    intents: list[str]              # non-empty
    triggers_on: list[str] = []     # simple dotted-path predicates evaluated against context
    description: str                # one paragraph for the prompt-router LLM
    body: str                       # the playbook markdown (post-frontmatter)
    priority: int = 0
    source_path: Path
```

## Frontmatter schema

Each `skills/*.md` opens with a YAML frontmatter block:

```yaml
---
id: explain_denial_with_alternative
name: Explain Denial With Alternative
intents: [refund_request]
triggers_on: ["candidate_decision.kind == deny"]
description: When the candidate decision is a denial, lead with empathy, cite the policy clause, then propose store credit or exchange.
priority: 0
---
```

Then the playbook body (used as injected prompt content):

```markdown
## When to use
...
## The pattern
...
## Pitfalls
...
```

## Skills shipped

| File | Intents | Trigger | Purpose |
|---|---|---|---|
| `skills/verify_identity.md` | `refund_request` | `not customer_identified` | Ask for order # + email; do not advance until identity verified |
| `skills/handle_emotional_escalation.md` | `complaint`, `frustrated`, `legal_threat` | always | De-escalate; acknowledge feeling; restate policy; offer human escalation |
| `skills/explain_denial_with_alternative.md` | `refund_request` | `candidate_decision.kind == deny` | Lead with empathy; cite clause; propose store credit / exchange |

## Behaviors

- **Loading is idempotent.** `load_skills()` is safe to call multiple times; the registry holds the first result. A test verifies repeat calls return the same list (object identity).
- **Validation rules** (raised as `SkillValidationError`):
  - `id` is non-empty string, unique across the directory.
  - `name` is non-empty string.
  - `intents` is non-empty list of strings.
  - `body` (post-frontmatter) is non-empty.
  - `triggers_on` items must be simple dotted-path predicates (regex `^[a-z_.]+\s*(==|!=)\s*[a-z_0-9"]+$` or the literal string `not customer_identified`).
- **Trigger evaluation** is intentionally tiny — no general expression parser. The router supports exactly:
  - `not customer_identified` → keyed off the call-site flag
  - `candidate_decision.kind == <value>` → keyed off `candidate_decision_kind`
  - additional predicates may be added in later iterations
- **Routing** matches `intent` against each skill's `intents` list; survivors must have ALL their `triggers_on` predicates True. Of the surviving set, the top `max_skills` by `(priority desc, id asc)` are returned.
- **`python-frontmatter` is the parser.** Added to `pyproject.toml` dependencies if not already transitive.

## Events emitted

- `L8_SKILLS / skill_loaded` — payload: `{id: str, source_path: str}` — one emit per skill at boot.
- `L8_SKILLS / skill_routed` — payload: `{conversation_id: str, intent: str, selected_ids: list[str]}` — one emit per `route_skills_for_intent` call.

## Files

```
app/skills/__init__.py            # exports load_skills, get_skill, route_skills_for_intent, Skill
app/skills/models.py              # Skill Pydantic model + SkillValidationError
app/skills/loader.py              # load_skills() + frontmatter parsing + validation
app/skills/registry.py            # cache + get_skill + route_skills_for_intent
skills/verify_identity.md
skills/handle_emotional_escalation.md
skills/explain_denial_with_alternative.md
```

## Dependencies

- `app.config` — `settings.SKILLS_DIR`
- `app.observability` — `get_emitter`
- `python-frontmatter`
- `pydantic`

Out of scope: dynamic skill creation at runtime (the incident-distiller proposes new skills as PR diffs, not as in-memory injections), skill versioning beyond git.

## Tests

`tests/test_skills.py` — minimum tests:

1. `test_loader_reads_all_skill_markdowns` — point loader at the production `skills/` dir; assert 3 `Skill` objects returned with the 3 expected ids.
2. `test_loader_rejects_skill_with_missing_id` — write a tmp skill without `id`; `SkillValidationError` raised with message naming the file.
3. `test_loader_rejects_skill_with_empty_body` — frontmatter only, no body → error.
4. `test_loader_rejects_duplicate_ids` — two skills with same id → error names both files.
5. `test_route_for_refund_request_intent_returns_verify_identity_when_not_identified` — `route_skills_for_intent("refund_request", customer_identified=False)` returns `verify_identity` (and possibly one more) in result.
6. `test_route_for_complaint_returns_handle_emotional_escalation` — `intent="complaint"` returns `handle_emotional_escalation`.
7. `test_route_respects_max_skills_limit` — many matches, `max_skills=1` returns exactly 1.
8. `test_skill_loaded_event_emitted_per_skill` — capture `LayerEvent` list; assert 3 `skill_loaded` events with the 3 ids.

## Done criteria

- [ ] All 4 Python module files (`__init__.py`, `models.py`, `loader.py`, `registry.py`) + 3 skill markdown files exist (7 files total).
- [ ] All 8 tests pass under `pytest -m "unit or integration" tests/test_skills.py`.
- [ ] `python-frontmatter` listed in `pyproject.toml` dependencies (explicit, not transitive-implicit).
- [ ] Each shipped skill markdown has all required frontmatter fields and a non-empty body with at least one `## When to use`, `## The pattern`, `## Pitfalls` section.
- [ ] `mypy --strict app/skills/` passes (best-effort).
