# Design — Harness-Engineered Refund Agent (WORPODD Take-Home)

**Author:** Ansuman SS Bhujabala
**Date:** 2026-06-18
**Status:** Approved (brainstorm), pending final spec review
**Deadline:** 2026-06-25 (submission). **Target ship:** 2026-06-18 EOD (today).
**Drives:** the implementation plan produced by `superpowers:writing-plans`, which drives the parallel sub-agent build.

---

## 1. Context

WORPODD recruiter take-home: build an AI Customer Support Agent for e-commerce refund processing as a vertical slice. Primary evaluation = a 7–10 minute Loom walkthrough; secondary = GitHub repo + README. Successful review → final team interview. This submission is positioned as a **senior / staff-level signal**, not a feature-complete tutorial.

The framing — locked in three prior memory entries — is **Harness Engineering**: 9 layers around the LLM that catch different failure classes, with a cross-cutting feedback loop that turns every verification failure into a PR-ready proposal for new infrastructure. The harness frame is the Loom thesis; LangGraph is an implementation detail of Layer 6.

What's already on disk (2 prior commits, ~880 LOC) is kept and built on: shared domain models (`app/domain/models.py`), settings (`app/config.py`), layer event emitter (`app/observability/layer_event_emitter.py`), structured logger, conftest with seed fixtures, `agentic.md` (L1 operating charter), `docs/architecture.md` (9-layer map), policy doc, 15 customers + 30 orders seed data, Docker + Makefile + pyproject, README, `specs/SPEC_TOOLS.md`.

---

## 2. Goals

1. End-to-end working harness on `localhost` + deployed to Hugging Face Spaces by **EOD 2026-06-18**.
2. Loom walkthrough recorded and submitted.
3. Every one of the 9 harness layers has at least one shippable, demo-able file. Demo-grade depth, not stubs.
4. **Failure→Infrastructure incident loop** as the hero / staff-level signal. Lead the Loom on it.
5. Satisfy the bounded **production-grade contract** in §6 (12 falsifiable pillars).
6. The 5 holding-the-line edge cases each demonstrably caught by a different harness layer, with the layer named live in the Loom.

## 3. Non-goals

- Voice pipeline. Explicit scope cut, documented in ADR-0005 + README.
- Real payment processor (Stripe / Adyen). `issue_refund` writes to SQLite + emits an event.
- Real authentication / authorization. Single-tenant, single-user demo. Documented as roadmap.
- Real PCI / SOC2 scope. Out of scope for take-home; documented.
- Multi-tenant policy versioning. One store, one policy version.
- Cytoscape.js upgrade for the dynamic diagram. Mermaid only — locked.
- Pre-day-7 "best ever" eval calibration. Eval gate ships green at agreed thresholds; further tuning is post-submission.

## 4. Architecture deltas vs. on-disk plan

The on-disk `docs/architecture.md` map is the spine and stays. This design adds explicit contracts for what was hand-waved, and tightens scope.

### 4.1 Adds

- **Event spine** — explicit `event_type` catalog, SSE subscription contract, ring-buffer replay so a dashboard refresh recovers the trace. Owns the path from `LayerEvent` → Langfuse trace, SSE stream, dynamic diagram.
- **Concurrency model** — single asyncio loop owns Azure OpenAI / Qdrant / Langfuse / SQLite clients. Gradio mounted under FastAPI via `gr.mount_gradio_app`. Sync nodes invoked through a threadpool executor. No shared mutable globals outside `app/config.settings`.
- **MCP lifecycle** — MCP stdio server runs **in-process**, bound to FastAPI's `lifespan` hook. NOT a sidecar — sidecar boot order breaks HF Spaces deploys.
- **Verification pipeline** — runs AFTER candidate decision, BEFORE `issue_refund` invocation. Fail-closed. 6 named checks run in parallel via `asyncio.gather`. Result aggregated into `VerificationResult`. Any `severity=block` failure: graph routes to escalation node + incident.yaml written.
- **Incident loop (the hero)** — explicit `incident.yaml` schema, distiller LLM prompt template, output = markdown PR-diff (proposes new skill / verification rule / policy clarification), idempotency key, "processed" state in SQLite.
- **Demo-script as enforceable spec** — `SPEC_DEMO_SCRIPT.md` captures the Loom opener verbatim, 5 cases mapped to exact `customer_id`/`order_id` from seed data, expected verification outcomes, expected event sequence on the dashboard. This is a contract over both the seed data and the graph behavior.
- **Bootstrap + CI** — `scripts/seed_qdrant.py`, `scripts/langfuse_bootstrap.py` (push canonical prompts to Langfuse), `.github/workflows/ci.yml` (tests, lint, mypy on push), `.github/workflows/evals.yml` (eval suite on PR + nightly).

