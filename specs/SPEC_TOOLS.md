# SPEC: Tools Layer

**Layer:** L3 — Tool Interfaces
**Owner:** `app/tools/`

The Tools layer exposes the 8 capabilities the agent can use to act on the mock CRM and policy systems. Every tool has a typed Pydantic input and output, runs inside a sandboxed executor with timeout and retry, and emits `LayerEvent`s on every call.

## Contract

The Tools layer exports two things to the rest of the system:

```python
from app.tools import TOOLS  # list[BaseTool] — used by MCP server + LangGraph
from app.tools import get_tool_by_name  # fast lookup
```

Each tool is a class that inherits from `BaseTool` (defined in this layer) with:
- `name: str` — stable identifier
- `description: str` — one-paragraph description loaded into the prompt
- `Input` / `Output` — Pydantic submodels
- `async run(input: Input) -> Output` — implementation

## The 8 Tools

| Tool | Purpose | Returns |
|---|---|---|
| `lookup_customer` | Find a customer by `customer_id` OR by `email` | `Customer` |
| `get_order` | Fetch an order by `order_id`, scoped to a customer | `Order` |
| `check_return_window` | Compute days since delivery + eligibility | `{within_window: bool, days_since_delivery: int, applied_clause: str}` |
| `check_item_condition` | Read the warehouse-attested condition from the order | `{condition: str, eligibility: str, applied_clause: str}` |
| `compute_refund_amount` | Apply policy math (full / partial / store credit) | `{kind: RefundDecisionKind, amount_usd: float, cited_clauses: list[str]}` |
| `issue_refund` | Write the refund record to SQLite + emit event | `{refund_id: str, status: "issued", amount_usd: float}` |
| `escalate_to_human` | Mark the conversation for human review | `{escalation_id: str, reason_code: str}` |
| `search_policy` | Free-text search of the policy doc via Qdrant | `list[PolicyClause]` |

## Behaviors

- **`lookup_customer`**: case-insensitive email match. If both `customer_id` and `email` provided, prefer ID. Returns `None` (not raises) when no match — caller decides whether that's an error.
- **`get_order`**: must accept a `customer_id` and verify the order belongs to that customer. Returns `None` on mismatch (this is the IDENTITY_MISMATCH precursor).
- **`check_return_window`**: applies POLICY-002 (VIP=60d) vs POLICY-001 (standard=14d). Honors POLICY-010 carrier delay extension.
- **`check_item_condition`**: maps `item_condition_reported` to a policy verdict per POLICY-006..009. `damaged_on_arrival` always returns `eligibility="full_refund_if_within_14d"`. Final-sale / digital / personal_care_opened items get `eligibility="non_refundable"`.
- **`compute_refund_amount`**: pure function over already-fetched data. Does NOT call other tools.
- **`issue_refund`**: writes to `data/state.db` table `refunds` with a generated ID `REF-{conversation_id}-{n}`. Must be idempotent on retry (insert-or-noop).
- **`escalate_to_human`**: writes a row to `human_approvals` table. Reason codes: `ABUSE_FLAG_PRESENT`, `ACTIVE_CHARGEBACK`, `AMOUNT_EXCEEDS_CAP`, `IDENTITY_MISMATCH`, `THREAT_DETECTED`, `INJECTION_DETECTED`, `FRAUD_RISK_HIGH`, `OUT_OF_SCOPE`.
- **`search_policy`**: top-K=5 from Qdrant, returns `PolicyClause` objects with `clause_id` parsed from the chunk metadata.

## Sandbox executor

Tools never call out to the network directly. They go through `app/tools/executor.py`:

```python
async def run_tool(tool: BaseTool, payload: dict) -> dict:
    """Run tool with timeout (settings.TOOL_TIMEOUT_SECONDS) and retry
    (settings.TOOL_MAX_RETRIES) with exponential backoff. Returns a
    structured envelope: {ok: bool, output: ..., error: ..., latency_ms, retries}.
    Always emits L4_EXECUTION events on start, success, retry, fail.
    """
```

