"""GET /healthz — liveness + dependency status probe.

Fast (1-second timeout per dep). Always returns 200; `ok` field reflects
aggregate health so callers can distinguish "alive but degraded."
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    ok: bool
    version: str
    qdrant: str  # "up" | "down"
    langfuse: str  # "up" | "down"


async def _probe_qdrant() -> str:
    """Return 'up' if Qdrant /healthz responds 2xx within 1 s, else 'down'."""
    url = settings.QDRANT_URL.rstrip("/") + "/healthz"
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.get(url)
        return "up" if response.status_code < 300 else "down"
    except Exception:  # noqa: BLE001
        return "down"


async def _probe_langfuse() -> str:
    """Return 'up' if Langfuse is configured and responds, else 'down'."""
    if not settings.langfuse_configured:
        return "down"
    url = settings.LANGFUSE_HOST.rstrip("/") + "/api/public/health"
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.get(url)
        return "up" if response.status_code < 300 else "down"
    except Exception:  # noqa: BLE001
        return "down"


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Liveness + dependency status. Always 200; inspect `ok` for health."""
    qdrant_status, langfuse_status = await asyncio.gather(
        _probe_qdrant(),
        _probe_langfuse(),
    )
    ok = qdrant_status == "up" and langfuse_status == "up"
    return HealthResponse(
        ok=ok,
        version="0.1.0",
        qdrant=qdrant_status,
        langfuse=langfuse_status,
    )
