# SPEC: Incident Loop — the failure→infrastructure feedback hero

**Layer:** Cross-cutting (the 10th conceptual artifact — the Loom's hero)
**Owner:** `app/learning/`

The Incident Loop is the most distinctive piece of the system. It is the literal embodiment of the harness doctrine: *"every failure becomes a new piece of infrastructure."* When a verification check blocks or a human overrides the agent's recommendation, a structured `incident.yaml` is written. Periodically, the distiller reads the unprocessed incidents, runs an LLM over them with a structured-output prompt, and emits **PR-ready unified-diff proposals** for new skills, new verification rules, or policy clarifications. The proposals are not auto-applied — they go to `data/proposals/` for human review.

This is the loop the Loom narrates at minutes 8:45–end.

## Contract

```python
from app.learning import write_incident, distill_incidents
```

- `write_incident(triggered_by: Literal[...], layer: LayerName, summary: str, detail: dict, *, conversation_id: str, incident_id: str | None = None) -> str` — writes `data/incidents/<timestamp>_<reason>.yaml`, also persists via `app.state.get_repository().save_incident(...)`, returns the `incident_id`. Idempotent: if `incident_id` is supplied and already exists on disk, the existing file path is returned with no overwrite.
- `async distill_incidents(min_age_minutes: int = 60, batch_size: int = 10) -> list[ProposedRemediation]` — reads the un-processed incidents (older than `min_age_minutes`, not in `processed_incidents`), runs the distiller LLM, validates each proposal via Pydantic, writes them to `data/proposals/<timestamp>_<kind>.md`, marks the source incidents as processed, returns the list.

A new domain model is added to `app/domain/models.py`:

```python
class ProposedRemediation(BaseModel):
    kind: Literal["new_skill", "new_verification_rule", "policy_clarification"]
    target_file: str               # relative path (e.g., "skills/handle_30day_grace.md")
    markdown_diff: str             # unified-diff text, parseable by git apply --check
    justification: str             # one paragraph explaining the proposed change
    source_incident_ids: list[str] # the incidents that motivated the proposal
    created_at: datetime
```

## Incident YAML schema

Versioned at `data/incidents/SCHEMA.md`:

```yaml
incident_id: 9c2c1f-...           # UUID
conversation_id: conv-abc-123
triggered_by: verification_failure   # | hitl_override | tool_failure | injection_detected
layer: L9_VERIFICATION                # any LayerName value
summary: One-line human description.
detail:
  failed_check: policy_assertion_return_window
  cited: [POLICY-001]
  expected: [POLICY-002]
created_at: 2026-06-18T18:00:00+00:00
```

Filenames follow `<UTC ISO timestamp>_<triggered_by>_<incident_id_short>.yaml`. The timestamp ensures lexicographic ordering; the short id (first 8 chars) makes filenames discriminable.

## Behaviors

- **`write_incident` is idempotent** on `incident_id`. The caller (typically `app.verification.run_verification_pipeline`) generates a UUID and passes it; replay-safety follows. If `incident_id` is omitted, a new UUID is minted.
- **Filesystem AND SQLite both written** — disk is for human inspection (the Loom showcases the file), DB is for the distiller's query path.
- **`distill_incidents` is idempotent.** A `processed_incidents` row (incident_id, processed_at, batch_id) prevents re-processing.
- **Distiller LLM** uses a structured-output prompt loaded via `app.instructions.load_system_prompt(name="distiller")` (one of the prompt files from SPEC_INSTRUCTIONS or a new prompt that the implementer adds — note: adding `prompts/distiller.md` is part of this task). The model is `AzureChatOpenAI` with `response_format={"type": "json_object"}` for structured output. The output schema is `list[ProposedRemediation]` validated via Pydantic.
- **PR-ready unified diff format** — the `markdown_diff` field is the output of a synthesized `diff -u` against the target_file (or a new-file diff for kinds like `new_skill`). The test asserts `git apply --check <(echo "$markdown_diff")` succeeds.
- **Three remediation kinds:**
  - `new_skill` → `target_file = "skills/<id>.md"`, diff is a new-file create with frontmatter + body matching SPEC_SKILLS schema.
  - `new_verification_rule` → `target_file = "app/verification/checks/<name>.py"`, diff is a new-file create with a check function matching SPEC_VERIFICATION shape.
  - `policy_clarification` → `target_file = "data/policy/refund_policy_v1.md"`, diff is an in-place modification adding or refining a `POLICY-NNN` clause.
- **Triggers:**
  - Manual: `make distill` → `python -m app.learning.distill_cli` → calls `distill_incidents()` and prints proposals.
  - Cron: `.github/workflows/distill.yml` (workflow_dispatch + nightly schedule), checks out main, runs `make distill`, opens a PR with the proposals committed.
- **One worked example proposal MUST be committed at `data/proposals/EXAMPLE.md`** so the Loom can show a concrete example without depending on a fresh distiller run. The example is hand-authored to match the live shape.

## Events emitted

- `INCIDENT_LOOP / incident_written` — payload: `{incident_id: str, triggered_by: str, layer: str, summary: str}`.
- `INCIDENT_LOOP / distillation_proposed` — payload: `{num_proposals: int, source_incident_ids: list[str]}`.

## Files

```
app/learning/__init__.py             # exports write_incident, distill_incidents, ProposedRemediation
app/learning/incident_logger.py      # write_incident
app/learning/incident_distiller.py   # distill_incidents
app/learning/distill_cli.py          # CLI entrypoint for `make distill`
prompts/distiller.md                 # structured-output system prompt
data/incidents/SCHEMA.md             # human-readable schema doc
data/proposals/EXAMPLE.md            # one worked example, hand-authored
```

## Dependencies

- `app.domain.models` — `IncidentRecord`, `LayerName`, `ProposedRemediation` (new), `LayerEvent`
- `app.state` — `get_repository()`
- `app.observability` — `get_emitter`, `get_logger`
- `app.instructions` — `load_system_prompt`
- `langchain_openai.AzureChatOpenAI`
- `pyyaml`
- Standard `subprocess` (for `git apply --check` in tests)

Out of scope: actually opening the PR (the CI workflow does that with `gh pr create`); applying the diff to the repo (always human-reviewed); replacing the verification pipeline (the distiller proposes, never enforces).

## Tests

`tests/test_incident_loop.py` — minimum tests:

1. `test_write_incident_creates_yaml_file_and_db_row` — call `write_incident`; assert YAML at `data/incidents/<filename>.yaml` exists, parses, content matches schema; assert one row in `incidents` table.
2. `test_write_incident_idempotent_on_id` — call twice with same `incident_id`; one file on disk, one row in DB.
3. `test_write_incident_emits_incident_written_event` — capture LayerEvents; exactly one event with the matching incident_id.
4. `test_distill_skips_already_processed` — seed 3 incidents, mark 1 as processed via `processed_incidents` row; distill returns proposals for only the other 2.
5. `test_distill_respects_min_age_filter` — seed 2 incidents 30 min old, 1 incident 90 min old; `distill_incidents(min_age_minutes=60)` only sees the 90-min one.
6. `test_distill_emits_proposals_with_valid_unified_diff` — stub LLM returns a `ProposedRemediation` with a new-file diff; assert `git apply --check` on the diff succeeds (uses `subprocess` against a tmp_path repo).
7. `test_distill_proposes_policy_clarification_when_pattern_matches` — seed 3 incidents with `failed_check=policy_assertion_return_window`; stub LLM returns a policy_clarification proposal; assert `target_file == "data/policy/refund_policy_v1.md"`.
8. `test_distill_marks_incidents_processed_after_emit` — after distill, the source incident_ids appear in `processed_incidents`.
9. `test_distill_handles_empty_incident_pool` — no eligible incidents → returns `[]`, no LLM call, no DB write.
10. `test_distill_writes_proposals_to_data_proposals_directory` — after distill, `data/proposals/<timestamp>_<kind>.md` files exist with the diff content.

## Done criteria

- [ ] All 5 source-tree files (`app/learning/__init__.py`, `incident_logger.py`, `incident_distiller.py`, `distill_cli.py`, `prompts/distiller.md`) + 2 data-tree files (`data/incidents/SCHEMA.md`, `data/proposals/EXAMPLE.md`) exist on disk (7 files total).
- [ ] `ProposedRemediation` model added to `app/domain/models.py` with a round-trip model test.
- [ ] All 10 tests pass under `pytest -m "unit or integration" tests/test_incident_loop.py`.
- [ ] `make distill` target added to `Makefile`.
- [ ] `data/proposals/EXAMPLE.md` contains a hand-authored example proposal whose `markdown_diff` passes `git apply --check` from the repo root.
- [ ] `mypy --strict app/learning/` passes (best-effort).
