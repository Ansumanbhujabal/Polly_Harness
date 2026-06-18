"""L3 Tools: check_return_window, check_item_condition, compute_refund_amount, search_policy.

Policy logic is a pure function over already-fetched data. No tool here calls another tool.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

from pydantic import Field

from app.domain.models import (
    Customer,
    CustomerTier,
    LayerName,
    Order,
    PolicyClause,
    RefundDecisionKind,
)
from app.observability.layer_event_emitter import get_emitter
from app.tools.base import BaseTool

# --------------------------------------------------------------------------- #
# Non-refundable item categories / conditions (POLICY-004)
# --------------------------------------------------------------------------- #
NON_REFUNDABLE_CATEGORIES = {"final_sale", "digital_download", "personal_care_opened", "custom_made", "perishable"}
NON_REFUNDABLE_CONDITIONS = {"delivered_digital"}


# --------------------------------------------------------------------------- #
# CheckReturnWindow
# --------------------------------------------------------------------------- #


class CheckReturnWindow(BaseTool):
    """Compute days since delivery and determine if the order is within the return window.

    Applies:
    - POLICY-001 (standard: 14 days)
    - POLICY-002 (VIP: 60 days)
    - POLICY-010 (carrier delay extension)

    Returns within_window, days_since_delivery, and the applied_clause string.
    """

    name = "check_return_window"
    description = (
        "Calculate how many days have elapsed since delivery and determine whether the order "
        "is still within the applicable return window. Applies POLICY-001 (14-day standard), "
        "POLICY-002 (60-day VIP), and POLICY-010 (carrier-delay extension). "
        "Returns {within_window, days_since_delivery, applied_clause}."
    )

    class Input(BaseTool.Input):
        order: Order
        customer: Customer

    class Output(BaseTool.Output):
        within_window: bool
        days_since_delivery: int
        applied_clause: str

    async def run(self, input: "CheckReturnWindow.Input") -> "CheckReturnWindow.Output":  # noqa: A002
        emitter = get_emitter()
        order = input.order
        customer = input.customer

        if order.delivery_date is None:
            # Not yet delivered
            emitter.emit(
                conversation_id="unknown",
                layer=LayerName.TOOLS,
                event_type="tool_invoked",
                payload={"tool": self.name, "not_delivered": True},
            )
            return self.Output(
                within_window=False,
                days_since_delivery=-1,
                applied_clause="NOT_DELIVERED",
            )

        delivery = date.fromisoformat(order.delivery_date)
        today = date.today()
        days_since = (today - delivery).days

        # Base window per tier
        is_vip = customer.tier in (CustomerTier.VIP, CustomerTier.VIP.value)
        base_window = 60 if is_vip else 14
        clause = "POLICY-002" if is_vip else "POLICY-001"

        # POLICY-010: carrier delay extension
        carrier_delay = order.carrier_delay_days or 0
        effective_window = base_window
        if carrier_delay > 5:
            effective_window = base_window + carrier_delay
            clause = f"{clause} + POLICY-010"

        within = days_since <= effective_window

        emitter.emit(
            conversation_id="unknown",
            layer=LayerName.TOOLS,
            event_type="tool_invoked",
            payload={
                "tool": self.name,
                "days_since_delivery": days_since,
                "effective_window": effective_window,
                "within_window": within,
                "applied_clause": clause,
            },
        )

        return self.Output(
            within_window=within,
            days_since_delivery=days_since,
            applied_clause=clause,
        )


# --------------------------------------------------------------------------- #
# CheckItemCondition
# --------------------------------------------------------------------------- #


class CheckItemCondition(BaseTool):
    """Map the warehouse-attested item condition to a policy verdict.

    Applies POLICY-004..009. The item_condition_reported from the order is the
    authoritative source — customer attestation alone does not override it.
    """

    name = "check_item_condition"
    description = (
        "Read the warehouse-attested item condition from the order and map it to a refund "
        "eligibility verdict per policy (POLICY-004 through POLICY-009). "
        "Returns {condition, eligibility, applied_clause}. "
        "Non-refundable categories (final_sale, digital_download, personal_care_opened, etc.) "
        "always return eligibility='non_refundable'."
    )

    class Input(BaseTool.Input):
        order: Order

    class Output(BaseTool.Output):
        condition: str
        eligibility: str
        applied_clause: str

    # Item condition → (eligibility, clause)
    _CONDITION_MAP: dict[str, tuple[str, str]] = {
        "new_unopened": ("full_refund", "POLICY-006"),
        "opened_unused": ("full_refund_if_within_14d_or_75pct_vip", "POLICY-007"),
        "used": ("partial_50_within_window", "POLICY-008"),
        "damaged_on_arrival": ("full_refund_if_within_14d", "POLICY-009"),
        "defective": ("full_refund_if_within_14d", "POLICY-009"),
        "defect_discovered_post_use": ("store_credit_escalate", "POLICY-011"),
        "delivered_digital": ("non_refundable", "POLICY-004"),
        "personal_care_sealed": ("full_refund", "POLICY-005"),
    }

    async def run(self, input: "CheckItemCondition.Input") -> "CheckItemCondition.Output":  # noqa: A002
        emitter = get_emitter()
        order = input.order
        condition = order.item_condition_reported

        # Check non-refundable category first (POLICY-004)
        # Category field is on the first item
        category = order.items[0].category if order.items else ""
        if category in NON_REFUNDABLE_CATEGORIES or condition in NON_REFUNDABLE_CONDITIONS:
            eligibility = "non_refundable"
            applied_clause = "POLICY-004"
        else:
            eligibility, applied_clause = self._CONDITION_MAP.get(
                condition, ("unknown_condition", "POLICY-006")
            )

        emitter.emit(
            conversation_id="unknown",
            layer=LayerName.TOOLS,
            event_type="tool_invoked",
            payload={
                "tool": self.name,
                "condition": condition,
                "eligibility": eligibility,
                "applied_clause": applied_clause,
            },
        )

        return self.Output(
            condition=condition,
            eligibility=eligibility,
            applied_clause=applied_clause,
        )


# --------------------------------------------------------------------------- #
# ComputeRefundAmount
# --------------------------------------------------------------------------- #


class ComputeRefundAmount(BaseTool):
    """Pure function: compute the refund amount and decision kind from pre-fetched data.

    Does NOT call other tools. The caller must have already determined:
    - whether the order is within the return window
    - the item condition / eligibility string

    Applies:
    - POLICY-006: new_unopened → full refund
    - POLICY-007: opened_unused → full if ≤14d, 75% if VIP >14d
    - POLICY-008: used → 50% if within window
    - POLICY-009: damaged_on_arrival → full
    - POLICY-012: escalate if amount > cap
    """

    name = "compute_refund_amount"
    description = (
        "Apply policy math to compute the refund amount and decision kind. "
        "Pure function over already-fetched data — does NOT call other tools. "
        "Requires: order, customer, within_window flag, item_condition string, eligibility string. "
        "Returns {kind: RefundDecisionKind, amount_usd: float, cited_clauses: list[str]}."
    )

    class Input(BaseTool.Input):
        order: Order
        customer: Customer
        within_window: bool
        item_condition: str
        eligibility: str

    class Output(BaseTool.Output):
        kind: RefundDecisionKind
        amount_usd: float
        cited_clauses: list[str]

    async def run(self, input: "ComputeRefundAmount.Input") -> "ComputeRefundAmount.Output":  # noqa: A002
        emitter = get_emitter()
        order = input.order
        customer = input.customer
        total = order.total_usd
        eligibility = input.eligibility
        within_window = input.within_window
        is_vip = customer.tier in (CustomerTier.VIP, CustomerTier.VIP.value)

        # Non-refundable
        if eligibility == "non_refundable":
            kind = RefundDecisionKind.DENY
            amount = 0.0
            clauses = ["POLICY-004"]

        # Outside window (and not a special eligibility)
        elif not within_window and eligibility not in (
            "full_refund_if_within_14d",
            "partial_50_within_window",
            "store_credit_escalate",
        ):
            kind = RefundDecisionKind.DENY
            amount = 0.0
            clauses = ["POLICY-003"]

        # Used item
        elif eligibility == "partial_50_within_window":
            if within_window:
                kind = RefundDecisionKind.APPROVE_PARTIAL
                amount = round(total * 0.50, 2)
                clauses = ["POLICY-008"]
            else:
                kind = RefundDecisionKind.DENY
                amount = 0.0
                clauses = ["POLICY-008", "POLICY-003"]

        # opened_unused beyond 14 days for VIP
        elif eligibility == "partial_75_vip_beyond_14d":
            if is_vip and within_window:
                kind = RefundDecisionKind.APPROVE_PARTIAL
                amount = round(total * 0.75, 2)
                clauses = ["POLICY-007", "POLICY-002"]
            elif within_window:
                kind = RefundDecisionKind.APPROVE_FULL
                amount = total
                clauses = ["POLICY-007"]
            else:
                kind = RefundDecisionKind.DENY
                amount = 0.0
                clauses = ["POLICY-007", "POLICY-003"]

        # damaged / defective — full if within 14 days
        elif eligibility == "full_refund_if_within_14d":
            if within_window:
                kind = RefundDecisionKind.APPROVE_FULL
                amount = total
                clauses = ["POLICY-009"]
            else:
                kind = RefundDecisionKind.DENY
                amount = 0.0
                clauses = ["POLICY-009", "POLICY-003"]

        # opened_unused general path
        elif eligibility == "full_refund_if_within_14d_or_75pct_vip":
            if within_window:
                kind = RefundDecisionKind.APPROVE_FULL
                amount = total
                clauses = ["POLICY-007"]
            else:
                kind = RefundDecisionKind.DENY
                amount = 0.0
                clauses = ["POLICY-007", "POLICY-003"]

        # store credit escalation (late defect)
        elif eligibility == "store_credit_escalate":
            kind = RefundDecisionKind.APPROVE_STORE_CREDIT
            amount = total
            clauses = ["POLICY-011"]

        # Full refund (new_unopened)
        elif eligibility == "full_refund":
            if within_window:
                kind = RefundDecisionKind.APPROVE_FULL
                amount = total
                clauses = ["POLICY-006"]
            else:
                kind = RefundDecisionKind.DENY
                amount = 0.0
                clauses = ["POLICY-003"]

        else:
            # Fallback — unknown eligibility
            kind = RefundDecisionKind.ESCALATE
            amount = 0.0
            clauses = []

        emitter.emit(
            conversation_id="unknown",
            layer=LayerName.TOOLS,
            event_type="tool_invoked",
            payload={
                "tool": self.name,
                "kind": kind.value if hasattr(kind, "value") else kind,
                "amount_usd": amount,
                "cited_clauses": clauses,
            },
        )

        return self.Output(kind=kind, amount_usd=amount, cited_clauses=clauses)


# --------------------------------------------------------------------------- #
# SearchPolicy
# --------------------------------------------------------------------------- #


class SearchPolicy(BaseTool):
    """Free-text search of the refund policy document.

    TODO: replace with Qdrant vector search when SPEC_CONTEXT lands (Wave 2).
    For now, uses a simple in-memory keyword-overlap scoring against paragraph
    chunks parsed from the policy markdown.
    """

    name = "search_policy"
    description = (
        "Search the refund policy document for clauses relevant to a free-text query. "
        "Returns up to top_k PolicyClause objects with clause_id, text, and relevance_score. "
        "Currently uses in-memory keyword matching; will be replaced with Qdrant vector "
        "search when the Context layer (SPEC_CONTEXT) is implemented in Wave 2."
    )

    def __init__(self, policy_text: Optional[str] = None) -> None:
        if policy_text is None:
            from app.config import settings

            policy_text = settings.POLICY_DOC_PATH.read_text()
        self._chunks = self._parse_chunks(policy_text)

    @staticmethod
    def _parse_chunks(text: str) -> list[PolicyClause]:
        """Split the policy markdown into per-clause chunks keyed on POLICY-NNN."""
        chunks: list[PolicyClause] = []
        # Match bold clause headers like **POLICY-001** — ...
        pattern = re.compile(r"\*\*(POLICY-\d+)\*\*\s*[—–-]?\s*(.*?)(?=\*\*POLICY-|\Z)", re.DOTALL)
        for m in pattern.finditer(text):
            clause_id = m.group(1)
            raw_text = m.group(2).strip()
            # Remove trailing section headers / table rows
            body = raw_text.split("\n\n---")[0].strip()
            if body:
                chunks.append(PolicyClause(clause_id=clause_id, text=body, relevance_score=0.0))
        return chunks

    @staticmethod
    def _score(query: str, clause: PolicyClause) -> float:
        """Simple token-overlap relevance score."""
        query_tokens = set(re.findall(r"\w+", query.lower()))
        text_tokens = set(re.findall(r"\w+", clause.text.lower()))
        if not query_tokens:
            return 0.0
        overlap = query_tokens & text_tokens
        return len(overlap) / len(query_tokens)

    class Input(BaseTool.Input):
        query: str = Field(..., description="Free-text query to search the policy")
        top_k: int = Field(5, ge=1, le=20, description="Maximum number of clauses to return")

    class Output(BaseTool.Output):
        clauses: list[PolicyClause] = Field(default_factory=list)

    async def run(self, input: "SearchPolicy.Input") -> "SearchPolicy.Output":  # noqa: A002
        emitter = get_emitter()

        scored = [
            PolicyClause(
                clause_id=c.clause_id,
                text=c.text,
                relevance_score=self._score(input.query, c),
            )
            for c in self._chunks
        ]
        scored.sort(key=lambda c: c.relevance_score, reverse=True)
        top = scored[: input.top_k]

        emitter.emit(
            conversation_id="unknown",
            layer=LayerName.TOOLS,
            event_type="tool_invoked",
            payload={
                "tool": self.name,
                "query": input.query,
                "results": len(top),
                "top_clause": top[0].clause_id if top else None,
            },
        )

        return self.Output(clauses=top)
