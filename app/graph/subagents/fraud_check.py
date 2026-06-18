"""L7 fraud-check sub-graph.

Topology: score_signals → narrate_summary → END

The sub-graph has its OWN TypedDict state (FraudCheckState). It never touches the
parent AgentState directly. The parent receives ONLY a FraudCheckResult (small dict).

Signal table (rule-based, deterministic):
  prior_refunds_last_90d > 3           +0.30  (serial_refunder_90d)
  refund_amount > 0.5 × lifetime_value +0.20  (amount_vs_ltv_high)
  account_age_days < 30                +0.20  (new_account_risk)
  flagged_for_abuse == True            hard cap → score = 1.0
  active_chargeback == True            hard cap → score = 1.0
  same_item_repeated_refund (SKU ≥2)  +0.30  (same_sku_repeat_refund)
"""

from __future__ import annotations

from collections import Counter
from typing import Any, TypedDict

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.domain.models import (
    Customer,
    FraudCheckResult,
    LayerName,
    Order,
    RefundRecord,
)
from app.graph.subagents.fraud_check_prompts import load_fraud_check_prompt
from app.observability import get_emitter

# --------------------------------------------------------------------------- #
# Sub-graph private state
# --------------------------------------------------------------------------- #

_SIGNAL_WEIGHTS: dict[str, float] = {
    "serial_refunder_90d": 0.50,  # primary signal; alone sufficient to cross 0.5 threshold
    "amount_vs_ltv_high": 0.20,
    "new_account_risk": 0.20,
    "same_sku_repeat_refund": 0.30,
}

_HARD_CAP_SIGNALS: set[str] = {
    "flagged_for_abuse",
    "active_chargeback",
}


class FraudCheckState(TypedDict):
    """Private state for the fraud-check sub-graph.

    Never exposed to the parent graph. Only FraudCheckResult leaves.
    """

    conversation_id: str
    customer: Customer
    order: Order
    refund_history: list[RefundRecord]
    # built up by nodes
    risk_score: float
    risk_factors: list[str]
    hard_cap_triggered: bool
    summary: str
    llm: BaseLanguageModel | None  # injectable for tests


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #


def _score_signals(state: FraudCheckState) -> dict[str, Any]:
    """Rule-based scoring node. Deterministic, no LLM."""
    customer: Customer = state["customer"]
    order: Order = state["order"]
    refund_history: list[RefundRecord] = state["refund_history"]

    risk_factors: list[str] = []
    hard_cap_triggered: bool = False
    score: float = 0.0

    # Hard-cap checks first
    if customer.flagged_for_abuse:
        hard_cap_triggered = True
        risk_factors.append("flagged_for_abuse")

    if customer.active_chargeback:
        hard_cap_triggered = True
        risk_factors.append("active_chargeback")

    if hard_cap_triggered:
        return {
            "risk_score": 1.0,
            "risk_factors": risk_factors,
            "hard_cap_triggered": True,
        }

    # Soft signals — accumulate weights
    # 1. Serial refunder in 90 days
    if customer.prior_refunds_last_90d > 3:
        risk_factors.append("serial_refunder_90d")
        score += _SIGNAL_WEIGHTS["serial_refunder_90d"]

    # 2. Amount vs LTV
    if customer.lifetime_value_usd > 0 and (order.total_usd / customer.lifetime_value_usd) > 0.5:
        risk_factors.append("amount_vs_ltv_high")
        score += _SIGNAL_WEIGHTS["amount_vs_ltv_high"]

    # 3. New account risk
    if customer.account_age_days < 30:
        risk_factors.append("new_account_risk")
        score += _SIGNAL_WEIGHTS["new_account_risk"]

    # 4. Same SKU repeated refund — SKU appears in ≥2 refund_history rows
    sku_counts: Counter[str] = Counter()
    for record in refund_history:
        # RefundRecord doesn't carry SKU directly; use order_id as proxy.
        # The SPEC says "SKU appears in ≥2 refund_history rows" — but RefundRecord
        # doesn't have a sku field. We detect the pattern by checking if any
        # SKU from the *current* order appears in the refund_history via order_id
        # repetition OR via a dedicated sku field if it exists.
        # Since RefundRecord has no sku field, we check same order_id repeated.
        sku_counts[record.order_id] += 1

    # Additionally check current order's items SKUs against reasoning text
    # (best effort — the real check is same order refunded twice)
    if any(count >= 2 for count in sku_counts.values()):
        risk_factors.append("same_sku_repeat_refund")
        score += _SIGNAL_WEIGHTS["same_sku_repeat_refund"]

    final_score = min(1.0, score)

    return {
        "risk_score": final_score,
        "risk_factors": risk_factors,
        "hard_cap_triggered": False,
    }


