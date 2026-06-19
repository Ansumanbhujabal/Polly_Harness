# ADR-0001: LangGraph as the Orchestration Layer

**Status:** Accepted
**Date:** 2026-06-18

## Context

The harness needs a single Orchestration layer (L6) that owns the state machine, the conditional edges, the retry policy, durable mid-conversation state, and a synchronous-feeling human-in-the-loop approval gate. The candidates considered were LangGraph, CrewAI, and raw `langchain` function-calling.

## Decision

Use **LangGraph 0.2+** with its `SqliteSaver` checkpointer and `interrupt()` primitive.

## Consequences

**Why this fits the harness frame:**
- LangGraph's `StateGraph` maps 1:1 to Layer 6 (Orchestration).
- The `SqliteSaver` is Layer 5 (Durable State) — same SQLite file holds checkpoints + the Repository's audit tables, so a single-file backup captures the full conversation state.
- `interrupt()` is the native expression of an HITL approval gate — the graph suspends, the API surfaces a `PendingApproval`, the human decides, `aresume()` continues from the checkpoint.
- Subgraphs (`fraud_check`) map to Layer 7 (Sub-agents) with isolated state — the parent never sees the 90-day refund history dump, only the distilled `FraudCheckResult`.

**What we gave up:** CrewAI's role-prompt ergonomics, and the lighter-weight feel of raw function-calling. Both would have required us to hand-build durable state, retries, and the approval gate from scratch — at 7-day take-home scope, building those would have squeezed out time for the layers that differentiate the submission (Verification, Incident Loop).

**Verification:** The graph topology lives in `app/graph/refund_graph.py`. The approval gate is exercised by `tests/test_graph.py::test_interrupt_and_resume_for_above_cap_refund`, which was the FIRST test written (a discipline flagged by the design's risk register §10 and visible in commit history).
