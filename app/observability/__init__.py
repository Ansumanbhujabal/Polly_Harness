"""Layer 9: Observability spine.

Every node in the harness emits a LayerEvent to the central emitter, which fans out to:
1. Langfuse (audit trail, traces, metrics)
2. SSE stream (admin dashboard live reasoning log)
3. Dynamic architecture diagram (pulses the active layer in the frontend)
"""
from app.observability.layer_event_emitter import LayerEventEmitter, get_emitter
from app.observability.structured_logger import get_logger

__all__ = ["LayerEventEmitter", "get_emitter", "get_logger"]
