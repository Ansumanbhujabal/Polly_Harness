# Architecture — The Harness Engineering Map

This document is the contract between the 9-layer harness engineering framework and the concrete files in this repo. Every layer maps to specific code. If a layer has no file, that's a bug.

> The thesis of harness engineering: *when an AI system fails, it is almost never the model — it is a harness layer that failed. Build the system so every failure becomes a new piece of infrastructure.*

---

## The Concentric Architecture

```
+-----------------------------------------------------------------+
|                         ORCHESTRATION                           |
|  app/graph/refund_graph.py — LangGraph StateGraph with          |
|  retries, interrupt-before-execute, approval gates              |
+-----------------------------------------------------------------+
|  +-------------------+        +----------------------------+    |
|  |    SKILL LAYER    |        |  VERIFICATION + OBSERVE    |    |
|  | skills/*.md +     |        | app/verification/* +       |    |
|  | app/skills/loader |        | Langfuse traces + evals    |    |
|  +-------------------+        +----------------------------+    |
|           |                                ^                    |
|  +-----------------------------------------------------------+  |
|  |                    DURABLE STATE                          |  |
|  |  SQLite + LangGraph SqliteSaver + app/state/repositories  |  |
|  +-----------------------------------------------------------+  |
|           |                                |                    |
|  +-------------------+        +----------------------------+    |
|  | EXECUTION ENV.    | <----> |     TOOL INTERFACES        |    |
|  | Docker container, |        | MCP server (stdio) +       |    |
|  | sandboxed tool    |        | app/tools/*.py Pydantic    |    |
|  | executor with     |        | schemas + tool_cards/*.md  |    |
|  | timeout + retry   |        |                            |    |
|  +-------------------+        +----------------------------+    |
|           |                                ^                    |
|  +-----------------------------------------------------------+  |
|  |             CONTEXT DELIVERY & MANAGEMENT                 |  |
|  |  Qdrant policy RAG + app/context/compactor.py +           |  |
|  |  customer_context_builder.py                              |  |
|  +-----------------------------------------------------------+  |
|           |                                ^                    |
|  +-------------------+        +----------------------------+    |
|  |    SUB-AGENTS     |        |      INSTRUCTIONS          |    |
|  | eligibility +     |        |  agentic.md + prompts/* +  |    |
|  | tone subgraphs    |        |  Langfuse prompt registry  |    |
|  +-------------------+        +----------------------------+    |
|           \________________________________________/            |
|                               |                                 |
|                         +-----------+                           |
|                         |   MODEL   |  Azure OpenAI             |
|                         | (Reasoning|  (GPT-4o / GPT-4.1)       |
|                         |  Engine)  |                           |
|                         +-----------+                           |
+-----------------------------------------------------------------+

       FEEDBACK LOOP (the doc's thesis baked in):
       Verification failure / HITL override
                  ↓
       app/learning/incident_logger.py
                  ↓
       data/incidents/<id>.yaml
                  ↓
       app/learning/incident_distiller.py
                  ↓
       PR-ready diff: new skill / verification rule / policy clarification
```

---

## Layer → File Map

