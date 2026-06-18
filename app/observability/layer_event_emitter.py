"""Central event spine. Every layer emits events here.

Why this exists:
  Layer 9 (Verification + Observability) needs to see every action across every other
  layer. Rather than have each layer write directly to Langfuse / SSE / the diagram,
  every layer emits to *this* and the emitter fans out. One place to add new sinks.

Sinks (registered at app startup by main.py):
  1. langfuse_sink — writes to the Langfuse trace tree
  2. sse_sink — pushes events to subscribed admin dashboard SSE clients
  3. diagram_sink — narrow projection used by the dynamic architecture diagram

Subscribers register a callback. Emit is non-blocking and never raises into the caller.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from typing import Any

from app.domain.models import LayerEvent, LayerName
from app.observability.structured_logger import get_logger

logger = get_logger(__name__)

# Imported at module level so tests can patch ``app.observability.layer_event_emitter.push_event``.
# The actual implementation lives in sse_publisher; this name is just a re-export alias.
# Use a late import to avoid circular imports at startup — the name is assigned below.
try:
    from app.observability.sse_publisher import push_event  # noqa: F401
except ImportError:  # pragma: no cover
    def push_event(event: LayerEvent) -> None:  # type: ignore[misc]
        pass

Sink = Callable[[LayerEvent], Awaitable[None] | None]


class LayerEventEmitter:
    """In-process pub/sub for LayerEvents. Thread-safe for sync sinks; async sinks are
    scheduled on the running event loop if one exists, else fire-and-forget."""

    def __init__(self) -> None:
        self._sinks: list[Sink] = []
        self._lock = threading.Lock()

    def subscribe(self, sink: Sink) -> None:
        with self._lock:
            self._sinks.append(sink)

    def unsubscribe(self, sink: Sink) -> None:
        with self._lock:
            try:
                self._sinks.remove(sink)
            except ValueError:
                pass

    def emit(
        self,
        *,
        conversation_id: str,
        layer: LayerName,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        event = LayerEvent(
            conversation_id=conversation_id,
            layer=layer,
            event_type=event_type,
            payload=payload or {},
        )
        logger.debug(
            "layer_event",
            extra={
                "conversation_id": conversation_id,
                "layer": layer.value,
                "event_type": event_type,
            },
        )
        # Fan out through the observability spine (SSE + Langfuse + structured log).
        # Use the module-level name so tests can patch it via
        # ``app.observability.layer_event_emitter.push_event``.
        try:
            push_event(event)
        except Exception as exc:  # noqa: BLE001 — push_event must never poison emitter
            logger.warning("push_event_error", extra={"error": str(exc)})

        for sink in list(self._sinks):
            try:
                result = sink(event)
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        # No running loop; run in a throwaway loop on a worker.
                        # We don't want to block emit, so spin a one-shot thread.
                        threading.Thread(
                            target=_run_coro_in_thread, args=(result,), daemon=True
                        ).start()
            except Exception as exc:  # noqa: BLE001 — sinks must never poison the emitter
                logger.warning("event_sink_error", extra={"error": str(exc)})


def _run_coro_in_thread(coro: Awaitable[None]) -> None:
    try:
        asyncio.run(coro)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001
        logger.warning("async_sink_error", extra={"error": str(exc)})


_global_emitter: LayerEventEmitter | None = None


def get_emitter() -> LayerEventEmitter:
    """Process-global emitter. Use this everywhere; lifecycle is managed by app.main."""
    global _global_emitter
    if _global_emitter is None:
        _global_emitter = LayerEventEmitter()
    return _global_emitter
