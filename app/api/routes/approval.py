"""POST /api/v1/approve — resolve a pending approval and resume the graph."""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.graph import RefundGraph, build_graph
from app.state import get_repository

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ApproveRequest(BaseModel):
    approval_id: str
    resolution: Literal["approved", "denied"]
    approver: str


class ApproveResponse(BaseModel):
    accepted: bool
    resource_id: str  # = approval_id


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/api/v1/approve")
async def approve(request: ApproveRequest) -> Any:
    """Resolve a pending approval and resume the suspended graph thread."""
    repo = get_repository()

    # Validate existence and unresolved state — resolve_approval validates in one step
    try:
        resolved = repo.resolve_approval(
            approval_id=request.approval_id,
            resolution=request.resolution,
            approver=request.approver,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg) from exc
        if "already resolved" in msg:
            raise HTTPException(status_code=409, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc

    # Resume the graph thread
    try:
        graph: RefundGraph = await build_graph()
        config: dict[str, Any] = {
            "configurable": {"thread_id": resolved.conversation_id},
        }
        await graph.aresume(config=config, approval=request.resolution)
    except Exception as exc:  # noqa: BLE001
        # Log the error but don't fail — the approval was persisted
        logger.error("approve_route_graph_resume_error: %s", exc)

    return ApproveResponse(
        accepted=True,
        resource_id=request.approval_id,
    )