| # | Layer | Files | Verification |
|---|-------|-------|--------------|
| **1** | Instructions | `agentic.md`, `prompts/system_refund_agent.md`, `prompts/intent_classifier.md`, `prompts/denial_rewriter.md` | Langfuse prompt registry mirrors these; runtime fetches by version |
| **2** | Context Delivery | `app/context/retriever.py` (Qdrant), `app/context/compactor.py`, `app/context/customer_context_builder.py` | Compacts history > 4k tokens; retrieves top-3 policy clauses per turn |
| **3** | Tool Interfaces | `app/mcp/server.py` (MCP stdio server), `app/tools/*.py` (Pydantic), `app/tools/tool_cards/*.md` | All 8 tools expose JSON schema; MCP-compliant tool_call envelope |
| **4** | Execution Environment | `Dockerfile`, `docker-compose.yml`, `app/tools/executor.py` (timeout, retry, structured error envelope) | Tools never make real network calls outside the container |
| **5** | Durable State | `app/state/sqlite_checkpointer.py`, `app/state/repositories.py`, SQLite at `data/state.db` | LangGraph resumes mid-conversation across restarts |
| **6** | Orchestration | `app/graph/refund_graph.py`, `app/graph/state.py` | LangGraph nodes: intake → identify → policy_lookup → eligibility → (approve\|deny\|escalate) → execute → respond. `interrupt()` before `issue_refund` when amount > cap |
| **7** | Sub-agents | `app/graph/subagents/eligibility.py`, `app/graph/subagents/tone.py`, `app/graph/subagents/fraud_check.py` | Each subagent has isolated context; main agent receives summary only |
| **8** | Skill Layer | `skills/*.md` (5 playbooks), `app/skills/loader.py`, `app/skills/registry.py` | Loader injects 1-2 skills into context per turn based on intent classification |
| **9** | Verification & Observability | `app/verification/policy_assertions.py`, `app/verification/injection_check.py`, `app/observability/langfuse_client.py`, `app/observability/layer_event_emitter.py` | Post-decision checks fail-closed; every node emits a layer-tagged event |

---

## Cross-Cutting Infrastructure

### The Failure→Infrastructure Loop (Layer 9.5)
- `app/learning/incident_logger.py` — writes `data/incidents/<timestamp>_<reason>.yaml` whenever a verification check fails OR a HITL override occurs
- `app/learning/incident_distiller.py` — periodic job that reviews incidents, proposes new skill markdowns / verification rules / policy clarifications as PR-ready diffs

### Semantic Cache (cross-cuts Layers 2, 3)
- `app/cache/semantic_cache.py` — keyed on `(intent_hash, policy_clause_ids_hash)`; reduces Azure OpenAI cost and latency on repeat queries

### Observability Spine
- Every node in `refund_graph.py` calls `layer_event_emitter.emit(layer="LAYER_X", event="...", payload=...)`
- The emitter publishes to (a) Langfuse trace, (b) SSE stream consumed by the admin dashboard, (c) the dynamic architecture diagram in the frontend

---

## Why each pick (short form — see `docs/decisions/` for full ADRs)

- **LangGraph** → native checkpointers map to Durable State; subgraphs map to Sub-agents; `interrupt()` maps to Orchestration approval gates
- **Azure OpenAI** → user has credits; OpenAI tool-call format is the most reliable; Langfuse integration is first-class
- **Langfuse** → single pane: prompts, traces, datasets, LLM-judge evals, semantic cache, metrics — replaces 4 separate tools
- **Qdrant local** → no vendor lock-in, embeds in Docker, production-grade filtering
- **Gradio + FastAPI** → free, deploys to HF Spaces, supports custom HTML for the dynamic diagram
- **MCP server** → the harness doc names MCP explicitly as the structured-schema pattern for Layer 3; honoring that is the senior signal
- **SQLite over MongoDB** → simpler for single-container HF Spaces deploy; SqliteSaver is battle-tested in LangGraph
- **HF Spaces** → free public URL, widely recognizable, 16GB RAM, Docker SDK supports our multi-process stack

---

## What this architecture is NOT

- Not microservices. Single container, single process group. Simpler is better at 7-day scope.
- Not voice-enabled. Explicit scope cut. Documented in `docs/decisions/0005-skip-voice.md`.
- Not multi-tenant. One mock store, one policy version. Multi-tenancy is a "next iteration" note in the README.
- Not real-payment-integrated. `issue_refund` writes to SQLite and emits an event; no Stripe/etc. wired.

---

## Diagram Drift Discipline

If a file is added that doesn't map to a layer, either (a) map it, or (b) document why it's cross-cutting infra (like the cache or incident loop). No orphan files. The architecture map is the source of truth.