### 4.2 Drops / changes from earlier doc

- **Tone subagent dropped.** Collapsed into main prompt. Subagents must have a strong purpose (context budget protection); tone is style.
- **Skills 5 → 3.** Three deep playbooks beat five shallow: `verify_identity.md`, `handle_emotional_escalation.md`, `explain_denial_with_alternative.md`.
- **Dynamic diagram with Mermaid only.** Cytoscape upgrade explicitly out of scope.
- **Semantic cache feature-flagged, default OFF.** File exists; flag flips on if integration burn has slack. Otherwise documented as roadmap.

## 5. Spec backlog — 16 SPECs total (1 existing, 15 to write)

Already exists: `specs/SPEC_TOOLS.md` (L3, 8 tools, 21 tests, ~140 lines).

To be written today (15 new specs). Each follows the existing `specs/README.md` template: Layer, Contract, Inputs/Outputs, Behaviors, Events emitted, Files, Tests, Done criteria.

| # | Spec file | Layer | Owner module |
|---|---|---|---|
| 1 | `SPEC_INSTRUCTIONS.md` | L1 | `app/instructions/` (new) — agentic.md loader, prompt catalog, Langfuse registry sync |
| 2 | `SPEC_CONTEXT.md` | L2 | `app/context/` — Qdrant retriever, compactor, customer_context_builder |
| 3 | `SPEC_EXECUTION.md` | L4 | `app/tools/executor.py` + `Dockerfile` — sandbox executor, network egress lockdown, structured envelope |
| 4 | `SPEC_STATE.md` | L5 | `app/state/` — SqliteSaver wrap, repositories, migrations |
| 5 | `SPEC_ORCHESTRATION.md` | L6 | `app/graph/` — refund_graph state machine, interrupt nodes, retry policy, conditional edges |
| 6 | `SPEC_SUBAGENTS.md` | L7 | `app/graph/subagents/fraud_check.py` — isolated context budget, summary-only return |
| 7 | `SPEC_SKILLS.md` | L8 | `app/skills/` + `skills/*.md` — frontmatter schema, loader, registry, intent→skill router |
| 8 | `SPEC_VERIFICATION.md` | L9 | `app/verification/` — 6 checks, parallel runner, fail-closed, incident emission |
| 9 | `SPEC_OBSERVABILITY.md` | X-cut | `app/observability/` — Langfuse client, emitter wiring, SSE publisher, dashboard subscriber |
| 10 | `SPEC_INCIDENT_LOOP.md` | X-cut (hero) | `app/learning/` — logger, distiller, schema, PR-diff format, processed-state tracking |
| 11 | `SPEC_MCP_SERVER.md` | X-cut | `app/mcp/server.py` — in-process MCP stdio, FastAPI lifespan binding, tool registration |
| 12 | `SPEC_API.md` | Cross | `app/api/` — FastAPI routes, SSE stream, health, admin endpoints |
| 13 | `SPEC_FRONTEND.md` | Cross | `frontend/` + Gradio app — chat, admin dashboard, dynamic Mermaid diagram, approval-gate panel |
| 14 | `SPEC_EVAL.md` | Cross | `eval/` — adversarial generator, scenarios.yaml, Langfuse-judge wiring, CI integration |
| 15 | `SPEC_DEMO_SCRIPT.md` | Loom | `docs/demo_script.md` — opener, 5 cases with exact IDs, expected events |

