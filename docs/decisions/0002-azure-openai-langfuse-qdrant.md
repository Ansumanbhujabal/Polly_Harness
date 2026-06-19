# ADR-0002: Azure OpenAI + Langfuse + Qdrant — the "single pane" observability stack

**Status:** Accepted
**Date:** 2026-06-18

## Context

Production-grade agentic systems need prompt management, traces, metrics, evals, and (optionally) a semantic cache. The naive choice is a bag of point tools — LangSmith for traces, Promptfoo for evals, MLflow for prompt versions, Redis for cache. That bag is four integrations, four auth surfaces, four UI conventions, and four points of failure. At 7-day take-home scope, integration time on auxiliary tools squeezes out time spent on the harness narrative.

## Decision

- **LLM:** Azure OpenAI (deployments `gpt-4o` for chat, `text-embedding-3-small` for embeddings). The author has Azure credits and the deployment is regional / latency-bounded.
- **Vector store:** Qdrant 1.12 in a private Docker network. Local-first, no vendor lock-in, embeds clauses with `fastembed` (`BAAI/bge-small-en-v1.5`) for deterministic retrieval.
- **Observability + Prompts + Evals + Cache:** Langfuse Cloud (free tier). Single pane of glass: prompts versioned and hot-reloaded, traces aggregated by `conversation_id`, judge-based eval scores stored as dataset runs, metrics dashboarded.

## Consequences

**Why this stack wins for this scope:**
- One integration surface for prompts, traces, evals, and (optional) semantic cache — `app/observability/langfuse_client.py` is one file, not four.
- Langfuse failures are caught at the `push_event` boundary and never raise — the system continues without observability if the cloud is down, fail-open by design.
- Qdrant runs alongside the FastAPI container in `docker-compose.yml` on a private bridge network — no external dependency for the refund-policy RAG path.
- Azure OpenAI's tool-call format is the most reliable in the OpenAI family, matching the LangGraph + LangChain expectation.

**What we gave up:** Multi-region failover, multi-cloud portability, the ability to swap one observability tool for another without touching `langfuse_client.py`. All of these are real production concerns and are documented as roadmap items in the README.

**Verification:** `tests/test_observability.py::test_push_event_swallows_langfuse_failure_and_logs_warn` proves fail-open semantics. The `EVENT_TYPE_CATALOG` registry in `app/observability/event_types.py` is the single source of truth for what every layer emits.
