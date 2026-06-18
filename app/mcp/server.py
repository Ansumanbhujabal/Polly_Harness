"""MCP Server — Layer 3 cross-cut protocol surface.

Exposes the same 8 typed tools from app.tools.TOOLS via the Model Context
Protocol (MCP) stdio transport.  Runs in-process with FastAPI — not as a
sidecar — and is bound to the FastAPI lifespan via mcp_lifespan_task().

The graph (L6) does NOT call tools through MCP; it uses
app.tools.executor.run_tool() directly. MCP exists for protocol compliance
and external connectivity (Claude Desktop, other harnesses).

Public API
----------
    build_mcp_server() -> FastMCP
    async mcp_lifespan_task() -> AsyncIterator[None]  (async context manager)
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from pydantic import create_model

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.tools import Tool
from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase, FuncMetadata

from app.domain.models import LayerName
from app.observability.layer_event_emitter import get_emitter
from app.observability.structured_logger import get_logger
from app.tools import TOOLS
from app.tools.base import BaseTool

logger = get_logger(__name__)

# Path to tool card Markdown files.
_TOOL_CARDS_DIR = Path(__file__).resolve().parent.parent / "tools" / "tool_cards"

# The single in-process FastMCP server instance (created by build_mcp_server).
_server: FastMCP | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_tool_card(tool_name: str) -> str | None:
    """Return the contents of the tool card Markdown for *tool_name*, or None."""
    card_path = _TOOL_CARDS_DIR / f"{tool_name}.md"
    if card_path.exists():
        return card_path.read_text(encoding="utf-8")
    return None


def _build_arg_model(input_schema: dict[str, Any]) -> type:
    """Create a dynamic Pydantic model that mirrors the tool's Input JSON schema.

    Used as FuncMetadata.arg_model so that FastMCP's arg-validation path
    correctly unpacks the incoming payload dict into keyword arguments that
    the handler closure can receive.

    Field types are deliberately loose (Optional[Any]) because strict type
    coercion is already handled by tool.Input(**kwargs) inside the handler.
    """
    props = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))
    fields: dict[str, Any] = {}
    for name in props:
        if name in required:
            fields[name] = (Any, ...)
        else:
            fields[name] = (Optional[Any], None)  # type: ignore[assignment]

    return create_model("_DynArgModel", __base__=ArgModelBase, **fields)


def _make_handler(tool: BaseTool):  # type: ignore[return]
    """Return an async handler closure that delegates to *tool.run()*."""

    async def _handler(**kwargs: Any) -> dict[str, Any]:
        inp = tool.Input(**kwargs)
        output = await tool.run(inp)
        return output.model_dump()

    _handler.__name__ = f"_mcp_handler_{tool.name}"
    return _handler


def _register_tool(server: FastMCP, tool: BaseTool) -> None:
    """Register a single harness tool with the MCP server.

    Steps:
    1. Resolve description from tool card (if present) else inline description.
    2. Build a dynamic arg model from the Pydantic Input JSON schema.
    3. Create a custom FuncMetadata so FastMCP validates + unpacks args correctly.
    4. Construct the MCP Tool object with the correct name, description, and schema.
    5. Inject it into the server's internal tool manager.
    6. Emit L3_TOOLS/mcp_tool_registered.
    """
    # 1. Description
    description = _load_tool_card(tool.name) or tool.description

    # 2. Input schema from Pydantic model
    input_schema = tool.Input.model_json_schema()

    # 3. Dynamic arg model + FuncMetadata
    arg_model = _build_arg_model(input_schema)
    fn_meta = FuncMetadata(arg_model=arg_model)

    # 4. Handler closure
    handler = _make_handler(tool)

    # 5. Build Tool — use from_function to satisfy Pydantic validation, then
    #    override fn, fn_metadata, is_async, and parameters (the raw schema used
    #    as inputSchema in the MCP protocol surface).
    base = Tool.from_function(handler, name=tool.name, description=description)
    mcp_tool = base.model_copy(
        update={
            "fn": handler,
            "fn_metadata": fn_meta,
            "is_async": True,
            "parameters": input_schema,
        }
    )

    # Inject directly into the tool manager's internal registry
    server._tool_manager._tools[tool.name] = mcp_tool

    # 6. Emit event
    get_emitter().emit(
        conversation_id="system",
        layer=LayerName.TOOLS,
        event_type="mcp_tool_registered",
        payload={"tool_name": tool.name},
    )
    logger.debug("mcp_tool_registered", extra={"tool_name": tool.name})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_mcp_server() -> FastMCP:
    """Construct an MCP server, register all 8 harness tools, and return it.

    Iterates app.tools.TOOLS in order; emits one mcp_tool_registered event
    per tool.  Each tool's description is sourced from its tool card Markdown
    file (if present) so that the richer human-readable contract is exposed on
    the protocol surface.

    Returns
    -------
    FastMCP
        A fully configured in-process MCP server with all 8 tools registered.
    """
    global _server

    server = FastMCP("refund-harness")

    for tool in TOOLS:
        _register_tool(server, tool)

    _server = server
    logger.info("mcp_server_built", extra={"tool_count": len(TOOLS)})
    return server


@asynccontextmanager
async def mcp_lifespan_task() -> AsyncIterator[None]:
    """Async context manager that manages the MCP server's stdio lifecycle.

    On ``__aenter__``: builds the MCP server (if not already built) and
    spawns its stdio run loop as a named background asyncio.Task called
    'mcp-server'.  Returns immediately — the task runs concurrently.

    On ``__aexit__``: cancels the background task, awaits its completion,
    and swallows the resulting CancelledError so FastAPI lifespan teardown
    continues cleanly.

    Usage (in FastAPI lifespan)::

        async with mcp_lifespan_task():
            yield  # app is running
    """
    server = build_mcp_server()

    # Spawn stdio loop as a background task.
    task = asyncio.get_event_loop().create_task(
        server.run_stdio_async(),
        name="mcp-server",
    )
    logger.info("mcp_lifespan_started")

    try:
        yield
    finally:
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        logger.info("mcp_lifespan_stopped")