## Tool cards

Each tool has a companion markdown in `app/tools/tool_cards/<name>.md` describing intent, inputs, outputs, failure modes. Loaded by the MCP server into the protocol description.

## Events emitted

- `L3_TOOLS / tool_invoked` on every call (payload: tool name, input)
- `L3_TOOLS / tool_succeeded` on success (payload: latency, output summary)
- `L4_EXECUTION / tool_retry` on retry
- `L4_EXECUTION / tool_failed` on terminal failure

## Files

```
app/tools/
├── __init__.py             # exports TOOLS, get_tool_by_name, BaseTool
├── base.py                 # BaseTool abstract class
├── executor.py             # sandbox executor (timeout/retry/event)
├── customer_tools.py       # lookup_customer
├── order_tools.py          # get_order
├── policy_tools.py         # check_return_window, check_item_condition,
│                           # compute_refund_amount, search_policy
├── refund_tools.py         # issue_refund, escalate_to_human
└── tool_cards/
    ├── lookup_customer.md
    ├── get_order.md
    ├── check_return_window.md
    ├── check_item_condition.md
    ├── compute_refund_amount.md
    ├── issue_refund.md
    ├── escalate_to_human.md
    └── search_policy.md
```

## Dependencies

- `app.domain.models` — Customer, Order, PolicyClause, RefundDecision, RefundDecisionKind, ToolInvocation
- `app.observability` — get_emitter, get_logger
- `app.config` — settings
- `app.state.repositories` — for issue_refund / escalate_to_human (CRUD on SQLite)
- `app.context.retriever` — for search_policy (Qdrant)

Out of scope: LangGraph, MCP — those layers wrap these tools, not the other way around.

## Tests

`tests/test_tools.py` — minimum tests:

1. `test_lookup_customer_by_id_succeeds` — CUST-001 returns Marcus Chen.
2. `test_lookup_customer_by_email_case_insensitive`
3. `test_lookup_customer_returns_none_for_unknown`
4. `test_get_order_scoped_to_customer_succeeds` — ORD-1001 + CUST-001.
5. `test_get_order_returns_none_on_customer_mismatch` — ORD-1001 + CUST-002 → None.
6. `test_check_return_window_within_for_standard_14d` — recent order, standard customer, returns within=True.
7. `test_check_return_window_outside_for_standard_after_14d` — ORD-1007 (>30d old), CUST-004 (standard) → False.
8. `test_check_return_window_vip_60d_extension` — order 40 days old + VIP returns within=True.
9. `test_check_return_window_honors_carrier_delay` — ORD-1028 with 17d carrier delay extends window.
10. `test_check_item_condition_damaged_returns_full` — ORD-1020.
11. `test_check_item_condition_used_returns_partial` — ORD-1006.
12. `test_check_item_condition_final_sale_returns_non_refundable` — ORD-1024.
13. `test_compute_refund_amount_full_path`
14. `test_compute_refund_amount_partial_50` — used item, returns 50%.
15. `test_compute_refund_amount_partial_75_vip` — VIP opened item >14d.
16. `test_issue_refund_writes_to_sqlite_and_returns_id`
17. `test_issue_refund_idempotent_on_retry` — same conversation_id+order_id returns same refund_id.
18. `test_escalate_to_human_writes_approval_row`
19. `test_search_policy_returns_relevant_clauses` — query "30 day return" returns POLICY-001 in top-3.
20. `test_executor_retries_on_transient_error_then_succeeds`
21. `test_executor_fails_after_max_retries`

Use the `all_customers` / `all_orders` fixtures from `tests/conftest.py`.

## Done criteria

- [ ] All 8 tools implemented as `BaseTool` subclasses with typed I/O.
- [ ] `executor.py` provides timeout + retry + event emission.
- [ ] 8 tool_cards markdown files written.
- [ ] All 21 tests pass under `pytest -m unit tests/test_tools.py`.
- [ ] No tool imports from `app.graph`, `app.mcp`, or `app.api` (one-way dependency only).
