"""Tests for the observability layer: SSE publisher, Langfuse client, push_event fan-out.

Tests are ordered to mirror the spec (SPEC_OBSERVABILITY.md §Tests).
All 9 tests must pass; existing test_event_emitter.py must continue to pass.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.domain.models import LayerEvent, LayerName
from app.observability.event_types import EVENT_TYPE_CATALOG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    conv_id: str = "conv-1",
    layer: LayerName = LayerName.ORCHESTRATION,
    event_type: str = "node_entered",
    payload: dict[str, Any] | None = None,
) -> LayerEvent:
    return LayerEvent(
        conversation_id=conv_id,
        layer=layer,
        event_type=event_type,
        payload=payload or {},
    )


async def _collect_n(
    stream: AsyncIterator[Any],
    n: int,
    timeout: float = 2.0,
) -> list[Any]:
    """Collect exactly *n* items from an async iterator with a timeout guard."""
    results: list[Any] = []
    async with asyncio.timeout(timeout):
        async for item in stream:
            results.append(item)
            if len(results) >= n:
                break
    return results


# ---------------------------------------------------------------------------
# Test 1 — push_event writes to ring buffer
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_push_event_writes_to_ring_buffer():
    """push 3 events; sse_event_stream immediately yields all 3."""
    # Import fresh to avoid cross-test state leakage
    from app.observability import push_event, sse_event_stream
    from app.observability.sse_publisher import _reset_state_for_testing

    _reset_state_for_testing()

    events = [
        _make_event("conv-tb1", LayerName.ORCHESTRATION, "node_entered"),
        _make_event("conv-tb1", LayerName.TOOLS, "tool_invoked"),
        _make_event("conv-tb1", LayerName.VERIFICATION, "check_started"),
    ]
    for ev in events:
        push_event(ev)

    collected = await _collect_n(sse_event_stream(conversation_id="conv-tb1"), 3)
    assert len(collected) == 3


# ---------------------------------------------------------------------------
# Test 2 — SSE stream replays buffered then tails live
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sse_event_stream_replays_buffered_then_tails_live():
    """push 2 pre-stream events, start streaming, push 1 live; assert 2+1 order."""
    import json

    from app.observability import push_event, sse_event_stream
    from app.observability.sse_publisher import _reset_state_for_testing

    _reset_state_for_testing()

    ev1 = _make_event("conv-rt2", LayerName.STATE, "write_performed")
    ev2 = _make_event("conv-rt2", LayerName.SKILLS, "skill_loaded")
    ev3 = _make_event("conv-rt2", LayerName.VERIFICATION, "check_passed")

    push_event(ev1)
    push_event(ev2)

    results: list[Any] = []

    async def stream_collector() -> None:
        """Consume 3 items from sse_event_stream."""
        async with asyncio.timeout(3.0):
            async for item in sse_event_stream(conversation_id="conv-rt2"):
                results.append(item)
                if len(results) >= 3:
                    break

    async def delayed_push() -> None:
        """Wait a tick then push the live event."""
        await asyncio.sleep(0.05)
        push_event(ev3)

    # Run both concurrently: the stream replays 2 buffered, then waits;
    # delayed_push fires ev3 while the stream is waiting.
    await asyncio.gather(stream_collector(), delayed_push())

    assert len(results) == 3
    first_data = json.loads(results[0].data)
    second_data = json.loads(results[1].data)
    third_data = json.loads(results[2].data)
    assert first_data["event_type"] == "write_performed"
    assert second_data["event_type"] == "skill_loaded"
    assert third_data["event_type"] == "check_passed"


# ---------------------------------------------------------------------------
# Test 3 — SSE stream filtered by conversation_id
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sse_event_stream_filtered_by_conversation_id():
    """Events for conv 'a' must not appear when subscribing to conv 'b'."""
    from app.observability import push_event, sse_event_stream
    from app.observability.sse_publisher import _reset_state_for_testing

    _reset_state_for_testing()

    for i in range(3):
        push_event(_make_event("conv-a", LayerName.ORCHESTRATION, "node_entered", {"i": i}))
    for i in range(2):
        push_event(_make_event("conv-b", LayerName.TOOLS, "tool_invoked", {"i": i}))

    collected_b = await _collect_n(sse_event_stream(conversation_id="conv-b"), 2)
    assert len(collected_b) == 2

    import json

    for item in collected_b:
        data = json.loads(item.data)
        assert data["conversation_id"] == "conv-b"


# ---------------------------------------------------------------------------
# Test 4 — push_event swallows Langfuse failure, logs WARN
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_push_event_swallows_langfuse_failure_and_logs_warn(caplog: pytest.LogCaptureFixture):
    """Langfuse HTTP 500 → push_event must not raise; a WARN log must appear."""
    import logging

    from app.observability.sse_publisher import _reset_state_for_testing

    _reset_state_for_testing()

    # Patch the Langfuse client to raise on any call
    mock_lf = MagicMock()
    mock_lf.start_observation.side_effect = RuntimeError("langfuse 500")

    with patch("app.observability.langfuse_client._langfuse_instance", mock_lf):
        with patch("app.observability.langfuse_client.get_langfuse_client", return_value=mock_lf):
            from app.observability import push_event

            ev = _make_event("conv-lf4", LayerName.ORCHESTRATION, "node_entered")

            with caplog.at_level(logging.WARNING):
                # Must NOT raise
                push_event(ev)

    # A WARN line must have been logged (either from langfuse_client or push_event itself)
    warn_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warn_messages) >= 1


# ---------------------------------------------------------------------------
# Test 5 — get_langfuse_client returns None when unconfigured
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_langfuse_client_returns_none_when_unconfigured(monkeypatch):
    """When LANGFUSE_PUBLIC_KEY/SECRET_KEY are empty, get_langfuse_client() -> None."""
    import app.observability.langfuse_client as lfc

    # Reset singleton so the lazy init fires again
    monkeypatch.setattr(lfc, "_langfuse_instance", None)
    monkeypatch.setattr(lfc, "_langfuse_initialised", False)

    monkeypatch.setattr(lfc.settings, "LANGFUSE_PUBLIC_KEY", "", raising=False)
    monkeypatch.setattr(lfc.settings, "LANGFUSE_SECRET_KEY", "", raising=False)

    result = lfc.get_langfuse_client()
    assert result is None


# ---------------------------------------------------------------------------
# Test 6 — ring buffer evicts oldest when full
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ring_buffer_evicts_oldest_when_full():
    """Push 501 events; buffer holds latest 500; first is gone."""
    from app.observability import push_event, sse_event_stream
    from app.observability.sse_publisher import _reset_state_for_testing

    _reset_state_for_testing()

    for i in range(501):
        push_event(_make_event("conv-buf6", LayerName.STATE, "write_performed", {"i": i}))

    import json

    collected = await _collect_n(sse_event_stream(conversation_id="conv-buf6"), 500)
    assert len(collected) == 500
    # First event in buffer should be the 2nd push (i=1), not i=0
    first_payload = json.loads(collected[0].data)["payload"]
    assert first_payload["i"] == 1


# ---------------------------------------------------------------------------
# Test 7 — Langfuse span nesting matches event chronology
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_langfuse_span_nesting_matches_event_chronology():
    """node_entered → tool_invoked → tool_succeeded → node_exited produces nested spans."""
    from app.observability.sse_publisher import _reset_state_for_testing

    _reset_state_for_testing()

    # Build a mock Langfuse client + span objects
    mock_node_span = MagicMock()
    mock_tool_span = MagicMock()

    mock_lf = MagicMock()
    # First start_observation → node span; second → tool span
    mock_lf.start_observation.side_effect = [mock_node_span, mock_tool_span]

    with patch("app.observability.langfuse_client.get_langfuse_client", return_value=mock_lf):
        from app.observability import push_event

        push_event(_make_event("conv-nest7", LayerName.ORCHESTRATION, "node_entered", {"node": "verify"}))
        push_event(_make_event("conv-nest7", LayerName.TOOLS, "tool_invoked", {"tool": "lookup"}))
        push_event(_make_event("conv-nest7", LayerName.TOOLS, "tool_succeeded", {"tool": "lookup"}))
        push_event(_make_event("conv-nest7", LayerName.ORCHESTRATION, "node_exited", {"node": "verify"}))

    # start_observation called twice (node + tool)
    assert mock_lf.start_observation.call_count == 2
    # end() called on both spans
    assert mock_node_span.end.called
    assert mock_tool_span.end.called


# ---------------------------------------------------------------------------
# Test 8 — emitter.emit propagates to push_event
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_emitter_emit_propagates_to_push_event():
    """get_emitter().emit(...) must call push_event exactly once with matching event."""
    from app.observability import get_emitter
    from app.observability.sse_publisher import _reset_state_for_testing

    _reset_state_for_testing()

    with patch("app.observability.layer_event_emitter.push_event") as mock_push:
        emitter = get_emitter()
        emitter.emit(
            conversation_id="conv-em8",
            layer=LayerName.SKILLS,
            event_type="skill_loaded",
            payload={"skill": "refund_policy"},
        )

    mock_push.assert_called_once()
    called_event: LayerEvent = mock_push.call_args[0][0]
    assert called_event.conversation_id == "conv-em8"
    assert called_event.layer == LayerName.SKILLS
    assert called_event.event_type == "skill_loaded"
    assert called_event.payload["skill"] == "refund_policy"


# ---------------------------------------------------------------------------
# Test 9 — EVENT_TYPE_CATALOG uniqueness + valid LayerName values
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_event_type_catalog_unique():
    """Catalog has no duplicates (frozenset guarantees it) and all layers are valid."""
    # frozenset cannot contain duplicates, but verify via len comparison
    catalog_list = list(EVENT_TYPE_CATALOG)
    assert len(catalog_list) == len(set(catalog_list)), "Duplicates found in EVENT_TYPE_CATALOG"

    valid_layer_names = set(LayerName)
    for layer, _event_type in EVENT_TYPE_CATALOG:
        assert layer in valid_layer_names, f"{layer!r} is not a valid LayerName"

    # Spot-check expected count: 27 tuples per spec
    assert len(EVENT_TYPE_CATALOG) == 27