## 6. Production-grade contract (the bounded "no loopholes")

Falsifiable. Every layer satisfies ALL 12. Out-of-scope items (real Stripe, real auth, real PCI) are listed in §3 as documented scope cuts — those are not loopholes.

| # | Pillar | Falsifiable test |
|---|---|---|
| 1 | **Type safety** | All cross-layer I/O via Pydantic models from `app/domain/models.py`. `mypy --strict` passes. No untyped dicts cross layer boundaries. |
| 2 | **Idempotency** | `issue_refund`, `escalate_to_human`, incident writes are insert-or-noop on `(conversation_id, business_key)`. Explicit test per write. |
| 3 | **Determinism in tests** | Seeded RNG via `random.seed(42)`, frozen time via `freezegun.freeze_time` where dates matter, recorded retriever fixtures, no real LLM in unit/integration tier. |
| 4 | **Fail-closed verification** | Any L9 check `severity=block` → agent CANNOT call `issue_refund`. Enforced in graph by `interrupt()` + tested with `test_block_prevents_issue`. |
| 5 | **Structured errors** | Every tool returns `{ok, output, error_code, latency_ms, retries}`. No raw exceptions cross sandbox boundary. Tested. |
| 6 | **Observability spine** | Every graph node + every tool + every check emits a `LayerEvent`. Trace coverage 100% — asserted by `test_every_node_emits_event`. |
| 7 | **Audit trail** | Reasoning string, cited clause IDs, candidate vs final decision, incident.yaml all persisted via `app/state/repositories.py`. Round-trip tested. |
| 8 | **Security baseline** | Injection check on every user turn. Sandboxed executor blocks network egress (mocked in tests, enforced via Docker network policy in deploy). No `eval`/`exec`. Secrets only via env. `.env` in `.gitignore`. |
| 9 | **Eval gate in CI** | `.github/workflows/evals.yml` runs adversarial set. PR fails if `policy_correctness < 0.95` or `injection_resistance < 0.98`. Ships green at these thresholds; judge calibration may iterate post-submission to tighten without changing the gate semantics. |
| 10 | **Cloneable & runnable** | `make install && make seed && make run` works from clean clone in <5 min with only env vars set. README quickstart verified by one-shot script `scripts/verify_quickstart.sh`. |
| 11 | **Test coverage** | Unit test per tool, per verification check, per skill loader path. Integration test for happy path + each of the 5 holding-the-line cases. Coverage >= 80% on `app/`. |
| 12 | **Docs match repo** | Every README link resolves. Every ADR exists. Every named test exists. Every named file exists. CI link-check guard: `scripts/check_doc_references.py`. |

**Best-effort, may spill to D2 morning:**
- Pillar 1 (`mypy --strict` cleanup across all new code)
- Pillar 9 (LLM-judge threshold calibration)

These are reclassified honestly because both can eat unpredictable hours in compressed sprints. If they spill, the submission still ships green with the threshold loosened OR mypy run in non-strict mode, with a follow-up commit before 2026-06-25.

## 7. Agent team & build mechanics

**Mechanism:** parallel sub-agent dispatch using `superpowers:dispatching-parallel-agents` + `superpowers:using-git-worktrees`.

**Three roles per spec, per wave:**

- **Builder** — uses `superpowers:test-driven-development` + `superpowers:subagent-driven-development`. Reads ONLY: its own `SPEC_*.md`, `app/domain/models.py`, `docs/architecture.md`. Writes tests first. Implements until tests pass + spec Done criteria satisfied. Returns a worktree branch.
- **Reviewer** — uses `superpowers:code-review`. Independent pass on the builder's diff against the spec. Rejects on: contract violation, missing tests, "WHAT" comments, untyped boundaries, missing event emission.
- **Verifier** — uses `superpowers:verification-before-completion`. Runs tests, lint, mypy, and confirms the spec's Done criteria checklist BEFORE Claude main reports completion.

