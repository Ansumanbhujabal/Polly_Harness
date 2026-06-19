# Refund Harness — A Harness-Engineered AI Customer Support Agent

> *"Most refund agents fail not because the model is wrong, but because the **harness** around the model is missing."*

This repository is a vertical-slice production-grade build of an AI customer support agent for e-commerce refund processing — but the real subject is **harness engineering**. The 9-layer architecture from [`docs/architecture.md`](docs/architecture.md) is the spine of the system, and every file in the repo maps to a layer.

## Why this architecture matters

A reliable agent is not a smarter model. It is an *outer system* that makes the model's failures recoverable, observable, and reversible. The harness has nine layers — each catches a different class of failure:

1. **Instructions** — `agentic.md` — the contract
2. **Context Delivery** — RAG, compaction, summarization
3. **Tool Interfaces** — MCP-compliant structured schemas
4. **Execution Environment** — sandboxed, timeout-bounded
5. **Durable State** — survives crashes and restarts
6. **Orchestration** — retries, approval gates, human-in-the-loop
7. **Sub-agents** — specialists for context-quality
8. **Skill Layer** — reusable procedural playbooks
9. **Verification & Observability** — external checks + traces

And a **10th cross-cutting loop**: every failure surfaced by Verification becomes a structured incident, which is distilled into proposed new skills, verification rules, or policy clarifications. *Harness engineering turns failures into infrastructure.*

## Quick start

```bash
# 1. Configure
cp .env.example .env
# Fill in AZURE_OPENAI_*, LANGFUSE_*, QDRANT_URL

# 2. Install
make install

# 3. Seed Qdrant + SQLite
make seed

# 4. Run
make run         # local
# OR
make docker-up   # containerized
```

App listens on `http://localhost:7860`. Chat is at `/`, admin dashboard at `/admin`.

## Live demo

🔗 **[refund-harness on Hugging Face Spaces](https://huggingface.co/spaces/__TBD__/refund-harness)**

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full 9-layer map with file pointers.

## Architectural Decisions

Every significant decision has an ADR in [`docs/decisions/`](docs/decisions/). Highlights:
- [0001 — LangGraph over CrewAI / raw function calling](docs/decisions/0001-langgraph-as-orchestration.md)
- [0002 — Azure OpenAI + Langfuse + Qdrant single-pane observability](docs/decisions/0002-azure-openai-langfuse-qdrant.md)
- [0003 — MCP protocol for the tool layer](docs/decisions/0003-mcp-tool-protocol.md)
- [0004 — Failure-to-infrastructure incident loop](docs/decisions/0004-incident-loop-feedback.md)
- [0005 — Skipping voice in scope](docs/decisions/0005-skip-voice.md)

## Failure Modes Catalog

| Failure Mode | Layer Responsible | Mitigation | Test |
|---|---|---|---|
| Prompt injection in customer message | Verification (#9) | `injection_check.py` regex + LLM-judge fallback | `test_verification.py::test_injection_detected` |
| Tool timeout | Execution Env (#4) | `executor.py` 10s timeout + 2 retries with backoff | `test_executor.py::test_timeout_then_retry` |
| Policy chunk miss (RAG returns wrong clause) | Context Delivery (#2) | Top-K=5 + re-rank + fallback to full policy doc | `test_retriever.py::test_falls_back_to_full_doc` |
| Customer ID collision | Tool Interfaces (#3) | Pydantic validation + unique constraint in SQLite | `test_tools.py::test_duplicate_customer_id_rejected` |
| LLM hallucinated refund ID | Verification (#9) | `policy_assertions.py` cross-checks issued refund_id format | `test_verification.py::test_hallucinated_id_blocked` |
| Customer at $200.01 (cap edge) | Orchestration (#6) | `interrupt()` triggers HITL approval | `test_graph.py::test_cap_edge_triggers_interrupt` |
| Stale prompt in cache | Observability (#9) | Langfuse prompt version pinning + TTL cache | `test_langfuse_client.py::test_prompt_version_pinned` |
| LangGraph state corruption mid-run | Durable State (#5) | `SqliteSaver` writes are atomic; resume tested in CI | `test_state.py::test_resume_after_crash` |

## How to Extend

| You want to | Edit |
|---|---|
| Add a new policy rule | `data/policy/refund_policy_v1.md` + add an eval case to `eval/scenarios.yaml` + bump version |
| Add a new tool | Implement in `app/tools/`, register in `app/mcp/server.py`, add `tool_cards/<tool>.md`, write a unit test |
| Add a new skill | Drop a markdown playbook in `skills/`, the loader picks it up; tag with `intent:` frontmatter |
| Add a new verification check | Implement in `app/verification/`, register in `verification_pipeline.py`, write a unit test |
| Add a new sub-agent | Add subgraph in `app/graph/subagents/`, wire from main graph as conditional edge |
| Change the LLM | Update `app/observability/langfuse_client.py` model param + `.env` |

## Scope (v0.1) — what is intentionally out

- **No voice pipeline.** Documented in [ADR-0005](docs/decisions/0005-skip-voice.md). Stub interface in `frontend/static/voice_extension.md` for future.
- **No real payment processor.** `issue_refund` writes to SQLite and emits an event. Production would wire Stripe / Adyen.
- **No multi-tenant policy versioning.** One store, one policy version. The change-control mechanism in POLICY-023 makes this extensible.
- **No real CRM.** 15 mock customers + 30 mock orders, deterministically seeded.

These are tradeoffs, not omissions. Depth in the harness was prioritized over feature breadth.

## Observability

Every LangGraph node emits a layer-tagged event. Events flow to:
- **Langfuse** for the audit trail (traces, metrics, cost)
- **SSE stream** consumed by the admin dashboard (live reasoning log)
- **Dynamic architecture diagram** in the frontend (pulses the active layer)

## Evals

```bash
make eval
```

Runs:
- `eval/scenarios.yaml` — 12 deterministic seed cases
- `eval/generated/` — 50+ adversarial mutations synthesized by `eval/generate_adversarial_cases.py`
- LLM-as-judge evaluators (policy_correctness, tone_appropriate, injection_resistance, hallucination_check)
- Pass-rate report posted to Langfuse dataset run

CI runs the eval suite on every PR (`.github/workflows/evals.yml`).

## Tech Stack

| Concern | Pick |
|---|---|
| Language / deps | Python 3.11+ / **uv** |
| Agent loop | **LangGraph** |
| Model | **Azure OpenAI** (GPT-4o / GPT-4.1) |
| Vector DB | **Qdrant** (local) |
| State | **SQLite** + LangGraph `SqliteSaver` |
| Tool protocol | **MCP** (stdio) |
| Observability + Prompts + Evals + Cache | **Langfuse** |
| API | **FastAPI** + SSE |
| Frontend | **Gradio** + custom HTML for dynamic diagram |
| Container | **Docker** (single image) |
| Host | **Hugging Face Spaces** (Docker SDK) |

## License

MIT — see [LICENSE](LICENSE).

---

Built by Ansuman SS Bhujabala · AI Engineer · 2026
