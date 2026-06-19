# ADR-0004: The Failure → Infrastructure Feedback Loop

**Status:** Accepted
**Date:** 2026-06-18

## Context

The harness engineering doctrine — quoted in `harness_engineering_idea_i_have.md` — is: *"every failure becomes a new piece of infrastructure."* A submission that *talks* about the doctrine without *embodying* it would be the median LangGraph tutorial with extra prose. The doctrine had to become code, and the code had to be visible in the Loom.

## Decision

Build the **Incident Loop** as the system's 10th conceptual artifact (cross-cutting, atop the 9 layers):

- Every L9 `severity=block` verification failure writes a structured `incident.yaml` to `data/incidents/` AND a row to the `incidents` SQLite table.
- A periodic distiller (`app/learning/incident_distiller.py`) reads un-processed incidents (filtered by min age), runs an LLM with structured-output, and emits **PR-ready unified diffs** as `ProposedRemediation` objects in three flavors: `new_skill`, `new_verification_rule`, `policy_clarification`.
- Proposals land in `data/proposals/`. They are never auto-applied — they go to PR review.
- `make distill` triggers the loop manually; `.github/workflows/distill.yml` runs it nightly via cron.

## Consequences

**Why this is the Loom's hero:**
- Hardest to fake. A competent LangGraph chat UI can't be retrofitted with a working distiller in a recording night.
- Smallest UI surface, biggest narrative weight. The Loom closes on `data/proposals/EXAMPLE.md` and a live `make distill` run — the diff is real, `git apply --check` passes on it, the audience sees infrastructure being proposed from failure.
- Strongest senior signal: it converts "production grade" from a buzzword into a verifiable lifecycle.

**What we gave up:** A more conservative system would have left this as a roadmap bullet. We took the implementation risk because the doctrine demanded it.

**Verification:** `tests/test_incident_loop.py::test_distill_emits_proposals_with_valid_unified_diff` runs `git apply --check` against the generated diff in a tmp_path repo. `data/proposals/EXAMPLE.md` is committed and its diff applies cleanly.
