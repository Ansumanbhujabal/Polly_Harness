# SPEC: Orchestration

**Layer:** L6 — Orchestration
**Owner:** `app/graph/`

The Orchestration layer is the LangGraph state machine that turns one customer message into a verified refund decision. It owns the node topology, the conditional edges, the `interrupt()` approval gate, the retry policy, and the wiring of every other layer into one async-callable graph. This layer is the vertical-slice integration apex — all of L1, L2, L3, L5, L7, L8, L9 flow through here.

## Contract

```python
from app.graph import build_graph, AgentState, RefundGraph
```

- `build_graph() -> RefundGraph` — compiles the LangGraph `StateGraph` with the `SqliteSaver` checkpointer from `app.state.get_checkpointer()`. Singleton on first call.
- `RefundGraph.ainvoke(state: AgentState, config: dict) -> AgentState` — runs the graph for one turn, honoring `interrupt()` (returns early with `state.awaiting_human_approval = True`).
- `RefundGraph.aresume(config: dict, approval: Literal["approved", "denied"]) -> AgentState` — resumes a suspended graph at the `await_human_approval` node with the supplied resolution.

`AgentState` is defined in `app/domain/models.py` (foundation commit) and re-exported from `app.graph.state` for ergonomic graph-side imports.

## Node topology

```
intake
   └── classify_intent
         └── identify_customer
               └── retrieve_policy
                     └── (intent == refund_request)
                           └── eligibility_check
                                 └── fraud_check  (sub-agent)
                                       └── compute_decision
                                             └── verification  (parallel L9 checks)
                                                   ├── verified, amount ≤ cap → issue_refund_node → respond
                                                   ├── verified, amount > cap → await_human_approval (interrupt)
                                                   │                              ↓ on resume
                                                   │                              ├── approved → issue_refund_node → respond
                                                   │                              └── denied   → escalate → respond
                                                   └── blocked → escalate → respond
```

Off-path early returns:

- `classify_intent` → `intent ∈ {off_topic, inquiry}` → `respond` directly (skip identify+policy+eligibility).
- `identify_customer` → identity mismatch → `escalate` with `reason_code = IDENTITY_MISMATCH`.

## Critical behaviors

- **`test_interrupt_and_resume_for_above_cap_refund` is the FIRST test written.** Listed in §10 of the design as a named risk. The builder's commit history must show this test landed before any node-implementation commit. Reviewer asserts this via `git log`.
- **Every node** emits `L6_ORCHESTRATION / node_entered` on entry AND `L6_ORCHESTRATION / node_exited` on exit. No exceptions. A single helper (e.g., `@node_event_decorator` or `with NodeEventScope(name):`) is acceptable as long as the events fire.
- **Conditional edges** read `state.candidate_decision.kind` and `state.verification.blocked`. Edges are pure functions in `app/graph/edges.py` — no side effects, no LLM calls.
- **Retry policy:** tool failures retry at the L4 executor (twice with exponential backoff). The graph does NOT add a retry layer on top. The only graph-level retry is `langchain_core.exceptions.OutputParserException` on the `compute_decision` node — retry once with a stricter format reminder, then escalate with `reason_code = LLM_OUTPUT_INVALID`.
- **`interrupt()` semantics:** when `compute_decision` returns a `RefundDecision` with `requires_human_approval=True` AND verification did not block, the `await_human_approval` node is reached. Before suspending, it writes a `PendingApproval` row via `app.state.get_repository().save_approval(...)` so the human-facing dashboard can list it. Then it calls LangGraph's `interrupt(...)` which suspends the graph state via `SqliteSaver`. `aresume()` reads `state.approval_resolution` and routes via an edge.
- **Off-topic and OOS routing:** `intent ∈ {off_topic, inquiry}` flows directly to `respond` with a templated redirect. Three consecutive off-topic turns trigger escalation per the agentic.md doctrine.
- **No real LLM in unit tier.** The graph factory accepts an injectable `llm` parameter for tests; production wires Azure OpenAI via `langchain_openai.AzureChatOpenAI` bound to `settings.AZURE_OPENAI_DEPLOYMENT_CHAT`.

## Events emitted

- `L6_ORCHESTRATION / node_entered` — payload: `{node: str, conversation_id: str}` — one per node entry.
- `L6_ORCHESTRATION / node_exited` — payload: `{node: str, conversation_id: str, latency_ms: float}` — one per node exit.
- `L6_ORCHESTRATION / interrupt_raised` — payload: `{approval_id: str, reason: str, amount_usd: float}` — emitted ONLY from `await_human_approval` before suspending.

Tool-level, retrieval, verification, sub-agent, skill events are emitted by their respective owning layers and seen here through the trace; the graph does NOT re-emit them.

