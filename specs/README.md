# Component Specs — The Army's Brief

This directory is the **spec-driven contract layer**. Each `SPEC_*.md` file defines one component of the harness: its public interface, its inputs/outputs, the events it emits, the files it must produce, and the tests it must ship with.

Every component agent reads **exactly three things** to do its job:

1. Its own `SPEC_*.md` in this directory
2. `app/domain/models.py` — the shared data shapes
3. `docs/architecture.md` — to know where it fits in the harness

That's the contract. If the army needs more context than that, the spec is incomplete and we need to update it.

## How the army reads a spec

Each spec has fixed sections. Implementers must satisfy every section.

| Section | Purpose |
|---|---|
| **Layer** | Which harness layer (or cross-cut) this belongs to |
| **Contract** | The public interface other components depend on |
| **Inputs / Outputs** | Exact types (always from `app.domain.models`) |
| **Behaviors** | What the component does, including the edge cases it must handle |
| **Events emitted** | Which `LayerEvent`s fire and when |
| **Files** | Exact paths to create — no improvising file layouts |
| **Tests** | Minimum tests required, with named assertions |
| **Done criteria** | Checklist the implementer ticks before declaring done |

## Discipline

- No file outside the spec's "Files" list may be created. If you need one, stop and amend the spec.
- No new domain model may be invented locally. If a shape is missing, add it to `app/domain/models.py` and update the spec.
- Every component must emit at least one `LayerEvent` on entry and one on exit.
- Every component must ship with tests. Skipping tests is not a tradeoff the army may make.
