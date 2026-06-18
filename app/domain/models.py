"""Shared domain models.

Single source of truth for the data shapes that cross layer boundaries. Every component
agent in the harness imports from here. If you find yourself defining a parallel
dataclass in a layer-specific file, stop and add it here instead.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Enumerations — referenced across layers
# --------------------------------------------------------------------------- #


class LayerName(str, Enum):
    """The 9 harness layers + cross-cutting infra. Every emitted event is tagged with one."""

    INSTRUCTIONS = "L1_INSTRUCTIONS"
    CONTEXT = "L2_CONTEXT"
    TOOLS = "L3_TOOLS"
    EXECUTION = "L4_EXECUTION"
    STATE = "L5_STATE"
    ORCHESTRATION = "L6_ORCHESTRATION"
    SUBAGENTS = "L7_SUBAGENTS"
    SKILLS = "L8_SKILLS"
    VERIFICATION = "L9_VERIFICATION"
    INCIDENT_LOOP = "INCIDENT_LOOP"  # cross-cutting feedback loop
    CACHE = "CACHE"  # cross-cutting


class CustomerTier(str, Enum):
    STANDARD = "standard"
    PREMIUM = "premium"
    VIP = "vip"


class OrderStatus(str, Enum):
    PENDING = "pending"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    DELIVERED_LATE = "delivered_late"
    DELIVERED_DISPUTED = "delivered_disputed"
    RETURNED = "returned"
    CANCELLED = "cancelled"


class RefundDecisionKind(str, Enum):
    APPROVE_FULL = "approve_full"
    APPROVE_PARTIAL = "approve_partial"
    APPROVE_STORE_CREDIT = "approve_store_credit"
    DENY = "deny"
    ESCALATE = "escalate"


# --------------------------------------------------------------------------- #
# CRM models
# --------------------------------------------------------------------------- #


class Customer(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    customer_id: str
    name: str
    email: str
    phone: str = ""
    tier: CustomerTier = CustomerTier.STANDARD
    account_age_days: int = 0
    lifetime_value_usd: float = 0.0
    prior_refund_count: int = 0
    prior_refunds_last_90d: int = 0
    flagged_for_abuse: bool = False
    active_chargeback: bool = False
    notes: str = ""

    @property
    def auto_approval_cap_usd(self) -> float:
        """Per POLICY-012 / POLICY-002."""
        return 500.0 if self.tier == CustomerTier.VIP.value else 200.0

    @property
    def return_window_days(self) -> int:
        """Per POLICY-001 / POLICY-002."""
        return 60 if self.tier == CustomerTier.VIP.value else 14


class Item(BaseModel):
    sku: str
    name: str
    category: str
    qty: int = 1
    unit_price_usd: float


class Order(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    order_id: str
    customer_id: str
    items: list[Item]
    total_usd: float
    purchase_date: str  # ISO date
    delivery_date: str | None = None
    scheduled_delivery_date: str | None = None
    status: OrderStatus = OrderStatus.PENDING
    item_condition_reported: str = "new_unopened"
    payment_method: str = ""
    chargeback_ref: str | None = None
    carrier_delay_days: int = 0
    customer_claim: str | None = None
    defect_report_date: str | None = None


# --------------------------------------------------------------------------- #
# Agent state — passed between LangGraph nodes
# --------------------------------------------------------------------------- #


class PolicyClause(BaseModel):
    """A retrieved policy chunk grounded in `data/policy/refund_policy_v1.md`."""

    clause_id: str  # e.g., POLICY-008
    text: str
    relevance_score: float = 0.0


class ToolInvocation(BaseModel):
    """One execution of a tool. Logged to durable state + emitted as a LayerEvent."""

    tool_name: str
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: float = 0.0
    retry_count: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)


class VerificationCheck(BaseModel):
    """One verification gate result (Layer 9)."""

    check_name: str  # e.g., "policy_assertion_return_window", "injection_check"
    passed: bool
    detail: str = ""
    severity: Literal["info", "warn", "block"] = "info"


class VerificationResult(BaseModel):
    """Aggregate of all checks run against a candidate decision."""

    checks: list[VerificationCheck] = Field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(c.severity == "block" and not c.passed for c in self.checks)

    @property
    def failures(self) -> list[VerificationCheck]:
        return [c for c in self.checks if not c.passed]


class RefundDecision(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    kind: RefundDecisionKind
    amount_usd: float = 0.0
    reason_summary: str
    cited_clause_ids: list[str] = Field(default_factory=list)
    escalation_code: str | None = None  # e.g., ABUSE_FLAG_PRESENT
    requires_human_approval: bool = False


class AgentState(BaseModel):
    """The LangGraph state object — passed between nodes, persisted via SqliteSaver."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    conversation_id: str
    messages: list[dict[str, Any]] = Field(default_factory=list)

    # Identified entities
    customer: Customer | None = None
    order: Order | None = None
    stated_email: str | None = None

    # Retrieved context
    relevant_clauses: list[PolicyClause] = Field(default_factory=list)
    loaded_skills: list[str] = Field(default_factory=list)  # skill IDs

    # Reasoning artifacts
    intent: str | None = None  # refund_request | exchange_request | inquiry | off_topic
    tool_invocations: list[ToolInvocation] = Field(default_factory=list)
    candidate_decision: RefundDecision | None = None
    final_decision: RefundDecision | None = None
    verification: VerificationResult = Field(default_factory=VerificationResult)

    # Sub-agent outputs
    fraud_risk_score: float | None = None
    fraud_risk_evidence: list[str] = Field(default_factory=list)

    # Approval gate
    awaiting_human_approval: bool = False
    approval_resolution: Literal["approved", "denied", None] = None

    # Final response
    response_text: str | None = None


