"""Tests for L3 Tool Interfaces + L4 Sandbox Executor.

TDD order: write tests first (RED), then implement (GREEN).

Markers:
- unit: fast, deterministic, no real I/O (SQLite in-memory ok)
- integration: touches SQLite file or broader stack

Random seed: 42 (per spec constraint)
Frozen date: 2026-06-18 (today in the scenario)
"""

from __future__ import annotations

import asyncio
import random
import sqlite3
from datetime import date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun import freeze_time

from app.domain.models import (
    Customer,
    CustomerTier,
    Order,
    PolicyClause,
    RefundDecisionKind,
)

random.seed(42)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

TODAY = date(2026, 6, 18)
TODAY_STR = "2026-06-18"


# --------------------------------------------------------------------------- #
# 1. test_lookup_customer_by_id_succeeds
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_lookup_customer_by_id_succeeds(all_customers: list[Customer]) -> None:
    from app.tools.customer_tools import LookupCustomer

    tool = LookupCustomer(customers=all_customers)
    result = await tool.run(tool.Input(customer_id="CUST-001"))

    assert result.customer is not None
    assert result.customer.name == "Marcus Chen"
    assert result.customer.customer_id == "CUST-001"


# --------------------------------------------------------------------------- #
# 2. test_lookup_customer_by_email_case_insensitive
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_lookup_customer_by_email_case_insensitive(all_customers: list[Customer]) -> None:
    from app.tools.customer_tools import LookupCustomer

    tool = LookupCustomer(customers=all_customers)
    result = await tool.run(tool.Input(email="MARCUS.CHEN@EXAMPLE.COM"))

    assert result.customer is not None
    assert result.customer.customer_id == "CUST-001"


# --------------------------------------------------------------------------- #
# 3. test_lookup_customer_returns_none_for_unknown
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_lookup_customer_returns_none_for_unknown(all_customers: list[Customer]) -> None:
    from app.tools.customer_tools import LookupCustomer

    tool = LookupCustomer(customers=all_customers)
    result = await tool.run(tool.Input(customer_id="CUST-GHOST"))

    assert result.customer is None


# --------------------------------------------------------------------------- #
# 4. test_get_order_scoped_to_customer_succeeds
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_get_order_scoped_to_customer_succeeds(all_orders: list[Order]) -> None:
    from app.tools.order_tools import GetOrder

    tool = GetOrder(orders=all_orders)
    result = await tool.run(tool.Input(order_id="ORD-1001", customer_id="CUST-001"))

    assert result.order is not None
    assert result.order.order_id == "ORD-1001"
    assert result.order.customer_id == "CUST-001"


# --------------------------------------------------------------------------- #
# 5. test_get_order_returns_none_on_customer_mismatch
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_get_order_returns_none_on_customer_mismatch(all_orders: list[Order]) -> None:
    from app.tools.order_tools import GetOrder

    tool = GetOrder(orders=all_orders)
    # ORD-1001 belongs to CUST-001, not CUST-002
    result = await tool.run(tool.Input(order_id="ORD-1001", customer_id="CUST-002"))

    assert result.order is None


# --------------------------------------------------------------------------- #
# 6. test_check_return_window_within_for_standard_14d
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_check_return_window_within_for_standard_14d(
    all_customers: list[Customer], all_orders: list[Order]
) -> None:
    from app.tools.policy_tools import CheckReturnWindow

    tool = CheckReturnWindow()
    # ORD-1003: delivered 2026-06-12, today 2026-06-18 => 6 days => within 14d
    customer = next(c for c in all_customers if c.customer_id == "CUST-002")
    order = next(o for o in all_orders if o.order_id == "ORD-1003")

    result = await tool.run(tool.Input(order=order, customer=customer))

    assert result.within_window is True
    assert result.days_since_delivery == 6


# --------------------------------------------------------------------------- #
# 7. test_check_return_window_outside_for_standard_after_14d
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_check_return_window_outside_for_standard_after_14d(
    all_customers: list[Customer], all_orders: list[Order]
) -> None:
    from app.tools.policy_tools import CheckReturnWindow

    tool = CheckReturnWindow()
    # ORD-1007: delivered 2026-04-21, today 2026-06-18 => 58 days => outside 14d for standard
    customer = next(c for c in all_customers if c.customer_id == "CUST-004")
    order = next(o for o in all_orders if o.order_id == "ORD-1007")

    result = await tool.run(tool.Input(order=order, customer=customer))

    assert result.within_window is False
    assert result.days_since_delivery > 14