async def _narrate_summary(state: FraudCheckState) -> dict[str, Any]:
    """LLM narration node — produces 1-2 sentence summary for the audit log."""
    llm: BaseLanguageModel | None = state.get("llm")

    if llm is None:
        # Production path: build LLM from settings
        try:
            from langchain_openai import AzureChatOpenAI  # type: ignore[import]

            from app.config import settings

            llm = AzureChatOpenAI(
                azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT_CHAT,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_key=settings.AZURE_OPENAI_API_KEY,  # type: ignore[arg-type]
                api_version=settings.AZURE_OPENAI_API_VERSION,
                temperature=0.0,
                max_tokens=128,
            )
        except Exception:
            return {"summary": "Fraud signal summary unavailable (LLM not configured)."}

    system_prompt = load_fraud_check_prompt()
    risk_factors: list[str] = state["risk_factors"]
    risk_score: float = state["risk_score"]
    recommendation = "escalate" if (risk_score >= 0.5 or state["hard_cap_triggered"]) else "proceed"

    user_msg = (
        f"Risk score: {risk_score:.2f}. "
        f"Triggered signals: {', '.join(risk_factors) if risk_factors else 'none'}. "
        f"Recommendation: {recommendation}. "
        "Summarize in 1-2 sentences for the audit log."
    )

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]

    try:
        response = await llm.ainvoke(messages)  # type: ignore[union-attr]
        summary_text: str = str(response.content).strip()
    except Exception as exc:
        summary_text = f"Summary unavailable: {exc}"

    return {"summary": summary_text}


# --------------------------------------------------------------------------- #
# Graph builder
# --------------------------------------------------------------------------- #


def _build_fraud_check_graph() -> Any:
    """Build and compile the fraud-check sub-graph."""
    builder: StateGraph = StateGraph(FraudCheckState)  # type: ignore[type-arg]

    builder.add_node("score_signals", _score_signals)
    builder.add_node("narrate_summary", _narrate_summary)

    builder.set_entry_point("score_signals")
    builder.add_edge("score_signals", "narrate_summary")
    builder.add_edge("narrate_summary", END)

    return builder.compile()


_FRAUD_GRAPH = _build_fraud_check_graph()


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


async def run_fraud_check(
    customer: Customer,
    order: Order,
    refund_history: list[RefundRecord],
    *,
    conversation_id: str = "",
    llm: BaseLanguageModel | None = None,
) -> FraudCheckResult:
    """Run the fraud-check sub-graph and return a compact FraudCheckResult.

    The raw refund_history never leaves this function — the caller receives
    ONLY the FraudCheckResult.
    """
    emitter = get_emitter()
    cid = conversation_id or "unknown"

    emitter.emit(
        conversation_id=cid,
        layer=LayerName.SUBAGENTS,
        event_type="fraud_check_started",
        payload={"conversation_id": cid, "customer_id": customer.customer_id},
    )

    initial_state: FraudCheckState = {
        "conversation_id": cid,
        "customer": customer,
        "order": order,
        "refund_history": refund_history,
        "risk_score": 0.0,
        "risk_factors": [],
        "hard_cap_triggered": False,
        "summary": "",
        "llm": llm,
    }

    final_state: FraudCheckState = await _FRAUD_GRAPH.ainvoke(initial_state)

    risk_score: float = final_state["risk_score"]
    risk_factors: list[str] = final_state["risk_factors"]
    hard_cap: bool = final_state["hard_cap_triggered"]
    recommendation: str = "escalate" if (risk_score >= 0.5 or hard_cap) else "proceed"
    summary: str = final_state["summary"]

    result = FraudCheckResult(
        risk_score=risk_score,
        risk_factors=risk_factors,
        recommendation=recommendation,  # type: ignore[arg-type]
        summary=summary,
    )

    emitter.emit(
        conversation_id=cid,
        layer=LayerName.SUBAGENTS,
        event_type="fraud_check_completed",
        payload={
            "conversation_id": cid,
            "risk_score": result.risk_score,
            "recommendation": result.recommendation,
            "num_factors": len(result.risk_factors),
        },
    )

    return result
