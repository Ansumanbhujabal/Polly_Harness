"""Admin API routes: /admin/api/* group."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.domain.models import IncidentRecord, LayerEvent, PendingApproval, ProposedRemediation
from app.learning import distill_incidents
from app.observability import get_conversation_events
from app.state import get_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class PendingApprovalsResponse(BaseModel):
    items: list[PendingApproval]


class IncidentsResponse(BaseModel):
    items: list[IncidentRecord]


class TraceResponse(BaseModel):
    items: list[LayerEvent]


class DistillResponse(BaseModel):
    accepted: bool
    proposals: list[ProposedRemediation]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/pending_approvals", response_model=PendingApprovalsResponse)
async def pending_approvals() -> Any:
    """List all unresolved pending approvals."""
    repo = get_repository()
    items = repo.list_pending_approvals()
    return PendingApprovalsResponse(items=items)


@router.get("/incidents", response_model=IncidentsResponse)
async def incidents(limit: int = Query(default=20, ge=1, le=500)) -> Any:
    """List recent incidents, most recent first, up to *limit*."""
    repo = get_repository()
    items = repo.list_incidents(limit=limit)
    return IncidentsResponse(items=items)


@router.get("/conversations/{conversation_id}/trace", response_model=TraceResponse)
async def conversation_trace(conversation_id: str) -> Any:
    """Return all buffered LayerEvents for a conversation, sorted ascending by timestamp."""
    events = get_conversation_events(conversation_id)
    return TraceResponse(items=events)


@router.post("/distill", response_model=DistillResponse)
async def distill() -> Any:
    """Trigger incident distillation and return the resulting proposals."""
    try:
        proposals = await distill_incidents()
    except Exception as exc:  # noqa: BLE001
        logger.error("distill_route_error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return DistillResponse(accepted=True, proposals=proposals)
