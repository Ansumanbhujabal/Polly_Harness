"""Node event helper — emits node_entered / node_exited for every graph node.

Usage (context manager):
    async with node_scope("intake", state.conversation_id):
        ...

Usage (sync):
    with node_scope("classify_intent", state.conversation_id):
        ...

Every node MUST use this so test_every_node_emits_entered_and_exited passes.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from app.domain.models import LayerName
from app.observability import get_emitter


@contextmanager
def node_scope(name: str, conversation_id: str) -> Generator[None, None, None]:
    """Sync context manager: emit node_entered on enter, node_exited on exit."""
    emitter = get_emitter()
    emitter.emit(
        conversation_id=conversation_id,
        layer=LayerName.ORCHESTRATION,
        event_type="node_entered",
        payload={"node": name, "conversation_id": conversation_id},
    )
    start = time.monotonic()
    try:
        yield
    finally:
        latency_ms = (time.monotonic() - start) * 1000
        emitter.emit(
            conversation_id=conversation_id,
            layer=LayerName.ORCHESTRATION,
            event_type="node_exited",
            payload={
                "node": name,
                "conversation_id": conversation_id,
                "latency_ms": latency_ms,
            },
        )


@asynccontextmanager
async def async_node_scope(name: str, conversation_id: str) -> AsyncGenerator[None, None]:
    """Async context manager: emit node_entered on enter, node_exited on exit."""
    emitter = get_emitter()
    emitter.emit(
        conversation_id=conversation_id,
        layer=LayerName.ORCHESTRATION,
        event_type="node_entered",
        payload={"node": name, "conversation_id": conversation_id},
    )
    start = time.monotonic()
    try:
        yield
    finally:
        latency_ms = (time.monotonic() - start) * 1000
        emitter.emit(
            conversation_id=conversation_id,
            layer=LayerName.ORCHESTRATION,
            event_type="node_exited",
            payload={
                "node": name,
                "conversation_id": conversation_id,
                "latency_ms": latency_ms,
            },
        )
