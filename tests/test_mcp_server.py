"""Tests for B6 — MCP Server (Layer 3 cross-cut protocol).

TDD order: write tests first (RED), implement (GREEN).

Test contract (from SPEC_MCP_SERVER.md):
  1. build_mcp_server() registers all 8 tools by name.
  2. A representative tool exposes required Pydantic Input fields in inputSchema.
  3. The tool card content appears in the registered description.
  4. mcp_lifespan_task() boots in ≤ 2 s; on __aexit__ the task is done + cancelled.
  5. Exactly 8 mcp_tool_registered LayerEvents are emitted, one per tool.

Markers:
  unit — fast, no real I/O
  integration — may involve asyncio task lifecycle
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import patch

import pytest

from app.domain.models import LayerName
from app.tools import TOOLS


# ---------------------------------------------------------------------------
# Test 1 — build_mcp_server registers all 8 tools
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_mcp_server_registers_all_eight_tools() -> None:
    """build_mcp_server() must register exactly the 8 tools in app.tools.TOOLS."""
    from app.mcp.server import build_mcp_server

    server = build_mcp_server()

    # FastMCP exposes list_tools() as a coroutine
    tools = asyncio.get_event_loop().run_until_complete(server.list_tools())

    registered_names = {t.name for t in tools}
    expected_names = {t.name for t in TOOLS}

    assert len(registered_names) == 8, f"Expected 8 tools, got {len(registered_names)}: {registered_names}"
    assert registered_names == expected_names, (
        f"Registered tool names mismatch.\n"
        f"  Expected: {sorted(expected_names)}\n"
        f"  Got:      {sorted(registered_names)}"
    )


# ---------------------------------------------------------------------------
# Test 2 — input_schema exposes required fields for lookup_customer
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_tool_input_schema_exposes_required_fields() -> None:
    """The MCP inputSchema for lookup_customer must reflect the Pydantic Input model.

    LookupCustomer.Input has optional customer_id and email.  The JSON Schema
    properties key must contain both field names.
    """
    from app.mcp.server import build_mcp_server
    from app.tools.customer_tools import LookupCustomer

    server = build_mcp_server()
    tools = asyncio.get_event_loop().run_until_complete(server.list_tools())

    tool_map = {t.name: t for t in tools}
    assert "lookup_customer" in tool_map, "lookup_customer not registered"

    mcp_tool = tool_map["lookup_customer"]
    schema: dict[str, Any] = mcp_tool.inputSchema

    # The schema must have a 'properties' key
    assert "properties" in schema, f"inputSchema missing 'properties': {schema}"

    # Verify the fields from LookupCustomer.Input appear in the schema
    lc_schema = LookupCustomer.Input.model_json_schema()
    expected_fields = set(lc_schema.get("properties", {}).keys())
    registered_fields = set(schema["properties"].keys())

    # All expected fields must be a subset of registered fields
    assert expected_fields <= registered_fields, (
        f"Missing fields in inputSchema.\n"
        f"  Expected at minimum: {sorted(expected_fields)}\n"
        f"  Got: {sorted(registered_fields)}"
    )


# ---------------------------------------------------------------------------
# Test 3 — tool card content appears in registered description
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_tool_description_includes_tool_card_content() -> None:
    """The MCP description for lookup_customer must include its tool card's first paragraph."""
    from app.mcp.server import build_mcp_server

    server = build_mcp_server()
    tools = asyncio.get_event_loop().run_until_complete(server.list_tools())

    tool_map = {t.name: t for t in tools}
    assert "lookup_customer" in tool_map

    mcp_tool = tool_map["lookup_customer"]
    description: str = mcp_tool.description or ""

    # The first substantive paragraph of the tool card
    expected_fragment = "Retrieve a customer record from the CRM"
    assert expected_fragment in description, (
        f"Tool card content not found in description.\n"
        f"  Expected fragment: {expected_fragment!r}\n"
        f"  Got description:   {description!r}"
    )


# ---------------------------------------------------------------------------
# Test 4 — lifespan task boots quickly and cancels cleanly
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_mcp_lifespan_task_cancels_on_exit() -> None:
    """mcp_lifespan_task:
    - __aenter__ completes within 2 seconds (boot timing sentinel).
    - On __aexit__ the background task is done() AND cancelled() within 1 second.
    """
    from app.mcp.server import mcp_lifespan_task

    t0 = time.monotonic()
    ctx = mcp_lifespan_task()

    # Enter — must complete fast
    await ctx.__aenter__()
    boot_elapsed = time.monotonic() - t0

    assert boot_elapsed < 2.0, (
        f"Boot took too long: {boot_elapsed:.3f}s (limit 2s)"
    )

    # Capture the running task — it was registered by __aenter__
    running_tasks = asyncio.all_tasks()
    mcp_tasks = [t for t in running_tasks if "mcp-server" in (t.get_name() or "")]
    assert len(mcp_tasks) == 1, (
        f"Expected exactly 1 task named 'mcp-server', found: {[t.get_name() for t in mcp_tasks]}"
    )
    bg_task = mcp_tasks[0]

    # Exit — task must be cancelled
    await ctx.__aexit__(None, None, None)

    # Give asyncio a moment to propagate cancellation
    await asyncio.sleep(0.05)

    assert bg_task.done(), "Background task is not done after __aexit__"
    assert bg_task.cancelled(), "Background task was not cancelled (expected CancelledError)"


# ---------------------------------------------------------------------------
# Test 5 — exactly 8 mcp_tool_registered events emitted
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_mcp_tool_registered_event_emitted_per_tool() -> None:
    """build_mcp_server() must emit exactly 8 L3_TOOLS/mcp_tool_registered events,
    one per tool, with matching tool_name payloads.
    """
    from app.mcp.server import build_mcp_server
    from app.observability.layer_event_emitter import get_emitter

    captured_events: list[Any] = []

    def _capture_sink(event: Any) -> None:
        if event.event_type == "mcp_tool_registered":
            captured_events.append(event)

    emitter = get_emitter()
    emitter.subscribe(_capture_sink)

    try:
        build_mcp_server()
    finally:
        emitter.unsubscribe(_capture_sink)

    assert len(captured_events) == 8, (
        f"Expected 8 mcp_tool_registered events, got {len(captured_events)}: "
        f"{[e.payload for e in captured_events]}"
    )

    # All events are L3_TOOLS layer
    for event in captured_events:
        assert event.layer == LayerName.TOOLS, (
            f"Event layer mismatch: expected TOOLS, got {event.layer}"
        )

    # Registered tool names match TOOLS
    emitted_names = {e.payload["tool_name"] for e in captured_events}
    expected_names = {t.name for t in TOOLS}
    assert emitted_names == expected_names, (
        f"Emitted tool names mismatch.\n"
        f"  Expected: {sorted(expected_names)}\n"
        f"  Got:      {sorted(emitted_names)}"
    )