# --------------------------------------------------------------------------- #
# 8. test_check_return_window_vip_60d_extension
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_check_return_window_vip_60d_extension(
    all_customers: list[Customer], all_orders: list[Order]
) -> None:
    from app.tools.policy_tools import CheckReturnWindow

    tool = CheckReturnWindow()
    # ORD-1001: delivered 2026-05-26, today 2026-06-18 => 23 days, CUST-001 is VIP (60d) => within
    customer = next(c for c in all_customers if c.customer_id == "CUST-001")
    order = next(o for o in all_orders if o.order_id == "ORD-1001")

    result = await tool.run(tool.Input(order=order, customer=customer))

    assert result.within_window is True
    assert result.days_since_delivery > 14  # would be out-of-window for standard
    assert "POLICY-002" in result.applied_clause


# --------------------------------------------------------------------------- #
# 9. test_check_return_window_honors_carrier_delay
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_check_return_window_honors_carrier_delay(
    all_customers: list[Customer], all_orders: list[Order]
) -> None:
    from app.tools.policy_tools import CheckReturnWindow

    tool = CheckReturnWindow()
    # ORD-1028: delivered 2026-04-25, carrier_delay_days=17, standard customer CUST-014
    # effective window = 14 + 17 = 31 days from delivery date 2026-04-25
    # 2026-04-25 + 31 = 2026-05-26 => today 2026-06-18 > 2026-05-26 => outside extended window
    # But the spec says "honors" the delay — meaning it DOES extend the window.
    # Let's check: days_since_delivery from 2026-04-25 = 54 days; window = 14 + 17 = 31 days
    # 54 > 31 so it's outside even extended. The key assertion is that carrier_delay is applied.
    customer = next(c for c in all_customers if c.customer_id == "CUST-014")
    order = next(o for o in all_orders if o.order_id == "ORD-1028")

    result = await tool.run(tool.Input(order=order, customer=customer))

    # The applied_clause should mention POLICY-010 (carrier delay extension)
    assert "POLICY-010" in result.applied_clause
    # window = 14 + 17 = 31 days; but 54 days have passed, so outside
    assert result.within_window is False
    assert result.days_since_delivery == 54


# --------------------------------------------------------------------------- #
# 10. test_check_item_condition_damaged_returns_full
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_check_item_condition_damaged_returns_full(all_orders: list[Order]) -> None:
    from app.tools.policy_tools import CheckItemCondition

    tool = CheckItemCondition()
    # ORD-1020: item_condition_reported = "damaged_on_arrival"
    order = next(o for o in all_orders if o.order_id == "ORD-1020")

    result = await tool.run(tool.Input(order=order))

    assert result.condition == "damaged_on_arrival"
    assert result.eligibility == "full_refund_if_within_14d"
    assert "POLICY-009" in result.applied_clause


# --------------------------------------------------------------------------- #
# 11. test_check_item_condition_used_returns_partial
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_check_item_condition_used_returns_partial(all_orders: list[Order]) -> None:
    from app.tools.policy_tools import CheckItemCondition

    tool = CheckItemCondition()
    # ORD-1006: item_condition_reported = "used"
    order = next(o for o in all_orders if o.order_id == "ORD-1006")

    result = await tool.run(tool.Input(order=order))

    assert result.condition == "used"
    assert result.eligibility == "partial_50_within_window"
    assert "POLICY-008" in result.applied_clause


# --------------------------------------------------------------------------- #
# 12. test_check_item_condition_final_sale_returns_non_refundable
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_check_item_condition_final_sale_returns_non_refundable(all_orders: list[Order]) -> None:
    from app.tools.policy_tools import CheckItemCondition

    tool = CheckItemCondition()
    # ORD-1024: category = "final_sale"
    order = next(o for o in all_orders if o.order_id == "ORD-1024")

    result = await tool.run(tool.Input(order=order))

    assert result.eligibility == "non_refundable"
    assert "POLICY-004" in result.applied_clause


# --------------------------------------------------------------------------- #
# 13. test_compute_refund_amount_full_path
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_compute_refund_amount_full_path(
    all_customers: list[Customer], all_orders: list[Order]
) -> None:
    from app.tools.policy_tools import ComputeRefundAmount

    tool = ComputeRefundAmount()
    # ORD-1003: new_unopened, within window, standard customer => full refund $145
    customer = next(c for c in all_customers if c.customer_id == "CUST-002")
    order = next(o for o in all_orders if o.order_id == "ORD-1003")

    result = await tool.run(
        tool.Input(
            order=order,
            customer=customer,
            within_window=True,
            item_condition="new_unopened",
            eligibility="full_refund",
        )
    )

    assert result.kind == RefundDecisionKind.APPROVE_FULL
    assert result.amount_usd == pytest.approx(145.0)
    assert "POLICY-006" in result.cited_clauses


