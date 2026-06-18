"""Node: fraud_check — runs the L7 fraud-check logic.

Calls the fraud check logic directly (NOT via sub-graph ainvoke) to avoid
nested LangGraph async context issues when using AsyncSqliteSaver.

The scoring signals and narration are called directly from the sub-agent
module functions rather than through the compiled sub-graph.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseLanguageModel

from app.domain.models import AgentState, FraudCheckResult
from app.graph.nodes._events import async_node_scope
from app.graph.subagents.fraud_check import (
    FraudCheckState,
    _narrate_summary,
    _score_signals,
)
from app.observability import get_emitter
from app.domain.models import LayerName


async def fraud_check_node(
    state: AgentState,
    llm: BaseLanguageModel | None = None,
) -> dict[str, Any]:
    """Run the fraud-check logic and update fraud_risk_score.

    Calls the sub-agent scoring and narration functions directly to avoid
    nested sub-graph ainvoke() deadlock with AsyncSqliteSaver.
    """
    cid: str = state.conversation_id or "unknown"

    async with async_node_scope("fraud_check", cid):
        customer = state.customer
        order = state.order

        if customer is None or order is None:
            return {"fraud_risk_score": 0.0, "fraud_risk_evidence": []}

        emitter = get_emitter()
        emitter.emit(
            conversation_id=cid,
            layer=LayerName.SUBAGENTS,
            event_type="fraud_check_started",
            payload={"conversation_id": cid, "customer_id": customer.customer_id},
        )

        # Build the fraud check state
        fraud_state: FraudCheckState = {
            "conversation_id": cid,
            "customer": customer,
            "order": order,
            "refund_history": [],
            "risk_score": 0.0,
            "risk_factors": [],
            "hard_cap_triggered": False,
            "summary": "",
            "llm": llm,
        }

        # Step 1: Score signals (deterministic, sync)
        score_updates = _score_signals(fraud_state)
        fraud_state.update(score_updates)  # type: ignore[typeddict-item]

        # Step 2: Narrate summary (async, LLM call)
        narrate_updates = await _narrate_summary(fraud_state)
        fraud_state.update(narrate_updates)  # type: ignore[typeddict-item]

        risk_score: float = fraud_state["risk_score"]
        risk_factors: list[str] = fraud_state["risk_factors"]
        hard_cap: bool = fraud_state["hard_cap_triggered"]
        recommendation: str = "escalate" if (risk_score >= 0.5 or hard_cap) else "proceed"
        summary: str = fraud_state["summary"]

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

        return {
            "fraud_risk_score": result.risk_score,
            "fraud_risk_evidence": result.risk_factors,
        }
