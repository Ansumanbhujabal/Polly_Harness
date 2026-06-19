# ADR-0005: Skip the Voice Pipeline

**Status:** Accepted
**Date:** 2026-06-18

## Context

A voice pipeline (e.g., OpenAI Realtime API, ElevenLabs, or LiveKit) was considered as an optional surface. The realistic cost: 1–2 days of integration time, fragile WebSocket transport debugging, and a feature that does not advance the harness narrative.

## Decision

**Skip voice entirely.** Document the cut explicitly in the README under "Scope (v0.1) — what is intentionally out." Leave a stub interface note at `frontend/static/voice_extension.md` describing how voice would slot in via the existing SSE event spine.

## Consequences

**Why the cut is the right call:**
- The harness frame is about *reliability* in a refund pipeline — voice is a transport concern, not a reliability concern. Building voice would have crowded out time spent on Verification (L9) and the Incident Loop, both of which carry more senior-engineering signal.
- Scope discipline IS itself a senior-engineering signal. Reviewers reading the README see an explicit non-goal with a documented tradeoff, not silence.

**What we gave up:** A potential bonus-points beat in the Loom and the implicit "I can integrate Realtime API" signal. The judgment call: a deeper Verification layer + a working Incident Loop carry more signal in a senior interview than a shallower demo with voice strapped on.

**Verification:** Voice is absent from every dependency in `pyproject.toml`, every test in `tests/`, every node in `app/graph/`. The cut is real, not hand-waved.
