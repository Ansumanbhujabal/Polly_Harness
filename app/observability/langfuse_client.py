"""Lazy Langfuse singleton with fail-open span nesting.

The client is only created when first requested AND ``settings.langfuse_configured``
is True. Once created, it is reused for the process lifetime.

Span nesting follows event chronology + ``LayerName``:
- Entering a layer opens a child span (e.g. ``node_entered`` → span open).
- Exiting the matching layer closes the open span (``node_exited`` → span.end()).

All Langfuse API calls are wrapped so that any exception is caught, logged at
WARNING, and silently swallowed — ``push_event`` must remain side-effect-only.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.config import settings
from app.domain.models import LayerEvent, LayerName

logger = logging.getLogger(__name__)

# Module-level singleton guards
_langfuse_lock = threading.Lock()
_langfuse_instance: Any | None = None  # Langfuse | None at runtime
_langfuse_initialised: bool = False

# Maps event_type → whether this event *opens* a span
_SPAN_OPEN_EVENTS: frozenset[str] = frozenset(
    {
        "node_entered",
        "tool_invoked",
        "fraud_check_started",
        "check_started",
        "skill_loaded",
    }
)

# Maps open event_type → its closing counterpart
_SPAN_CLOSE_PAIRS: dict[str, str] = {
    "node_entered": "node_exited",
    "tool_invoked": "tool_succeeded",
    "fraud_check_started": "fraud_check_completed",
    "check_started": "check_passed",  # or check_failed — both close
    "skill_loaded": "skill_routed",
}
# Reverse: close event → opening event
_SPAN_OPEN_FOR_CLOSE: dict[str, str] = {v: k for k, v in _SPAN_CLOSE_PAIRS.items()}
# Extra close events that map to the same opener (e.g. check_failed also closes check_started)
_EXTRA_CLOSE: dict[str, str] = {
    "check_failed": "check_started",
    "tool_failed": "tool_invoked",
    "node_exited": "node_entered",
}
_SPAN_OPEN_FOR_CLOSE.update(_EXTRA_CLOSE)

# Per-conversation span stacks: {conversation_id: {open_event_type: span_object}}
_span_stacks: dict[str, dict[str, Any]] = {}
_span_stack_lock = threading.Lock()


def get_langfuse_client() -> Any | None:  # Langfuse | None
    """Return the process-wide Langfuse client, or None if unconfigured.

    Lazy: the client is created on first call. Thread-safe.
    """
    global _langfuse_instance, _langfuse_initialised

    if _langfuse_initialised:
        return _langfuse_instance

    with _langfuse_lock:
        if _langfuse_initialised:
            return _langfuse_instance

        if not settings.langfuse_configured:
            logger.debug("langfuse_unconfigured: skipping client init")
            _langfuse_instance = None
        else:
            try:
                from langfuse import Langfuse  # noqa: PLC0415

                _langfuse_instance = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_HOST,
                )
                logger.info("langfuse_client_created", extra={"host": settings.LANGFUSE_HOST})
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "langfuse_init_failed",
                    extra={"error": str(exc), "exc_type": type(exc).__name__},
                )
                _langfuse_instance = None

        _langfuse_initialised = True
        return _langfuse_instance


def route_event_to_langfuse(event: LayerEvent) -> None:
    """Fan out one ``LayerEvent`` to Langfuse as a span or event.

    Fails open: any exception is caught, logged WARN, and swallowed.
    """
    try:
        _route_event_to_langfuse_unsafe(event)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "langfuse_route_failed",
            extra={
                "error": str(exc),
                "exc_type": type(exc).__name__,
                "conversation_id": event.conversation_id,
                "event_type": event.event_type,
                "layer": event.layer.value,
            },
        )


def _route_event_to_langfuse_unsafe(event: LayerEvent) -> None:
    """Inner (may raise) implementation — always call via ``route_event_to_langfuse``."""
    client = get_langfuse_client()
    if client is None:
        return

    conv_id = event.conversation_id
    et = event.event_type

    with _span_stack_lock:
        if conv_id not in _span_stacks:
            _span_stacks[conv_id] = {}

        stack = _span_stacks[conv_id]

        if et in _SPAN_OPEN_EVENTS:
            # Open a new span
            span = client.start_observation(
                name=f"{event.layer.value}:{et}",
                as_type="span",
                metadata={
                    "conversation_id": conv_id,
                    "layer": event.layer.value,
                    "event_type": et,
                    **event.payload,
                },
            )
            stack[et] = span

        elif et in _SPAN_OPEN_FOR_CLOSE:
            opener_et = _SPAN_OPEN_FOR_CLOSE[et]
            span = stack.pop(opener_et, None)
            if span is not None:
                span.end()

        else:
            # Simple point event — log as Langfuse event
            client.create_event(
                name=f"{event.layer.value}:{et}",
                metadata={
                    "conversation_id": conv_id,
                    "layer": event.layer.value,
                    **event.payload,
                },
            )


def shutdown_langfuse() -> None:
    """Flush and close the Langfuse client. Call from app lifespan shutdown."""
    global _langfuse_instance, _langfuse_initialised
    with _langfuse_lock:
        if _langfuse_instance is not None:
            try:
                _langfuse_instance.shutdown()
            except Exception as exc:  # noqa: BLE001
                logger.warning("langfuse_shutdown_error", extra={"error": str(exc)})
        _langfuse_instance = None
        _langfuse_initialised = False


__all__ = [
    "get_langfuse_client",
    "route_event_to_langfuse",
    "shutdown_langfuse",
]