**Merge gate to main:** all three roles pass + Ansuman reads the diff before merge.

**Contract discipline:** if a builder needs a file outside the spec's `Files` list, it stops and amends the spec FIRST. Same for domain models — added to `app/domain/models.py` with a passing test before any consumer references it. This discipline is inherited from `specs/README.md`.

**Worktree convention:** one worktree per spec under `/tmp/refund-harness-worktrees/<spec-slug>/`. Branch naming: `agent/<wave>/<spec-slug>`.

## 8. Wave plan (the dependency-respecting fan-out)

### Wave 1 — no inter-dependencies (7 agents parallel)
- SPEC_TOOLS (already specced; builder starts immediately)
- SPEC_EXECUTION (L4 — Docker network policy, sandbox env; the executor.py code is co-built with SPEC_TOOLS but the Docker contract + egress lockdown is separately specced here)
- SPEC_STATE
- SPEC_SKILLS
- SPEC_OBSERVABILITY
- SPEC_MCP_SERVER
- Bootstrap scripts (seed_qdrant + langfuse_bootstrap) — paired with SPEC_OBSERVABILITY agent

Note: `SPEC_DEMO_SCRIPT` is written in the spec-writing block (H+1 → H+2), not Wave 1. It has no buildable code — its "build" is the integration-burn audit at H+12 that confirms the seed data + graph behavior match the contract.

### Wave 2 — depends on Wave 1 contracts (4 agents parallel)
- SPEC_CONTEXT — depends on Qdrant seeded (Wave 1 bootstrap)
- SPEC_VERIFICATION — depends on SPEC_STATE (incident writer) + SPEC_OBSERVABILITY (event emitter)
- SPEC_SUBAGENTS — depends on SPEC_TOOLS (calls tools)
- SPEC_INSTRUCTIONS — depends on Langfuse bootstrap (prompt registry)

### Wave 3 — integration (3 agents parallel)
- SPEC_ORCHESTRATION — depends on L1, L2, L3, L5, L7, L9 — the integration apex
- SPEC_API — depends on L6
- SPEC_INCIDENT_LOOP distiller — depends on incident writer (Wave 2 verification)

### Wave 4 — surface + evals (3 agents parallel)
- SPEC_FRONTEND — depends on SPEC_API + SSE contract
- SPEC_EVAL adversarial gen + CI workflows — depends on full graph
- Integration burn debugger agent (on standby)

### Integration burn (sequential, with debugger agent on call)
- Run 5 holding-the-line cases end-to-end. Fix surfaced bugs.
- Seed-data audit vs `SPEC_DEMO_SCRIPT.md` — does each case have working data?
- Write 5 ADRs.
- README link audit via `scripts/check_doc_references.py`.

### Ship
- HF Spaces deploy + live smoke test.
- Loom recording (opener + demo + code-tour takes).
- Submit.

## 9. Compressed today schedule

| Block | Work | Mechanism |
|---|---|---|
| H+0 → H+1 | This design doc + spec self-review + your final sign-off | Foreground |
| H+1 → H+2 | `superpowers:writing-plans` → executable plan. 2 parallel sub-agents write all 15 new SPECs from the plan. | Me + 2 agents |
| H+2 → H+4 | **Wave 1** parallel build | 6 agents, 6 worktrees |
| H+4 → H+5.5 | Wave 1 review + verify + merge each branch as it lands | Foreground |
| H+5.5 → H+7 | **Wave 2** parallel build | 4 agents |
| H+7 → H+8 | Wave 2 merge | Foreground |
| H+8 → H+9.5 | **Wave 3** parallel build (vertical slice apex) | 3 agents |
| H+9.5 → H+10.5 | Wave 3 merge — vertical slice runs end-to-end on localhost | Foreground |
| H+10.5 → H+12 | **Wave 4** parallel build | 3 agents |
| H+12 → H+13 | Integration burn: 5 cases live, fix surfaced bugs | Me + 1 debugger agent |
| H+13 → H+14 | ADRs (5), README link audit, seed-data audit | 1 agent |
| H+14 → H+15 | HF Spaces deploy + smoke-test live URL | Foreground |
| H+15 → H+16 | Loom recording (opener + demo + code-tour) + submit | You |
| Stretch | mypy strict cleanup + LLM-judge calibration spillover | D2 morning if needed |

