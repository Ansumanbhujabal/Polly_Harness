"""API routes aggregator.

Exports a single ``router`` that bundles all sub-routers. Import and
include this in ``app/api/main.py``.
"""

from fastapi import APIRouter

from app.api.routes.admin import router as admin_router
from app.api.routes.approval import router as approval_router
from app.api.routes.chat import router as chat_router
from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router

router = APIRouter()

router.include_router(health_router)
router.include_router(chat_router)
router.include_router(approval_router)
router.include_router(events_router)
router.include_router(admin_router)

__all__ = ["router"]
