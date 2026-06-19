"""Layer 9: Observability spine.

Every node in the harness emits a LayerEvent to the central emitter, which fans out to:
1. Langfuse (audit trail, traces, metrics)
2. SSE stream (admin dashboard live reasoning log)
3. Dynamic architecture diagram (pulses the active layer in the frontend)

Public contract (SPEC_OBSERVABILITY §Contract):
    get_emitter()         — LayerEventEmitter singleton
    get_logger(name)      — structured JSON logger
    get_langfuse_client() — lazy Langfuse singleton (None when unconfigured)
    push_event(event)     — fan-out: SSE ring buffer + Langfuse + logger
    sse_event_stream(cid) — async generator replaying buffer then tailing live
"""

from app.observability.langfuse_client import get_langfuse_client
from app.observability.layer_event_emitter import LayerEventEmitter, get_emitter
from app.observability.sse_publisher import get_conversation_events, push_event, sse_event_stream
from app.observability.structured_logger import get_logger

__all__ = [
    "LayerEventEmitter",
    "get_conversation_events",
    "get_emitter",
    "get_langfuse_client",
    "get_logger",
    "push_event",
    "sse_event_stream",
]
