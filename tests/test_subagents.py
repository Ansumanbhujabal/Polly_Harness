"""Tests for L7 fraud-check sub-agent.

Tests 1-8 per SPEC_SUBAGENTS.md.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models import (
    AgentState,
    Customer,
    FraudCheckResult,
    Item,
    LayerEvent,
    LayerName,
    Order,
    RefundDecisionKind,
    RefundRecord,
)
from app.graph.subagents import run_fraud_check
from app.observability import get_emitter


# --------------------------------------------------------------------------- #
# Helpers / shared fixtures
# --------------------------------------------------------------------------- #


def _make_customer(**kwargs: Any) -> Customer:
    defaults: dict[str, Any] = {
        "customer_id": "CUST-TEST",
        "name": "Test User",
        "email": "test@example.com",
        "account_age_days": 365,
        "lifetime_value_usd": 1000.0,
        "prior_refunds_last_90d": 0,
        "flagged_for_abuse": False,
        "active_chargeback": False,
    }
    defaults.update(kwargs)
    return Customer(**defaults)


def _make_order(**kwargs: Any) -> Order:
    defaults: dict[str, Any] = {
        "order_id": "ORD-TEST-001",
        "customer_id": "CUST-TEST",
        "items": [Item(sku="SKU-AAA", name="Widget", category="electronics", unit_price_usd=50.0)],
        "total_usd": 50.0,
        "purchase_date": "2026-05-01",
    }
    defaults.update(kwargs)
    return Order(**defaults)


def _make_refund_record(order_id: str = "ORD-HIST-001", **kwargs: Any) -> RefundRecord:
    defaults: dict[str, Any] = {
        "refund_id": f"RFD-{order_id}",
        "conversation_id": "CONV-HIST",
        "order_id": order_id,
        "customer_id": "CUST-TEST",
        "amount_usd": 30.0,
        "kind": RefundDecisionKind.APPROVE_PARTIAL,
        "reasoning": "standard return",
    }
    defaults.update(kwargs)
    return RefundRecord(**defaults)


def _stub_llm(response_text: str) -> MagicMock:
    """Return a fake LLM whose ainvoke returns a message with response_text."""
    llm = MagicMock()
    msg = MagicMock()
    msg.content = response_text
    llm.ainvoke = AsyncMock(return_value=msg)
    return llm


# --------------------------------------------------------------------------- #
# Test 1: low-risk customer proceeds
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fraud_check_low_risk_proceeds():
    """Clean customer (no prior refunds, > 30d account, LTV > 10× order) → proceed."""
    customer = _make_customer(
        account_age_days=365,
        lifetime_value_usd=1000.0,
        prior_refunds_last_90d=0,
        flagged_for_abuse=False,
        active_chargeback=False,
    )
    order = _make_order(total_usd=50.0)
    refund_history: list[RefundRecord] = []

    result = await run_fraud_check(
        customer,
        order,
        refund_history,
        conversation_id="conv-001",
        llm=_stub_llm("No fraud signals detected."),
    )

    assert isinstance(result, FraudCheckResult)
    assert result.risk_score < 0.5
    assert result.recommendation == "proceed"


# --------------------------------------------------------------------------- #
# Test 2: serial refunder escalates
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fraud_check_serial_refunder_escalates():
    """customer.prior_refunds_last_90d = 6 → score ≥ 0.5 → escalate."""
    customer = _make_customer(
        prior_refunds_last_90d=6,
        lifetime_value_usd=1000.0,
        account_age_days=180,
        flagged_for_abuse=False,
        active_chargeback=False,
    )
    order = _make_order(total_usd=50.0)

    result = await run_fraud_check(
        customer,
        order,
        [],
        conversation_id="conv-002",
        llm=_stub_llm("Customer has 6 refunds in 90 days, recommending escalation."),
    )

    assert result.risk_score >= 0.5
    assert result.recommendation == "escalate"
    assert "serial_refunder_90d" in result.risk_factors


# --------------------------------------------------------------------------- #
# Test 3: flagged_for_abuse hard cap → score = 1.0
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fraud_check_flagged_abuse_hard_caps_escalate():
    """flagged_for_abuse=True → risk_score == 1.0 regardless of other signals."""
    customer = _make_customer(
        flagged_for_abuse=True,
        prior_refunds_last_90d=0,
        account_age_days=500,
        lifetime_value_usd=10000.0,
        active_chargeback=False,
    )
    order = _make_order(total_usd=10.0)

    result = await run_fraud_check(
        customer,
        order,
        [],
        conversation_id="conv-003",
        llm=_stub_llm("Customer is flagged for abuse."),
    )

    assert result.risk_score == 1.0
    assert result.recommendation == "escalate"
    assert "flagged_for_abuse" in result.risk_factors


# --------------------------------------------------------------------------- #
# Test 4: active_chargeback hard cap
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fraud_check_active_chargeback_hard_caps_escalate():
    """active_chargeback=True → hard cap → score = 1.0, escalate."""
    customer = _make_customer(
        active_chargeback=True,
        flagged_for_abuse=False,
        prior_refunds_last_90d=0,
        account_age_days=500,
        lifetime_value_usd=10000.0,
    )
    order = _make_order(total_usd=10.0)

    result = await run_fraud_check(
        customer,
        order,
        [],
        conversation_id="conv-004",
        llm=_stub_llm("Active chargeback detected."),
    )

    assert result.risk_score == 1.0
    assert result.recommendation == "escalate"
    assert "active_chargeback" in result.risk_factors


# --------------------------------------------------------------------------- #
# Test 5: amount vs LTV triggers the signal
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fraud_check_amount_vs_ltv_triggers():
    """order.total_usd = 0.8 × customer.lifetime_value_usd → amount_vs_ltv_high triggered."""
    customer = _make_customer(
        lifetime_value_usd=100.0,
        prior_refunds_last_90d=0,
        account_age_days=120,
        flagged_for_abuse=False,
        active_chargeback=False,
    )
    order = _make_order(total_usd=80.0)  # 80% of LTV

    result = await run_fraud_check(
        customer,
        order,
        [],
        conversation_id="conv-005",
        llm=_stub_llm("High refund amount relative to lifetime value."),
    )

    assert "amount_vs_ltv_high" in result.risk_factors


# --------------------------------------------------------------------------- #
# Test 6: summary string from stub LLM is preserved
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fraud_check_returns_summary_string():
    """stub LLM returns fixed text; result.summary must match that text."""
    expected_summary = "Customer has 6 refunds in 90 days, recommending escalation."
    customer = _make_customer(prior_refunds_last_90d=6)
    order = _make_order()

    result = await run_fraud_check(
        customer,
        order,
        [],
        conversation_id="conv-006",
        llm=_stub_llm(expected_summary),
    )

    assert result.summary == expected_summary


# --------------------------------------------------------------------------- #
# Test 7: emits fraud_check_started and fraud_check_completed events
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fraud_check_emits_started_and_completed_events():
    """Capture LayerEvents via a fake sink; assert exactly 1 of each type."""
    emitter = get_emitter()
    captured_events: list[LayerEvent] = []

    def fake_sink(event: LayerEvent) -> None:
        if event.layer == LayerName.SUBAGENTS:
            captured_events.append(event)

    emitter.subscribe(fake_sink)
    try:
        customer = _make_customer()
        order = _make_order()
        cid = "conv-007-events"

        await run_fraud_check(
            customer,
            order,
            [],
            conversation_id=cid,
            llm=_stub_llm("No fraud signals detected."),
        )

        started = [e for e in captured_events if e.event_type == "fraud_check_started"]
        completed = [e for e in captured_events if e.event_type == "fraud_check_completed"]

        assert len(started) == 1, f"Expected 1 started event, got {len(started)}"
        assert len(completed) == 1, f"Expected 1 completed event, got {len(completed)}"
        assert started[0].payload["conversation_id"] == cid
        assert completed[0].payload["conversation_id"] == cid
        assert "risk_score" in completed[0].payload
        assert "recommendation" in completed[0].payload
        assert "num_factors" in completed[0].payload
    finally:
        emitter.unsubscribe(fake_sink)


# --------------------------------------------------------------------------- #
# Test 8: parent state receives NO raw refund_history data
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fraud_check_does_not_leak_refund_history_to_parent_state():
    """After run_fraud_check, parent AgentState.messages must contain NO fields from raw refund_history.

    Specifically: no SKU, no order_id from refund_history, no per-row payload.
    ONLY the summary string and structured FraudCheckResult are on the parent state.
    """
    # Build a refund_history with identifiable sentinel values
    sentinel_order_id = "ORD-SENTINEL-LEAK-TEST-XYZ"
    sentinel_reasoning = "sentinel-reasoning-text-99999"

    history = [
        _make_refund_record(order_id=sentinel_order_id, reasoning=sentinel_reasoning),
        _make_refund_record(order_id=sentinel_order_id, reasoning=sentinel_reasoning),
    ]

    customer = _make_customer(prior_refunds_last_90d=0)
    order = _make_order()

    result = await run_fraud_check(
        customer,
        order,
        history,
        conversation_id="conv-008",
        llm=_stub_llm("Duplicate refunds detected for same order."),
    )

    # Simulate what the parent graph would do: store ONLY the FraudCheckResult
    parent_state = AgentState(
        conversation_id="conv-008",
        fraud_risk_score=result.risk_score,
        fraud_risk_evidence=result.risk_factors,
        messages=[
            # Parent agent might add the summary as a message (the ONLY acceptable content)
            {"role": "system", "content": result.summary},
        ],
    )

    # Serialize parent state to JSON to inspect all fields
    serialized = parent_state.model_dump_json()

    # The sentinel values from raw refund_history must NOT appear anywhere in parent state
    assert sentinel_order_id not in serialized, (
        f"Raw refund history order_id leaked into parent state: {sentinel_order_id}"
    )
    assert sentinel_reasoning not in serialized, (
        f"Raw refund history reasoning leaked into parent state: {sentinel_reasoning}"
    )

    # The FraudCheckResult IS present (via fraud_risk_score and fraud_risk_evidence)
    state_dict = json.loads(serialized)
    assert state_dict["fraud_risk_score"] == pytest.approx(result.risk_score)
    assert state_dict["fraud_risk_evidence"] == result.risk_factors

    # The summary string IS present (it's the one piece of LLM narration the parent gets)
    assert result.summary in serialized
