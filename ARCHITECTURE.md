# ARCHITECTURE — the 9-layer Polly Harness map

> The thesis: *when an AI system fails, it is almost never the model — it is a harness layer that failed. Build the system so every failure becomes a new piece of infrastructure.*

This document is the contract between the 9-layer harness framework and the concrete files in this repo. Every layer maps to specific code. If a layer has no file, that's a bug.

The deep technical reference (with the original concentric-architecture sketch and the file-by-file map at the level of individual classes) lives at [`docs/architecture.md`](docs/architecture.md). This file is the top-level summary.

---

## The 9 layers

```
                     ╔══════════════════════════════════════╗
                     ║    USER · BROWSER (HTTP / WS / SSE)  ║
                     ╚══════════════════════════════════════╝
                                       ↓
   ┌──────────────────────────────────────────────────────────────────────┐
   │ L9 · VERIFICATION   Judges, evals, drift detection                   │
   │     G1+G2 judges · 229-case ground truth · Cohen κ · drift z-test    │
   ├──────────────────────────────────────────────────────────────────────┤
   │ L8 · TRUST & SAFETY   Adversarial + abuse defenses                   │
   │     injection detector · jailbreak gate · fraud heuristic ·          │
   │     abuse rules · chargeback block                                   │
   ├──────────────────────────────────────────────────────────────────────┤
   │ L7 · SURFACE   How humans reach the agent                            │
   │     Portfolio HTML · Gradio chat (iframe) · FastAPI /api/v1 ·        │
   │     Admin dashboard                                                  │
   ├──────────────────────────────────────────────────────────────────────┤
   │ L6 · SYNC & STATE   Persist, interrupt, audit                        │
   │     SqliteSaver · interrupt() / resume · audit log · SSE event bus   │
   ├──────────────────────────────────────────────────────────────────────┤
   │ L5 · CONTROL   LangGraph state machine — 9 nodes                     │
   │     intake → identify_customer → classify_intent → retrieve_policy → │
   │     eligibility_check → fraud_check → compute_decision →             │
   │     [await_approval] → respond                                       │
   ├──────────────────────────────────────────────────────────────────────┤
   │ L4 · VALIDATION   Boundary type / size checks                        │
   │     intake length-guard (8000 char cap) · Pydantic in/out ·          │
   │     reason-code enum                                                 │
   ├──────────────────────────────────────────────────────────────────────┤
   │ L3 · TOOLS   8 MCP-exposed typed tools                               │
   │     lookup_customer · get_order · check_return_window ·              │
   │     check_item_condition · compute_refund_amount · issue_refund ·    │
   │     search_policy · check_fraud_risk                                 │
   ├──────────────────────────────────────────────────────────────────────┤
   │ L2 · CONTEXT & MEMORY   Grounding data the agent reads               │
   │     Qdrant: policy_v1 (POLICY-001…023) ·                             │
   │     CRM JSON: 15 customers + 24 orders · SQLite: conversation state  │
   ├──────────────────────────────────────────────────────────────────────┤
   │ L1 · INSTRUCTIONS   Who Polly is, what she can do                    │
   │     system prompt · persona · intent taxonomy · escalation codes ·   │
   │     refund policy doc embedded into respond                          │
   └──────────────────────────────────────────────────────────────────────┘
                                       ↓
        ┌────────────────────────────────────────────────────────────┐
        │ EXTERNAL INFRASTRUCTURE                                    │
        │ Azure OpenAI (gpt-4o · L1+L9) · Qdrant 1.12 (L2) ·         │
        │ SQLite (L6) · Langfuse Cloud (L7+L9) · MCP server (L3)     │
        └────────────────────────────────────────────────────────────┘
```

Read from L1 up: instructions sit at the bottom; everything above adds safety, validation, or measurement that the request must pass through.

---

## Layer-by-layer file map

### L1 — Instructions

| Component | File |
|---|---|
| Main system prompt | `prompts/system_refund_agent.md` |
| Intent classifier (the heavy lifter; 70+ examples covering 7 attack patterns) | `prompts/intent_classifier.md` |
| Fraud-check sub-agent | `prompts/fraud_check_subagent.md` |
| Denial composition | `prompts/denial_rewriter.md` |
| Incident distiller | `prompts/distiller.md` |
| Refund policy doc — embedded into respond's conversational prompt | `data/policy/refund_policy_v1.md` |
| Prompt loader (Langfuse-first, local fallback, in-memory TTL cache) | `app/instructions/loader.py` |

### L2 — Context & Memory

| Component | File |
|---|---|
| Qdrant client (policy clause retrieval) | `app/context/qdrant_client.py` |
| Compaction / summarization | `app/context/compactor.py` |
| Retrieval pipeline | `app/context/retrieval.py` |
| CRM data (the grounding) | `data/crm/customers.json` · `data/crm/orders.json` |
| Persistent state (LangGraph checkpoints) | `data/state.db` (SQLite, runtime) |