**Discipline preserved despite compression:** worktree per spec, code-review skill as merge gate, verification-before-completion before any "done" claim. Compression does not relax contracts — that is how quality breaks.

## 10. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| HF Spaces deploy fails on first push (Docker SDK quirks) | Medium | Build production Docker image locally first (`make docker-up` already in place); test container exec'd as if HF before push. Fallback: Render Docker free tier. |
| LangGraph `interrupt()` semantics surprise the orchestration agent | Medium | `SPEC_ORCHESTRATION.md` requires the interrupt + resume flow as the FIRST integration test, not the last. Spec includes a worked code example in its Behaviors section. |
| Langfuse LLM-judge calibration eats Wave 4 budget | Medium | Pillar 9 reclassified to best-effort. Ship with permissive thresholds; tighten post-submission. |
| Qdrant seeding produces poor retrieval on the "30-day vs 14-day" case | High (it's the Loom opener) | Seed-data audit step at H+13. Embedding model fixed (`text-embedding-3-small`). Retrieval test in SPEC_CONTEXT covers exact queries from SPEC_DEMO_SCRIPT. |
| Sub-agent goes off-contract and edits files outside its spec's Files list | Medium | Reviewer role catches it. Worktree isolation contains damage. Merge gate refuses. |
| Loom take quality (you recording while tired at H+15) | Medium | Two takes minimum. Opening line memorized verbatim — already in memory. SPEC_DEMO_SCRIPT pre-stages exact text. Cap at 3 takes; ship best. |
| mypy strict cleanup explodes | Medium | Reclassified as best-effort. Acceptable to ship with non-strict mypy in CI for v0.1. |
| You burn out mid-sprint | Real | Plan has a 1-hour buffer between waves for breaks. If anything feels off, halt and reassess — D2–D6 buffer is real. |

## 11. Open questions

None. Strategic decisions are locked in memory:
- [[project-worpodd-challenge]] — brief
- [[project-harness-strategy-decisions]] — locked stack
- [[project-loom-strategy]] — Loom storyline + 5 cases
- [[feedback-decision-delegation]] — make-the-call mode
- [[feedback-aggressive-cadence]] — compressed sprint mode

If the spec self-review or your final review surfaces a question, it goes here.

## 12. Out of scope (explicit)

- Voice (ADR-0005)
- Real Stripe / payment processor
- Real auth/auth (single-user demo)
- Real PCI / SOC2 scope
- Multi-tenant policy versioning
- Cytoscape.js diagram upgrade
- Mobile-responsive Gradio styling
- Tone subagent
- 4th / 5th skill markdowns beyond the 3 specified
- Semantic-cache turned on by default

## 13. Done criteria for this design

- [x] All 21 improvement gaps from brainstorm are either in §4 (adopted) or §3/§12 (explicitly cut)
- [x] All 15 specs listed in §5 with owners and layers
- [x] All 12 production-grade pillars in §6 are individually falsifiable
- [x] Wave plan in §8 respects all dependencies (no Wave-2 spec consumes a Wave-3 contract)
- [x] Compressed schedule in §9 totals ≤ 16 hours
- [x] Risk register in §10 covers the top 7 named risks
- [x] Memory references in §11 are all extant memory files
- [x] Scope cuts in §12 match what was deferred earlier

## 14. Next step

After your sign-off on this doc:
1. I invoke `superpowers:writing-plans` to produce the executable implementation plan that drives §7–§9.
2. The plan dispatches the SPEC-writing agents first (H+1 → H+2 block).
3. The SPECs drive the Wave 1–4 builder agents.

---

*This design is the contract. If reality diverges, we update this doc and re-derive — we don't drift silently.*
