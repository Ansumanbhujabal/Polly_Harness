"""Tests for L2: Context Delivery & Management layer.

Tests are written first (RED phase) per TDD protocol.
All Qdrant calls are mocked — no real network.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.domain.models import Customer, CustomerTier, Item, LayerName, Order, OrderStatus, PolicyClause


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_customer(
    email: str = "jane.doe@example.com",
    phone: str = "+91-98765-43210",
) -> Customer:
    return Customer(
        customer_id="CUST-TEST",
        name="Jane Doe",
        email=email,
        phone=phone,
        tier=CustomerTier.STANDARD,
    )


def _make_order() -> Order:
    return Order(
        order_id="ORD-001",
        customer_id="CUST-TEST",
        items=[Item(sku="SKU-1", name="Widget", category="electronics", qty=1, unit_price_usd=99.99)],
        total_usd=99.99,
        purchase_date="2026-06-01",
        status=OrderStatus.DELIVERED,
    )


def _fake_qdrant_search_result(clause_ids: list[str]) -> list[Any]:
    """Build minimal Qdrant ScoredPoint-like objects for mocking."""
    results = []
    for i, cid in enumerate(clause_ids):
        point = MagicMock()
        point.score = 0.9 - i * 0.05
        point.payload = {
            "clause_id": cid,
            "section_title": "Section 1",
            "text": f"Clause text for {cid}",
        }
        results.append(point)
    return results


def _long_messages(num_non_system: int = 10) -> list[dict[str, str]]:
    """Build a message list that will exceed token thresholds when long enough."""
    msgs: list[dict[str, str]] = [
        {"role": "system", "content": "You are a helpful refund agent."}
    ]
    for i in range(num_non_system):
        role = "user" if i % 2 == 0 else "assistant"
        # Make content long enough to accumulate tokens
        msgs.append({"role": role, "content": f"Message {i}: " + ("This is a long sentence. " * 30)})
    return msgs


# ===========================================================================
# Test 1 — Retriever raises helpful error when collection missing
# ===========================================================================

@pytest.mark.unit
def test_retriever_raises_helpful_error_when_collection_missing(mocker):
    """Qdrant reports collection absent → RuntimeError with exact message."""
    # Reset the singleton before this test
    import app.context.retriever as ret_module
    ret_module._retriever_singleton = None

    mock_client_cls = mocker.patch("app.context.retriever.QdrantClient")
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    # Simulate collection not found
    mock_client.get_collection.side_effect = Exception("Not found")

    mocker.patch("app.context.retriever.TextEmbedding")

    with pytest.raises(RuntimeError, match=r"Run `make seed` first"):
        from app.context import get_retriever
        get_retriever()

    # Reset singleton after test
    ret_module._retriever_singleton = None


# ===========================================================================
# Test 2 — Retriever returns top_k clauses with POLICY-NNN ids
# ===========================================================================

@pytest.mark.unit
def test_retriever_returns_top_k_clauses_with_ids(mocker):
    """Replayed Qdrant response → list[PolicyClause] with correct POLICY-NNN ids."""
    import app.context.retriever as ret_module
    ret_module._retriever_singleton = None

    clause_ids = ["POLICY-001", "POLICY-005", "POLICY-008"]
    fake_results = _fake_qdrant_search_result(clause_ids)

    mock_client_cls = mocker.patch("app.context.retriever.QdrantClient")
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.get_collection.return_value = MagicMock()  # collection exists
    mock_client.search.return_value = fake_results
    mock_query_resp = MagicMock()
    mock_query_resp.points = fake_results
    mock_client.query_points.return_value = mock_query_resp

    mock_embed_cls = mocker.patch("app.context.retriever.TextEmbedding")
    mock_embed = MagicMock()
    mock_embed_cls.return_value = mock_embed
    mock_embed.embed.return_value = iter([[0.1] * 384])

    retriever = ret_module.PolicyRetriever()
    clauses = asyncio.run(retriever.search("return window", top_k=3))

    assert isinstance(clauses, list)
    assert len(clauses) == 3
    for clause, cid in zip(clauses, clause_ids):
        assert isinstance(clause, PolicyClause)
        assert clause.clause_id == cid
        assert clause.clause_id.startswith("POLICY-")

    ret_module._retriever_singleton = None


# ===========================================================================
# Test 3 — Retriever emits L2_CONTEXT / retrieval_performed event on success
# ===========================================================================

@pytest.mark.unit
def test_retriever_emits_event_on_success(mocker):
    """After successful search → exactly one LayerEvent with correct fields."""
    import app.context.retriever as ret_module
    ret_module._retriever_singleton = None

    clause_ids = ["POLICY-002", "POLICY-003"]
    fake_results = _fake_qdrant_search_result(clause_ids)

    mock_client_cls = mocker.patch("app.context.retriever.QdrantClient")
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.get_collection.return_value = MagicMock()
    mock_client.search.return_value = fake_results
    mock_query_resp = MagicMock()
    mock_query_resp.points = fake_results
    mock_client.query_points.return_value = mock_query_resp

    mock_embed_cls = mocker.patch("app.context.retriever.TextEmbedding")
    mock_embed = MagicMock()
    mock_embed_cls.return_value = mock_embed
    mock_embed.embed.return_value = iter([[0.1] * 384])

    captured: list[Any] = []

    from app.observability import get_emitter
    emitter = get_emitter()
    emitter.subscribe(captured.append)

    try:
        retriever = ret_module.PolicyRetriever()
        clauses = asyncio.run(retriever.search("damage clause", top_k=2))

        events = [e for e in captured if e.event_type == "retrieval_performed"]
        assert len(events) == 1
        ev = events[0]
        assert ev.layer == LayerName.CONTEXT
        assert ev.payload["returned_clauses"] == len(clauses)
        assert "query" in ev.payload
        assert "top_k" in ev.payload
        assert "latency_ms" in ev.payload
    finally:
        emitter.unsubscribe(captured.append)
        ret_module._retriever_singleton = None


# ===========================================================================
# Test 4 — build_customer_context redacts email
# ===========================================================================

@pytest.mark.unit
def test_build_customer_context_redacts_email():
    from app.context import build_customer_context

    customer = _make_customer(email="jane.doe@example.com")
    ctx = build_customer_context(customer, order=None)

    # Must contain redacted form
    assert "j***@example.com" in ctx.values() or any(
        "j***@example.com" in str(v) for v in ctx.values()
    )
    # Raw email must NOT appear anywhere in the dict
    assert "jane.doe@example.com" not in str(ctx)


# ===========================================================================
# Test 5 — build_customer_context redacts phone
# ===========================================================================

@pytest.mark.unit
def test_build_customer_context_redacts_phone():
    from app.context import build_customer_context

    customer = _make_customer(phone="+91-98765-43210")
    ctx = build_customer_context(customer, order=None)

    # Must contain last-4 form
    assert any("3210" in str(v) for v in ctx.values())
    assert any("***-3210" in str(v) for v in ctx.values())
    # Raw phone must NOT appear
    assert "+91-98765-43210" not in str(ctx)


# ===========================================================================
# Test 6 — build_customer_context omits order keys when order is None
# ===========================================================================

@pytest.mark.unit
def test_build_customer_context_omits_order_when_none():
    from app.context import build_customer_context

    customer = _make_customer()
    ctx = build_customer_context(customer, order=None)

    forbidden_keys = {"order_id", "status", "items"}
    assert forbidden_keys.isdisjoint(ctx.keys()), (
        f"Found order keys in ctx when order=None: {forbidden_keys & ctx.keys()}"
    )


# ===========================================================================
# Test 7 — compact_messages no-op when below threshold
# ===========================================================================

@pytest.mark.unit
def test_compact_messages_noop_below_threshold(mocker):
    """Short message list → identical object returned, no LLM call."""
    from app.context import compact_messages

    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]

    mock_llm = mocker.patch("app.context.compactor._call_llm_summarize")

    result = compact_messages(messages, max_tokens=4000)

    assert result is messages, "Should return the exact same list object"
    mock_llm.assert_not_called()


# ===========================================================================
# Test 8 — compact_messages preserves system + last 3 turns
# ===========================================================================

@pytest.mark.unit
def test_compact_messages_preserves_system_and_last_three_turns(mocker):
    """Long message list → system message and last 3 non-system messages survive verbatim."""
    from app.context import compact_messages

    mocker.patch(
        "app.context.compactor._call_llm_summarize",
        return_value="Summary of middle conversation.",
    )

    messages = _long_messages(num_non_system=10)
    system_msg = messages[0]
    last_three = messages[-3:]

    # ~2090 tokens original, 1000 threshold → compaction triggers
    result = compact_messages(messages, max_tokens=1000)

    # System message preserved
    assert any(m["role"] == "system" for m in result), "System message missing"
    sys_msgs = [m for m in result if m["role"] == "system"]
    assert sys_msgs[0]["content"] == system_msg["content"]

    # Last 3 non-system messages present verbatim at the tail
    non_sys_result = [m for m in result if m["role"] != "system"]
    assert len(non_sys_result) >= 3
    # The last 3 non-system messages of result should be last 3 of input
    for expected, actual in zip(last_three, non_sys_result[-3:]):
        assert actual["content"] == expected["content"]
        assert actual["role"] == expected["role"]


# ===========================================================================
# Test 9 — compact_messages emits compaction_triggered event with token delta
# ===========================================================================

@pytest.mark.unit
def test_compact_messages_emits_event_with_token_delta(mocker):
    """After compaction → one compaction_triggered event; pre_tokens > post_tokens."""
    from app.context import compact_messages

    mocker.patch(
        "app.context.compactor._call_llm_summarize",
        return_value="Brief summary.",
    )

    captured: list[Any] = []
    from app.observability import get_emitter
    emitter = get_emitter()
    emitter.subscribe(captured.append)

    try:
        messages = _long_messages(num_non_system=10)
        # Original ~2090 tokens, compacted ~585; threshold 1000 triggers compaction
        compact_messages(messages, max_tokens=1000)

        events = [e for e in captured if e.event_type == "compaction_triggered"]
        assert len(events) == 1
        ev = events[0]
        assert ev.layer == LayerName.CONTEXT
        assert ev.payload["pre_tokens"] > ev.payload["post_tokens"]
    finally:
        emitter.unsubscribe(captured.append)


# ===========================================================================
# Test 10 — compact_messages idempotent when already compact
# ===========================================================================

@pytest.mark.unit
def test_compact_messages_idempotent_when_already_compact(mocker):
    """compact twice → second call is a no-op (no second LLM call, no second event)."""
    from app.context import compact_messages

    mock_llm = mocker.patch(
        "app.context.compactor._call_llm_summarize",
        return_value="Brief summary.",
    )

    captured: list[Any] = []
    from app.observability import get_emitter
    emitter = get_emitter()
    emitter.subscribe(captured.append)

    try:
        messages = _long_messages(num_non_system=10)
        # Original ~2090 tokens, compacted ~585; threshold 1000 triggers first compaction
        # but leaves the compacted result below threshold → second call is a no-op.

        # First compaction (triggers summarisation)
        first_result = compact_messages(messages, max_tokens=1000)
        call_count_after_first = mock_llm.call_count
        events_after_first = [e for e in captured if e.event_type == "compaction_triggered"]

        # Second compaction on the already-compacted result (same threshold)
        second_result = compact_messages(first_result, max_tokens=1000)

        events_after_second = [e for e in captured if e.event_type == "compaction_triggered"]

        # No new LLM call
        assert mock_llm.call_count == call_count_after_first, "LLM was called again on second compact"

        # No new event
        assert len(events_after_second) == len(events_after_first), "Second compact emitted extra event"

        # Second result is identical object (no-op)
        assert second_result is first_result
    finally:
        emitter.unsubscribe(captured.append)
