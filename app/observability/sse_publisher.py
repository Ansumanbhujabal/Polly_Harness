"""SSE ring buffer + push_event fan-out.

Architecture:
- Global ring buffer (deque maxlen=500) receives every event.
- Per-conversation ring buffers (deque maxlen=500) receive events for that conversation.
- An asyncio.Event is signalled on every push to wake up live SSE subscribers.
- push_event fans out to: ring buffers, Langfuse (via langfuse_client), structured logger.
- push_event NEVER raises — all failures are caught and logged WARN.

``sse_event_stream`` is an async generator that:
  1. Replays buffered events for the requested filter.
  2. Tails live events via the asyncio.Event signal.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections import deque
from collections.abc import AsyncIterator

from sse_starlette import ServerSentEvent

from app.domain.models import LayerEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ring buffers
# ---------------------------------------------------------------------------

_BUFFER_SIZE = 500

# Global buffer: all events regardless of conversation
_global_buffer: deque[LayerEvent] = deque(maxlen=_BUFFER_SIZE)

# Per-conversation buffers
_conv_buffers: dict[str, deque[LayerEvent]] = {}
_buffer_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Live-tail signalling
# ---------------------------------------------------------------------------

# One asyncio.Event per event loop that has active subscribers.
# We keep a set of weak references to all live Event objects; on each push
# we set() all of them to wake up waiting subscribers.
_live_events: list[asyncio.Event] = []
_live_events_lock = threading.Lock()


def _register_live_event(ev: asyncio.Event) -> None:
    with _live_events_lock:
        _live_events.append(ev)


def _deregister_live_event(ev: asyncio.Event) -> None:
    with _live_events_lock:
        try:
            _live_events.remove(ev)
        except ValueError:
            pass


def _notify_all_live() -> None:
    """Wake up every waiting SSE subscriber."""
    with _live_events_lock:
        for ev in list(_live_events):
            try:
                ev.set()
            except Exception:  # noqa: BLE001 — never raise from push_event
                pass


# ---------------------------------------------------------------------------
# Public: push_event fan-out
# ---------------------------------------------------------------------------


def push_event(event: LayerEvent) -> None:  # noqa: D401
    """Fan out *event* to the SSE ring buffer, Langfuse, and the structured logger.

    NEVER raises — all failures are caught and logged WARN.
    """
    # 1. Write to ring buffers
    try:
        with _buffer_lock:
            _global_buffer.append(event)
            if event.conversation_id not in _conv_buffers:
                _conv_buffers[event.conversation_id] = deque(maxlen=_BUFFER_SIZE)
            _conv_buffers[event.conversation_id].append(event)
    except Exception as exc:  # noqa: BLE001
        logger.warning("push_event_buffer_error", extra={"error": str(exc)})

    # 2. Notify live SSE subscribers
    try:
        _notify_all_live()
    except Exception as exc:  # noqa: BLE001
        logger.warning("push_event_notify_error", extra={"error": str(exc)})

    # 3. Langfuse (fail-open)
    try:
        from app.observability.langfuse_client import route_event_to_langfuse  # noqa: PLC0415

        route_event_to_langfuse(event)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "push_event_langfuse_error",
            extra={
                "error": str(exc),
                "exc_type": type(exc).__name__,
                "conversation_id": event.conversation_id,
                "event_type": event.event_type,
            },
        )

    # 4. Structured logger
    try:
        logger.debug(
            "push_event",
            extra={
                "conversation_id": event.conversation_id,
                "layer": event.layer.value,
                "event_type": event.event_type,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("push_event_log_error", extra={"error": str(exc)})


# ---------------------------------------------------------------------------
# Public: sse_event_stream
# ---------------------------------------------------------------------------


def _event_to_sse(event: LayerEvent) -> ServerSentEvent:
    """Serialise a LayerEvent to a ServerSentEvent with JSON data."""
    data = json.dumps(
        {
            "conversation_id": event.conversation_id,
            "layer": event.layer.value,
            "event_type": event.event_type,
            "payload": event.payload,
            "timestamp": event.timestamp.isoformat(),
        },
        default=str,
    )
    return ServerSentEvent(data=data, event=event.event_type)


async def sse_event_stream(
    conversation_id: str | None = None,
) -> AsyncIterator[ServerSentEvent]:
    """Async generator: replay buffered events then tail live ones.

    Args:
        conversation_id: If given, filter to events for that conversation.
                         If None, stream all events.

    Yields:
        ``ServerSentEvent`` objects ready for Starlette's EventSourceResponse.
    """
    # Snapshot buffer at connect time
    with _buffer_lock:
        if conversation_id is None:
            buffered = list(_global_buffer)
        else:
            buffered = list(_conv_buffers.get(conversation_id, []))

    # Phase 1: replay buffer
    for ev in buffered:
        yield _event_to_sse(ev)

    # Phase 2: tail live events
    live_signal = asyncio.Event()
    _register_live_event(live_signal)
    try:
        # Track what we've already yielded from the buffer so we don't re-yield
        already_yielded = len(buffered)

        while True:
            # Wait for a new push
            await live_signal.wait()
            live_signal.clear()

            # Snapshot current state of the buffer
            with _buffer_lock:
                if conversation_id is None:
                    current = list(_global_buffer)
                else:
                    current = list(_conv_buffers.get(conversation_id, []))

            # Yield any items we haven't emitted yet
            new_items = current[already_yielded:]
            for ev in new_items:
                yield _event_to_sse(ev)
            already_yielded = len(current)
    finally:
        _deregister_live_event(live_signal)


# ---------------------------------------------------------------------------
# Test helper — resets all module state between tests
# ---------------------------------------------------------------------------


def _reset_state_for_testing() -> None:
    """Clear all in-memory state. Only call from tests."""
    global _global_buffer, _conv_buffers, _live_events

    with _buffer_lock:
        _global_buffer = deque(maxlen=_BUFFER_SIZE)
        _conv_buffers = {}

    with _live_events_lock:
        _live_events = []

    # Also reset langfuse singleton so each test starts fresh
    try:
        import app.observability.langfuse_client as lfc  # noqa: PLC0415

        lfc._langfuse_instance = None
        lfc._langfuse_initialised = False
        lfc._span_stacks = {}
    except Exception:  # noqa: BLE001
        pass


def get_conversation_events(conversation_id: str) -> list[LayerEvent]:
    """Return a snapshot of buffered events for *conversation_id*, sorted by timestamp ascending."""
    with _buffer_lock:
        events = list(_conv_buffers.get(conversation_id, []))
    return sorted(events, key=lambda e: e.timestamp)


__all__ = ["push_event", "sse_event_stream", "get_conversation_events", "_reset_state_for_testing"]