# --------------------------------------------------------------------------- #
# 14. test_compute_refund_amount_partial_50
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_compute_refund_amount_partial_50(
    all_customers: list[Customer], all_orders: list[Order]
) -> None:
    from app.tools.policy_tools import ComputeRefundAmount

    tool = ComputeRefundAmount()
    # ORD-1006: used item, within window => 50% partial refund
    customer = next(c for c in all_customers if c.customer_id == "CUST-004")
    order = next(o for o in all_orders if o.order_id == "ORD-1006")

    result = await tool.run(
        tool.Input(
            order=order,
            customer=customer,
            within_window=True,
            item_condition="used",
            eligibility="partial_50_within_window",
        )
    )

    assert result.kind == RefundDecisionKind.APPROVE_PARTIAL
    assert result.amount_usd == pytest.approx(39.0)  # 78 * 0.5
    assert "POLICY-008" in result.cited_clauses


# --------------------------------------------------------------------------- #
# 15. test_compute_refund_amount_partial_75_vip
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_compute_refund_amount_partial_75_vip(
    all_customers: list[Customer], all_orders: list[Order]
) -> None:
    from app.tools.policy_tools import ComputeRefundAmount

    tool = ComputeRefundAmount()
    # ORD-1027: opened_unused, VIP customer (CUST-013), within 60d window but >14d => 75%
    customer = next(c for c in all_customers if c.customer_id == "CUST-013")
    order = next(o for o in all_orders if o.order_id == "ORD-1027")

    result = await tool.run(
        tool.Input(
            order=order,
            customer=customer,
            within_window=True,
            item_condition="opened_unused",
            eligibility="partial_75_vip_beyond_14d",
        )
    )

    assert result.kind == RefundDecisionKind.APPROVE_PARTIAL
    assert result.amount_usd == pytest.approx(1199.0 * 0.75)
    assert "POLICY-007" in result.cited_clauses


# --------------------------------------------------------------------------- #
# 16. test_issue_refund_writes_to_sqlite_and_returns_id
# --------------------------------------------------------------------------- #


@pytest.mark.integration
@freeze_time(TODAY_STR)
async def test_issue_refund_writes_to_sqlite_and_returns_id(
    all_orders: list[Order], tmp_path
) -> None:
    from app.tools.refund_tools import IssueRefund

    db_path = str(tmp_path / "test.db")
    tool = IssueRefund(db_path=db_path)
    order = next(o for o in all_orders if o.order_id == "ORD-1003")

    result = await tool.run(
        tool.Input(
            conversation_id="CONV-TEST-001",
            order_id=order.order_id,
            amount_usd=145.0,
            kind=RefundDecisionKind.APPROVE_FULL,
        )
    )

    assert result.refund_id.startswith("REF-CONV-TEST-001-")
    assert result.status == "issued"
    assert result.amount_usd == pytest.approx(145.0)

    # Verify it's in the DB
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT refund_id FROM refunds WHERE order_id=?", ("ORD-1003",)).fetchall()
    conn.close()
    assert len(rows) == 1


# --------------------------------------------------------------------------- #
# 17. test_issue_refund_idempotent_on_retry
# --------------------------------------------------------------------------- #


@pytest.mark.integration
@freeze_time(TODAY_STR)
async def test_issue_refund_idempotent_on_retry(
    all_orders: list[Order], tmp_path
) -> None:
    from app.tools.refund_tools import IssueRefund

    db_path = str(tmp_path / "test.db")
    tool = IssueRefund(db_path=db_path)
    order = next(o for o in all_orders if o.order_id == "ORD-1003")

    inp = tool.Input(
        conversation_id="CONV-IDEMPOTENT-001",
        order_id=order.order_id,
        amount_usd=145.0,
        kind=RefundDecisionKind.APPROVE_FULL,
    )

    result1 = await tool.run(inp)
    result2 = await tool.run(inp)

    # Same refund_id on both calls
    assert result1.refund_id == result2.refund_id

    # Only one row in DB
    conn = sqlite3.connect(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM refunds WHERE conversation_id=? AND order_id=?",
        ("CONV-IDEMPOTENT-001", "ORD-1003"),
    ).fetchone()[0]
    conn.close()
    assert count == 1