## Files

```
app/graph/__init__.py             # exports build_graph, AgentState, RefundGraph
app/graph/state.py                # re-export of AgentState from app.domain.models
app/graph/refund_graph.py         # build_graph(), node registration, edge wiring
app/graph/edges.py                # pure conditional-edge functions
app/graph/nodes/__init__.py
app/graph/nodes/intake.py
app/graph/nodes/classify_intent.py
app/graph/nodes/identify_customer.py
app/graph/nodes/retrieve_policy.py
app/graph/nodes/eligibility_check.py
app/graph/nodes/compute_decision.py
app/graph/nodes/verification.py
app/graph/nodes/issue_refund_node.py
app/graph/nodes/escalate.py
app/graph/nodes/respond.py
app/graph/nodes/await_human_approval.py
```

## Dependencies

- `app.domain.models` — `AgentState`, `RefundDecision`, `RefundDecisionKind`, `VerificationResult`, `PendingApproval`
- `app.instructions` — `load_system_prompt`, `load_skill_router_prompt` (L1)
- `app.context` — `get_retriever`, `build_customer_context`, `compact_messages` (L2)
- `app.tools` — `get_tool_by_name` and the typed tools (L3, via `app/tools/executor.run_tool`)
- `app.state` — `get_checkpointer`, `get_repository` (L5)
- `app.graph.subagents` — `run_fraud_check` (L7)
- `app.skills` — `route_skills_for_intent` (L8)
- `app.verification` — `run_verification_pipeline` (L9)
- `app.observability` — `get_emitter`
- `langgraph.graph.StateGraph`, `langgraph.types.interrupt`
- `langchain_openai.AzureChatOpenAI`

Out of scope: API surface (owned by `SPEC_API`), frontend (`SPEC_FRONTEND`), MCP protocol (`SPEC_MCP_SERVER`).

## Tests

`tests/test_graph.py` — minimum tests:

1. `test_graph_happy_path_standard_refund_under_cap` — CUST-001 + ORD-1001 within window, amount under cap → ISSUE.
2. `test_interrupt_and_resume_for_above_cap_refund` — **WRITTEN FIRST** — CUST-002 (VIP) + ORD-1015 ($1,200, cap $500) → `ainvoke` returns with `awaiting_human_approval=True`; `aresume("approved")` continues to ISSUE; separately `aresume("denied")` routes to ESCALATE.
3. `test_blocked_verification_routes_to_escalate` — injection-bait message → L9 block → escalate path.
4. `test_fraud_check_high_routes_to_escalate` — CUST-009 (serial refunder) → fraud risk score ≥ 0.5 → escalate.
5. `test_intent_off_topic_short_circuits_to_respond_with_redirect` — message "what's the weather?" → respond directly, skip identity/policy nodes.
6. `test_customer_identity_mismatch_blocks_refund` — order belongs to a different customer than the one claiming → escalate `IDENTITY_MISMATCH`.
7. `test_carrier_delay_extension_keeps_within_window` — ORD-1028 (17d carrier delay) → return-window check passes.
8. `test_vip_60d_return_window_applied` — CUST-002 VIP, 40-day-old order → return window passes.
9. `test_every_node_emits_entered_and_exited` — run happy path; capture LayerEvents; assert one `node_entered` and one `node_exited` per node visited.
10. `test_state_persists_across_session_via_checkpointer` — invoke; close; re-open; resume from checkpoint; final state matches.
11. `test_no_real_llm_calls_in_unit_tier` — patch `AzureChatOpenAI.ainvoke` to raise on call; run all unit-tier graph tests; none of them call it (assert the patch was never tripped).

Use the injectable `llm` parameter for stub LLM responses. Use the existing `all_customers` / `all_orders` fixtures from `tests/conftest.py`.

## Done criteria

- [ ] All 11 node files + `edges.py` + `refund_graph.py` + `state.py` + `__init__.py` + `nodes/__init__.py` exist (16 files total under `app/graph/`).
- [ ] All 11 graph tests pass under `pytest -m integration tests/test_graph.py`.
- [ ] `test_interrupt_and_resume_for_above_cap_refund` was the FIRST test written — `git log --diff-filter=A --follow -- tests/test_graph.py | head -1` returns the commit that introduced this test BEFORE any commit touching `app/graph/nodes/`. Reviewer asserts this.
- [ ] No node bypasses the event emitter — `test_every_node_emits_entered_and_exited` covers this contract.
- [ ] The graph never reaches `issue_refund_node` when `state.verification.blocked is True` — covered by test 3 plus a defensive assert at the top of `issue_refund_node`.
- [ ] `mypy --strict app/graph/` passes (best-effort).
