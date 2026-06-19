"""POST /api/v1/chat — drive one conversation turn through the RefundGraph."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.domain.models import AgentState, RefundDecision
from app.graph import RefundGraph, build_graph
from app.tools import get_tool_by_name
from app.tools.executor import run_tool

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str
    customer_id: str | None = None
    order_id: str | None = None


class AgentStateSummary(BaseModel):
    """Small Pydantic projection of AgentState for API consumers.

    NOT exported from this module — used only in ChatResponse.
    """

    conversation_id: str
    final_decision: RefundDecision | None
    response_text: str | None
    num_tool_invocations: int
    awaiting_human_approval: bool


class ChatResponse(BaseModel):
    accepted: bool
    conversation_id: str
    final_state_summary: AgentStateSummary


class ErrorResponse(BaseModel):
    accepted: bool = False
    error_code: str
    detail: str


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/api/v1/chat")
async def chat(request: ChatRequest) -> Any:
    """Drive one conversation turn. Returns AgentStateSummary on success."""
    conversation_id = request.conversation_id or str(uuid.uuid4())

    try:
        graph: RefundGraph = await build_graph()

        prefilled_customer = None
        prefilled_order = None
        if request.customer_id:
            tool = get_tool_by_name("lookup_customer")
            if tool is not None:
                r = await run_tool(
                    tool, {"customer_id": request.customer_id}, conversation_id=conversation_id
                )
                if r["ok"] and r["output"] and r["output"].get("customer"):
                    prefilled_customer = r["output"]["customer"]
        if request.order_id and prefilled_customer is not None:
            tool = get_tool_by_name("get_order")
            if tool is not None:
                cust_id = (
                    prefilled_customer.customer_id
                    if hasattr(prefilled_customer, "customer_id")
                    else prefilled_customer.get("customer_id", "")
                )
                r = await run_tool(
                    tool,
                    {"order_id": request.order_id, "customer_id": cust_id},
                    conversation_id=conversation_id,
                )
                if r["ok"] and r["output"] and r["output"].get("order"):
                    prefilled_order = r["output"]["order"]

        initial_state = AgentState(
            conversation_id=conversation_id,
            messages=[{"role": "user", "content": request.message}],
            customer=prefilled_customer,
            order=prefilled_order,
        )
        config: dict[str, Any] = {
            "configurable": {"thread_id": conversation_id},
        }

        result: dict[str, Any] = await graph.ainvoke(initial_state, config)

        # Build summary from result dict
        final_decision: RefundDecision | None = None
        fd_raw = result.get("final_decision")
        if fd_raw is not None:
            if isinstance(fd_raw, RefundDecision):
                final_decision = fd_raw
            else:
                final_decision = RefundDecision.model_validate(fd_raw)

        summary = AgentStateSummary(
            conversation_id=result.get("conversation_id", conversation_id),
            final_decision=final_decision,
            response_text=result.get("response_text"),
            num_tool_invocations=len(result.get("tool_invocations", [])),
            awaiting_human_approval=bool(result.get("awaiting_human_approval", False)),
        )

        return ChatResponse(
            accepted=True,
            conversation_id=conversation_id,
            final_state_summary=summary,
        )

    except Exception as exc:  # noqa: BLE001
        logger.error("chat_route_error: %s", exc)
        # Upstream Azure content-filter rejections produce a 400; serve a soft response
        # so the chat UI shows a refusal rather than a stack trace.
        msg = str(exc)
        if "content_filter" in msg or "ResponsibleAIPolicy" in msg or "jailbreak" in msg.lower():
            summary = AgentStateSummary(
                conversation_id=conversation_id,
                final_decision=None,
                response_text=(
                    "I can't process that message. If you'd like help with a refund, "
                    "share the order ID and what's wrong with the item and I'll take it from there."
                ),
                num_tool_invocations=0,
                awaiting_human_approval=False,
            )
            return ChatResponse(
                accepted=True,
                conversation_id=conversation_id,
                final_state_summary=summary,
            )
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail=str(exc)) from exc
