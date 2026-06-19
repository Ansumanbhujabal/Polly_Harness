"""GET /events/stream?conversation_id=... — live SSE trace stream."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response
from sse_starlette import EventSourceResponse

from app.observability import sse_event_stream

router = APIRouter()


@router.get("/events/stream")
async def events_stream(conversation_id: str | None = None) -> Response:
    """Stream LayerEvents as Server-Sent Events.

    Query param:
        conversation_id: Filter to events for this conversation.
                         Omit to stream all events.
    """
    generator = sse_event_stream(conversation_id=conversation_id)
    return EventSourceResponse(generator, ping=15)
