# SPEC: Sub-agents

**Layer:** L7 — Sub-agents
**Owner:** `app/graph/subagents/`

The Sub-agents layer runs specialized sub-graphs whose purpose is to **protect the parent agent's context budget** by doing work the parent shouldn't see in full. The only sub-agent in scope is `fraud_check` — it consumes a 90-day refund history (potentially many rows) and returns a small `FraudCheckResult` to the parent. The parent agent never sees the raw history, only the distilled signal.

Tone subagent is explicitly out of scope — tone is style, not a context-quality problem, and is handled inside the main agent prompt.

## Contract

```python
from app.graph.subagents import run_fraud_check
```

- `async run_fraud_check(customer: Customer, order: Order, refund_history: list[RefundRecord]) -> FraudCheckResult`

A new domain model is added to `app/domain/models.py` (with its own model test):

```python
class FraudCheckResult(BaseModel):
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_factors: list[str]   # ordered, highest-weight first
    recommendation: Literal["proceed", "escalate"]
    summary: str              # LLM-narrated, ≤ 2 sentences
```

## Behaviors

- Runs as an **isolated LangGraph sub-graph** with its own `TypedDict` state — NOT the parent `AgentState`. The graph topology is small: `score_signals → narrate_summary → END`.
- The parent graph (L6) calls `run_fraud_check` and stores ONLY the `FraudCheckResult` on `AgentState.fraud_risk_score` + `AgentState.fraud_risk_evidence`. The raw `refund_history` list never enters the parent's `state.messages` or any other parent-visible field. **This is the entire point of the sub-agent.**
- **Scoring (rule-based, deterministic):**

| Signal | Source | Weight |
|---|---|---|
| `prior_refunds_last_90d > 3` | `customer.prior_refunds_last_90d` | +0.30 |
| `refund_amount > 0.5 × lifetime_value_usd` | `order.total_usd / customer.lifetime_value_usd` | +0.20 |
| `account_age_days < 30` | `customer.account_age_days` | +0.20 |
| `flagged_for_abuse == True` | `customer.flagged_for_abuse` | hard cap → score = 1.0 |
| `active_chargeback == True` | `customer.active_chargeback` | hard cap → score = 1.0 |
| `same_item_repeated_refund` | SKU appears in ≥2 `refund_history` rows | +0.30 |

- Final `risk_score = min(1.0, sum_of_weights)` for soft signals; any hard-cap signal sets `risk_score = 1.0`.
- **`recommendation = "escalate"` when `risk_score >= 0.5` OR any hard-cap signal is present.** Otherwise `"proceed"`.
- **`summary` uses Azure OpenAI** (`AzureChatOpenAI` bound to `settings.AZURE_OPENAI_DEPLOYMENT_CHAT`) — one short call, prompt loaded from `prompts/fraud_check_subagent.md` via `app.instructions.load_system_prompt(name="fraud_check_subagent")`. The summary describes WHICH factors triggered, not the underlying numbers.
- **`risk_factors` is the ordered list of triggered signal names** (e.g., `["serial_refunder_90d", "amount_vs_ltv_high"]`) — used by the parent's audit trail and the dashboard.
- The sub-graph runs as an `await`able async function, not a separate process. Same event loop as the parent.

## Events emitted

- `L7_SUBAGENTS / fraud_check_started` — payload: `{conversation_id: str, customer_id: str}`.
- `L7_SUBAGENTS / fraud_check_completed` — payload: `{conversation_id: str, risk_score: float, recommendation: str, num_factors: int}`.

## Files

```
app/graph/subagents/__init__.py             # exports run_fraud_check, FraudCheckResult re-export
app/graph/subagents/fraud_check.py          # the sub-graph: state, score node, summary node
app/graph/subagents/fraud_check_prompts.py  # loads prompts/fraud_check_subagent.md via L1
```

## Dependencies

- `app.domain.models` — `Customer`, `Order`, `RefundRecord`, `FraudCheckResult` (new), `AgentState`
- `app.instructions` — `load_system_prompt`
- `app.observability` — `get_emitter`
- `langgraph.graph.StateGraph`
- `langchain_openai.AzureChatOpenAI`

Out of scope: the tone sub-agent (collapsed into main prompt), the eligibility-check node (lives in L6 as a regular node, not a sub-agent — eligibility is small data and belongs in the parent context).

## Tests

`tests/test_subagents.py` — minimum tests:

1. `test_fraud_check_low_risk_proceeds` — clean customer (no prior refunds, > 30d account, LTV > 10× order) → `risk_score < 0.5`, `recommendation == "proceed"`.
2. `test_fraud_check_serial_refunder_escalates` — `customer.prior_refunds_last_90d = 6` → score ≥ 0.5 → escalate.
3. `test_fraud_check_flagged_abuse_hard_caps_escalate` — `flagged_for_abuse=True` → `risk_score == 1.0` regardless of other signals.
4. `test_fraud_check_active_chargeback_hard_caps_escalate` — `active_chargeback=True` → hard cap.
5. `test_fraud_check_amount_vs_ltv_triggers` — `order.total_usd = 0.8 × customer.lifetime_value_usd` → `amount_vs_ltv_high` in `risk_factors`.
6. `test_fraud_check_returns_summary_string` — stub LLM returns "Customer has 6 refunds in 90 days, recommending escalation."; result `summary` matches.
7. `test_fraud_check_emits_started_and_completed_events` — capture LayerEvents via a fake emitter; exactly one of each event type, with the matching `conversation_id`.
8. `test_fraud_check_does_not_leak_refund_history_to_parent_state` — call `run_fraud_check` from a stub parent graph; after return, assert `parent_state.messages` contains no SKU from `refund_history`, no order_id from `refund_history`, no per-row payload. ONLY the summary string and the structured `FraudCheckResult` are on the parent state.

Use deterministic-RNG fixtures; stub the LLM via an injectable `llm` parameter.

## Done criteria

- [ ] All 3 module files exist (`__init__.py`, `fraud_check.py`, `fraud_check_prompts.py`).
- [ ] `FraudCheckResult` domain model added to `app/domain/models.py` with a round-trip model test in `tests/test_domain_models.py`.
- [ ] All 8 tests pass under `pytest -m "unit or integration" tests/test_subagents.py`.
- [ ] Test 8 explicitly asserts that parent `AgentState.messages` after `run_fraud_check` returns contains zero references to any field present in the raw `refund_history` input (asserted by string search on `state.model_dump_json()`).
- [ ] `mypy --strict app/graph/subagents/` passes (best-effort).