# --------------------------------------------------------------------------- #
# 18. test_escalate_to_human_writes_approval_row
# --------------------------------------------------------------------------- #


@pytest.mark.integration
@freeze_time(TODAY_STR)
async def test_escalate_to_human_writes_approval_row(tmp_path) -> None:
    from app.tools.refund_tools import EscalateToHuman

    db_path = str(tmp_path / "test.db")
    tool = EscalateToHuman(db_path=db_path)

    result = await tool.run(
        tool.Input(
            conversation_id="CONV-ESC-001",
            order_id="ORD-1019",
            reason_code="ACTIVE_CHARGEBACK",
            notes="Customer has open chargeback CB-2026-0419",
        )
    )

    assert result.escalation_id.startswith("ESC-")
    assert result.reason_code == "ACTIVE_CHARGEBACK"

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT reason_code FROM human_approvals WHERE conversation_id=?",
        ("CONV-ESC-001",),
    ).fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][0] == "ACTIVE_CHARGEBACK"


# --------------------------------------------------------------------------- #
# 19. test_search_policy_returns_relevant_clauses
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@freeze_time(TODAY_STR)
async def test_search_policy_returns_relevant_clauses(policy_doc_text: str) -> None:
    from app.tools.policy_tools import SearchPolicy

    tool = SearchPolicy(policy_text=policy_doc_text)
    result = await tool.run(tool.Input(query="30 day return", top_k=3))

    clause_ids = [c.clause_id for c in result.clauses]
    # POLICY-001 is about 14-day return; POLICY-002 is 60-day VIP; the query "30 day return"
    # should surface at least one of the return-window policies
    assert any("POLICY-00" in cid for cid in clause_ids), f"No policy clause found in: {clause_ids}"
    assert len(result.clauses) <= 3
    assert all(isinstance(c, PolicyClause) for c in result.clauses)


# --------------------------------------------------------------------------- #
# 20. test_executor_retries_on_transient_error_then_succeeds
# --------------------------------------------------------------------------- #
# NOTE: freeze_time is intentionally NOT used on executor tests — freezegun
# patches time.time but does not cooperate with asyncio.sleep's event loop
# clock, causing the test to hang. The executor tests use a zero-backoff
# override instead to keep runtime fast.


@pytest.mark.unit
async def test_executor_retries_on_transient_error_then_succeeds() -> None:
    from app.tools.base import BaseTool
    from app.tools.executor import run_tool

    call_count = 0

    class FlakyTool(BaseTool):
        name = "flaky_test_tool"
        description = "Fails once then succeeds."

        class Input(BaseTool.Input):
            value: str = "test"

        class Output(BaseTool.Output):
            echo: str = ""

        async def run(self, input: "FlakyTool.Input") -> "FlakyTool.Output":
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("transient failure")
            return FlakyTool.Output(echo=input.value)

    tool = FlakyTool()
    # Pass timeout_seconds=5 and max_retries=2; backoff is negligible for fast raises
    envelope = await run_tool(
        tool, {"value": "hello"}, conversation_id="CONV-RETRY-001",
        timeout_seconds=5.0, max_retries=2
    )

    assert envelope["ok"] is True
    assert envelope["retries"] == 1
    assert envelope["output"]["echo"] == "hello"
    assert call_count == 2


# --------------------------------------------------------------------------- #
# 21. test_executor_fails_after_max_retries
# --------------------------------------------------------------------------- #


@pytest.mark.unit
async def test_executor_fails_after_max_retries() -> None:
    from app.tools.base import BaseTool
    from app.tools.executor import run_tool

    call_count = 0

    class AlwaysFailsTool(BaseTool):
        name = "always_fails_tool"
        description = "Always fails."

        class Input(BaseTool.Input):
            pass

        class Output(BaseTool.Output):
            pass

        async def run(self, input: "AlwaysFailsTool.Input") -> "AlwaysFailsTool.Output":
            nonlocal call_count
            call_count += 1
            raise RuntimeError("permanent failure")

    tool = AlwaysFailsTool()
    envelope = await run_tool(
        tool, {}, conversation_id="CONV-FAIL-001",
        timeout_seconds=5.0, max_retries=2
    )

    assert envelope["ok"] is False
    assert envelope["error_code"] is not None
    assert "permanent failure" in envelope["error_code"]
    # called 1 initial + 2 retries = 3 total
    assert call_count == 3
    assert envelope["retries"] == 2
