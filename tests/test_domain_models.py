"""Unit tests for the shared domain models.

These tests pin down the contracts every component agent depends on. If a model
changes shape, these break first, so the army's downstream tests fail loudly
instead of producing silently wrong refunds.
"""

import pytest

from app.domain.models import (
    AgentState,
    Customer,
    CustomerTier,
    EscalationRecord,
    IncidentRecord,
    LayerEvent,
    LayerName,
    Order,
    OrderStatus,
    PendingApproval,
    PolicyClause,
    RefundDecision,
    RefundDecisionKind,
    RefundRecord,
    VerificationCheck,
    VerificationResult,
)


# --------------------------------------------------------------------------- #
# Customer
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_all_15_customers_parse(all_customers):
    assert len(all_customers) == 15
    assert all(isinstance(c, Customer) for c in all_customers)
    assert {c.customer_id for c in all_customers} == {f"CUST-{i:03d}" for i in range(1, 16)}


@pytest.mark.unit
def test_vip_customer_has_500_cap_and_60_day_window(vip_customer):
    assert vip_customer.auto_approval_cap_usd == 500.0
    assert vip_customer.return_window_days == 60


@pytest.mark.unit
def test_standard_customer_has_200_cap_and_14_day_window(all_customers):
    standard = next(c for c in all_customers if c.tier == CustomerTier.STANDARD.value)
    assert standard.auto_approval_cap_usd == 200.0
    assert standard.return_window_days == 14


@pytest.mark.unit
def test_serial_refunder_is_flagged(serial_refunder):
    assert serial_refunder.flagged_for_abuse is True
    assert serial_refunder.prior_refunds_last_90d >= 4


@pytest.mark.unit
def test_chargeback_customer_has_active_chargeback(chargeback_customer):
    assert chargeback_customer.active_chargeback is True


# --------------------------------------------------------------------------- #
# Order
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_all_orders_parse(all_orders):
    assert len(all_orders) >= 20  # we seeded 25
    assert all(isinstance(o, Order) for o in all_orders)


@pytest.mark.unit
def test_carrier_delay_order_present(all_orders):
    delayed = next(o for o in all_orders if o.order_id == "ORD-1028")
    assert delayed.carrier_delay_days > 5
    assert delayed.status == OrderStatus.DELIVERED_LATE.value


@pytest.mark.unit
def test_final_sale_order_present(all_orders):
    fs = next(o for o in all_orders if o.order_id == "ORD-1024")
    assert fs.items[0].category == "final_sale"


@pytest.mark.unit
def test_damaged_order_present(all_orders):
    dmg = next(o for o in all_orders if o.order_id == "ORD-1025")
    assert dmg.item_condition_reported == "damaged_on_arrival"


@pytest.mark.unit
def test_chargeback_order_has_ref(all_orders):
    cb = next(o for o in all_orders if o.order_id == "ORD-1019")
    assert cb.chargeback_ref is not None


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_verification_blocked_when_any_block_check_fails():
    result = VerificationResult(
        checks=[
            VerificationCheck(check_name="ok", passed=True, severity="block"),
            VerificationCheck(check_name="bad", passed=False, severity="block"),
        ]
    )
    assert result.blocked is True
    assert len(result.failures) == 1


@pytest.mark.unit
def test_verification_not_blocked_when_only_warns_fail():
    result = VerificationResult(
        checks=[
            VerificationCheck(check_name="warn-only", passed=False, severity="warn"),
        ]
    )
    assert result.blocked is False


# --------------------------------------------------------------------------- #
# RefundDecision
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_refund_decision_kinds_cover_all_paths():
    kinds = {k.value for k in RefundDecisionKind}
    assert {"approve_full", "approve_partial", "approve_store_credit", "deny", "escalate"} <= kinds


@pytest.mark.unit
def test_decision_round_trip():
    d = RefundDecision(
        kind=RefundDecisionKind.APPROVE_PARTIAL,
        amount_usd=39.00,
        reason_summary="Used condition within window: 50% partial.",
        cited_clause_ids=["POLICY-008"],
    )
    assert d.amount_usd == 39.00
    assert "POLICY-008" in d.cited_clause_ids


# --------------------------------------------------------------------------- #
# AgentState
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_agent_state_minimal_construct():
    s = AgentState(conversation_id="conv-1")
    assert s.conversation_id == "conv-1"
    assert s.messages == []
    assert s.customer is None
    assert s.verification.blocked is False


@pytest.mark.unit
def test_agent_state_carries_policy_clauses():
    s = AgentState(
        conversation_id="conv-2",
        relevant_clauses=[
            PolicyClause(clause_id="POLICY-001", text="...", relevance_score=0.91),
        ],
    )
    assert s.relevant_clauses[0].clause_id == "POLICY-001"


# --------------------------------------------------------------------------- #
# LayerEvent + IncidentRecord
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_layer_event_constructable_for_every_layer():
    for layer in LayerName:
        ev = LayerEvent(conversation_id="c1", layer=layer, event_type="ping")
        assert ev.layer == layer


@pytest.mark.unit
def test_incident_record_minimal():
    inc = IncidentRecord(
        incident_id="INC-1",
        conversation_id="c1",
        triggered_by="verification_failure",
        layer=LayerName.VERIFICATION,
        summary="Injection detected on customer message",
    )
    assert inc.layer == LayerName.VERIFICATION


# --------------------------------------------------------------------------- #
# L5 domain models: RefundRecord, EscalationRecord, PendingApproval
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_refund_record_round_trip_json():
    record = RefundRecord(
        refund_id="RFD-001",
        conversation_id="CONV-A",
        order_id="ORD-1001",
        customer_id="CUST-007",
        amount_usd=89.50,
        kind=RefundDecisionKind.APPROVE_PARTIAL,
        cited_clauses=["POLICY-001", "POLICY-008"],
        reasoning="Item returned within 10-day window; partial for used condition.",
    )
    data = record.model_dump_json()
    restored = RefundRecord.model_validate_json(data)
    assert restored.refund_id == "RFD-001"
    assert restored.amount_usd == pytest.approx(89.50)
    assert restored.kind == RefundDecisionKind.APPROVE_PARTIAL.value
    assert "POLICY-008" in restored.cited_clauses
    assert isinstance(restored.created_at, type(record.created_at))


@pytest.mark.unit
def test_escalation_record_defaults_and_round_trip():
    esc = EscalationRecord(
        escalation_id="ESC-001",
        conversation_id="CONV-B",
        reason_code="CHARGEBACK_ACTIVE",
    )
    assert esc.severity == "medium"  # default

    data = esc.model_dump_json()
    restored = EscalationRecord.model_validate_json(data)
    assert restored.escalation_id == "ESC-001"
    assert restored.reason_code == "CHARGEBACK_ACTIVE"
    assert restored.severity == "medium"


@pytest.mark.unit
def test_pending_approval_defaults_and_round_trip():
    decision = RefundDecision(
        kind=RefundDecisionKind.APPROVE_FULL,
        amount_usd=350.0,
        reason_summary="Full refund within VIP window",
        cited_clause_ids=["POLICY-002"],
        requires_human_approval=True,
    )
    approval = PendingApproval(
        approval_id="APR-001",
        conversation_id="CONV-C",
        candidate_decision=decision,
        required_approver_role="senior_agent",
    )
    assert approval.resolution is None
    assert approval.approver is None
    assert approval.resolved_at is None

    data = approval.model_dump_json()
    restored = PendingApproval.model_validate_json(data)
    assert restored.approval_id == "APR-001"
    assert restored.candidate_decision.amount_usd == pytest.approx(350.0)
    assert restored.resolution is None