# --------------------------------------------------------------------------- #
# Cross-cutting: events + incidents
# --------------------------------------------------------------------------- #


class LayerEvent(BaseModel):
    """One observable event from somewhere in the harness.

    Every node, tool, verification check, sub-agent emits one of these. The event spine
    fans it out to Langfuse, the SSE stream (admin dashboard), and the dynamic diagram.
    """

    conversation_id: str
    layer: LayerName
    event_type: str  # e.g., "node_entered", "tool_called", "check_failed"
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class IncidentRecord(BaseModel):
    """A structured incident the failure-to-infrastructure loop will consume.

    Written by `app/learning/incident_logger.py` whenever a verification check
    fails OR a HITL approval overrides the agent's recommendation OR a tool
    fails after all retries. Periodically distilled into PR-ready proposals
    for new skills / verification rules / policy clarifications.
    """

    incident_id: str
    conversation_id: str
    triggered_by: Literal[
        "verification_failure",
        "hitl_override",
        "tool_failure",
        "injection_detected",
    ]
    layer: LayerName
    summary: str
    detail: dict[str, Any] = Field(default_factory=dict)
    proposed_remediation: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --------------------------------------------------------------------------- #
# L5 Durable State models — persisted to SQLite by app/state/repositories.py
# --------------------------------------------------------------------------- #


class FraudCheckResult(BaseModel):
    """Output of the L7 fraud-check sub-agent.

    The parent graph stores ONLY this object — never the raw refund_history list.
    That isolation is the entire point of L7: protect the parent's context budget
    from a potentially-long refund-history payload.
    """

    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_factors: list[str]  # ordered, highest-weight first
    recommendation: Literal["proceed", "escalate"]
    summary: str  # LLM-narrated, ≤ 2 sentences


class RefundRecord(BaseModel):
    """A successfully issued refund, persisted to the `refunds` table.

    Business key: (conversation_id, order_id) — insert-or-noop on duplicate.
    """

    model_config = ConfigDict(use_enum_values=True)

    refund_id: str
    conversation_id: str
    order_id: str
    customer_id: str
    amount_usd: float
    kind: RefundDecisionKind
    cited_clauses: list[str] = Field(default_factory=list)
    reasoning: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EscalationRecord(BaseModel):
    """A human-handoff record, persisted to the `escalations` table."""

    escalation_id: str
    conversation_id: str
    reason_code: str
    severity: Literal["low", "medium", "high"] = "medium"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PendingApproval(BaseModel):
    """A decision awaiting human approval, persisted to the `pending_approvals` table.

    `resolution` is NULL until a human approves or denies.
    `resolve_approval()` on the Repository flips the row to a terminal state.
    """

    approval_id: str
    conversation_id: str
    candidate_decision: RefundDecision
    required_approver_role: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolution: Literal["approved", "denied", None] = None
    approver: str | None = None
    resolved_at: datetime | None = None