### L3 — Tool Interfaces

| Component | File |
|---|---|
| Base typed tool with Pydantic in/out + observability | `app/tools/base.py` |
| Tool implementations | `app/tools/customer_tools.py` · `order_tools.py` · `policy_tools.py` · `refund_tools.py` |
| Executor (timeout, retry, layer-event emission) | `app/tools/executor.py` |
| MCP server (exposes the 8 tools over the protocol) | `app/mcp/server.py` |
| Tool registry | `app/tools/__init__.py` |
| Tool cards (markdown specs for human review) | `app/tools/tool_cards/*.md` |

### L4 — Validation

| Component | File |
|---|---|
| Intake length-guard (8000-char cap) | `app/graph/nodes/intake.py` |
| Pydantic input/output validation | `app/domain/models.py` |
| Reason-code enum | `app/domain/models.py::RefundDecisionKind` |

### L5 — Control (LangGraph)

| Component | File |
|---|---|
| StateGraph composition + edge routing | `app/graph/refund_graph.py` |
| Routing helpers (intent → respond / escalate / pipeline) | `app/graph/edges.py` |
| Nodes (each emits a LayerEvent) | `app/graph/nodes/intake.py`, `identify_customer.py`, `classify_intent.py`, `retrieve_policy.py`, `eligibility_check.py`, `fraud_check.py`, `compute_decision.py`, `respond.py`, `await_human_approval.py`, `escalate.py`, `issue_refund_node.py`, `verification.py` |

### L6 — Sync & State

| Component | File |
|---|---|
| AsyncSqliteSaver wiring | `app/graph/refund_graph.py::build_graph` |
| Approval-state checkpoint (interrupt-before-execute) | `app/graph/nodes/await_human_approval.py` |
| Approval repository (durable approval records) | `app/state/approval_repository.py` |
| SSE event bus | `app/observability/sse_bus.py` · `app/api/routes/events.py` |

### L7 — Surface

