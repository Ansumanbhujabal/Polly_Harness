"""Tests for the central LayerEventEmitter."""

import pytest

from app.domain.models import LayerEvent, LayerName
from app.observability.layer_event_emitter import LayerEventEmitter


@pytest.mark.unit
def test_emit_fans_out_to_sync_sinks():
    emitter = LayerEventEmitter()
    received: list[LayerEvent] = []
    emitter.subscribe(lambda e: received.append(e))

    emitter.emit(
        conversation_id="conv-1",
        layer=LayerName.TOOLS,
        event_type="tool_called",
        payload={"tool": "lookup_customer"},
    )

    assert len(received) == 1
    assert received[0].layer == LayerName.TOOLS
    assert received[0].payload["tool"] == "lookup_customer"


@pytest.mark.unit
def test_emit_continues_after_a_sink_raises():
    emitter = LayerEventEmitter()
    good_received: list[LayerEvent] = []

    def bad_sink(event: LayerEvent) -> None:
        raise RuntimeError("oops")

    def good_sink(event: LayerEvent) -> None:
        good_received.append(event)

    emitter.subscribe(bad_sink)
    emitter.subscribe(good_sink)

    emitter.emit(conversation_id="c", layer=LayerName.VERIFICATION, event_type="ping")
    assert len(good_received) == 1


@pytest.mark.unit
def test_unsubscribe_stops_delivery():
    emitter = LayerEventEmitter()
    received: list[LayerEvent] = []

    def sink(e: LayerEvent) -> None:
        received.append(e)

    emitter.subscribe(sink)
    emitter.emit(conversation_id="c", layer=LayerName.STATE, event_type="a")
    emitter.unsubscribe(sink)
    emitter.emit(conversation_id="c", layer=LayerName.STATE, event_type="b")

    assert [e.event_type for e in received] == ["a"]