| Component | File |
|---|---|
| FastAPI factory (root portfolio + API + Gradio mounts) | `app/api/main.py` |
| Chat endpoint (the agent's front door) | `app/api/routes/chat.py` |
| CRM context endpoint (free customer/order picker) | `app/api/routes/crm.py` |
| Approvals API | `app/api/routes/approval.py` |
| Admin API | `app/api/routes/admin.py` |
| Health | `app/api/routes/health.py` |
| Portfolio template | `frontend/templates/index.html` |
| Portfolio styles (drafting-table design system) | `frontend/static/portfolio.css` |
| Custom inline chat (picker, sidebar, decision chips) | `frontend/static/chat.js` |
| Operator dashboard | `frontend/app.py` (mounted at `/admin`) |

### L8 — Trust & Safety

| Component | File |
|---|---|
| Injection / jailbreak / persona detection (intent classifier routing) | `app/graph/nodes/classify_intent.py` + `prompts/intent_classifier.md` |
| Fraud heuristic | `app/graph/nodes/fraud_check.py` |
| Abuse / chargeback gates | `app/graph/nodes/compute_decision.py::_apply_abuse_gates` |
| English-only / persona-shift / translation-jailbreak clamp | `app/graph/nodes/respond.py::CONVERSATIONAL_SYSTEM_PROMPT` |
| Azure OpenAI content filter | external (configured per deployment) |

### L9 — Verification & Observability

| Component | File |
|---|---|
| Eight axis judges | `eval/judges/*.py` (`policy_correctness`, `policy_grounding`, `injection_resistance`, `jailbreak_resistance`, `tone_appropriate`, `refusal_correctness`, `hallucination_check`, `tool_safety`) |
| Ground truth | `eval/ground_truth.json` (229 cases) |
| Production-grade thresholds | `eval/thresholds.yaml` |
| Eval runner | `eval/run_simulation.py` |
| Before/after diff + regression flag | `eval/compile_results.py` |
| Calibration (Cohen κ, drift z-test, ECE) | `eval/calibration.py` |
| Six adversarial generators | `eval/adversarial/{injection,jailbreak,llm_poisoning,hijacking,stress,abuse}.py` |
| Run JSONs + per-iteration findings | `eval/runs/v{1..21}.json` + `v{1..21}_findings.md` |
| Master tracker | `eval/IMPROVEMENT_LOG.md` |
| Synthesizing narrative | `eval/PRODUCTION_GRADE_POSTMORTEM.md` |
| Layer event emitter | `app/observability/layer_event_emitter.py` |
| Langfuse handler | `app/observability/langfuse_client.py` · `langfuse_handler.py` |
| Log spine | `app/observability/log_spine.py` |

---

## The 10th cross-cutting loop — incident → distiller → proposal

The harness has a self-improvement loop that runs against itself:

1. **Verification** (L9) scores each case, and the eval logs every regression with `[axis/case_id] expected=X actual=Y blocked=Z | response_text…` issue lines.
2. **Incidents** are stored in the durable state (`app/state/incident_repository.py`).
3. **Distiller** (`prompts/distiller.md` driven by `app/incidents/distiller.py`) reads the incidents and proposes structured changes — new prompts, new skills, new verification rules, new policy clarifications.
4. **Operator** sees the proposals at `/admin → Incidents → Run Distiller`, can accept or reject.
5. **Accepted proposals** become commits, the next eval re-runs, the loop closes.

This loop is what made v16 (poisoning + fake-policy examples), v17 (CoT-leak), and v21 (translation-wrapped fake decisions) possible — each was a structured response to a specific named failure surfaced by the prior iteration's eval.

---

## Decision path — what a single chat message becomes

```
USER message
   ↓
L7 surface → POST /api/v1/chat
   ↓
L6 sync → load conversation state (or initialize fresh on every turn — per v18's
            state-clearing fix, the per-turn fields intent / response_text /
            final_decision / candidate_decision are always nulled before invoke)
   ↓
L5 control → graph.ainvoke(state, config={"thread_id": conversation_id})
   ↓
   intake (L4 length-guard) →
   classify_intent (L1 prompt + L8 safety classes) →
       branches:
         off_topic / inquiry / complaint → respond (skip pipeline)
         emotional_pressure / injection_attempt → escalate
         refund_request / exchange_request → identify_customer → ...pipeline
   ↓
   [pipeline:] retrieve_policy (L2 Qdrant) → eligibility_check (L3 tools) →
               fraud_check (L3+L8) → compute_decision (L5 logic) →
               [await_human_approval (L6 interrupt) if > tier cap]
   ↓
   respond (L1 prompt with policy doc + L8 English-only clamp) →
       composes DECISION · KIND · $AMOUNT · clauses chip
   ↓
L9 verification (offline, on every eval run, not on every chat turn)
   ↓
L7 surface ← ChatResponse → chip rendered in browser
```

Eight of these nine nodes are **deterministic, not LLM-driven**. Only `classify_intent` and `respond` call the LLM. Every other step is a typed tool call or a graph transition. Every node emits a LayerEvent the SSE bus picks up, so each chat turn is a fully observable timeline in `/admin → Operations → Live Trace`.

---

## How the architecture connects to the eval iteration story

The three architectural inflections account for **38.1 of the 60.5 cumulative percentage points** of pass-rate gain:

- **v5 (real L9 LLM-judge, +22.4pp)** — replaced two scoring stubs with real `gpt-4o-mini` judges. C1 Injection: 59.5% → 95.2%. C3 LLM Poisoning: 3% → 78.8%. C4 Hijacking: 40% → 92%. **One change, three categories.**
- **v14 (A6 axis-judge restructure, +7.4pp)** — recognized the A6 axis was a two-judge AND that couldn't be satisfied by natural empathetic responses. Removed `refusal_correctness` from A6. A6: 0% → 45.5%.
- **v15 (conversational short-circuit + LLM-composed respond, +8.3pp)** — restructured `route_after_classify_intent` to branch three ways (conversational / safety / pipeline), and let the LLM compose conversational replies with the CRM context. A6: 45.5% → 93.9%. C6 Abuse: 45.5% → 93.9%. A4 → 100%. C2 → 100%. C4 → 100%.

Every other iteration tuned the consequences of those three structural decisions. See [`eval/PRODUCTION_GRADE_POSTMORTEM.md`](eval/PRODUCTION_GRADE_POSTMORTEM.md) for the full synthesis.

---

## What this architecture is *not*

- It is **not** a single-monolith LLM call wrapped in a prompt. Eight of nine pipeline nodes are deterministic Python or typed tool calls — the LLM is on the critical path twice, not nine times.
- It is **not** "production-grade because of nine layers." It is production-grade because there is an eval framework that can falsify each layer's claims and an audit trail showing every safety improvement is attributable to one named change.
- It is **not** prompt-bashing. Twelve of seventeen iterations changed Python code (and five changed only the scoring layer). Two prompt iterations carry meaningful weight (v16, v17, v21 — and even those are structured few-shot additions, not "add a sentence to the system prompt and hope").

---

## Further reading

- [`eval/PRODUCTION_GRADE_POSTMORTEM.md`](eval/PRODUCTION_GRADE_POSTMORTEM.md) — the synthesizing narrative across v1 → v17 (with v18-v21 addenda in their findings docs)
- [`eval/IMPROVEMENT_LOG.md`](eval/IMPROVEMENT_LOG.md) — master tracker, one row per iteration
- [`docs/architecture.md`](docs/architecture.md) — the deep technical reference (file-by-file at the class level)
- [`eval/runs/v{1..21}_findings.md`](eval/runs/) — per-iteration hypothesis + intervention + measured Δ + residual
