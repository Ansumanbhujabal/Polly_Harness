# SPEC: MCP Server

**Layer:** Cross-cutting (the Layer-3 protocol implementation)
**Owner:** `app/mcp/`

The MCP Server layer is the harness doc's explicit nod to structured tool protocols. It exposes the same 8 typed tools as `app.tools.TOOLS` via the Model Context Protocol stdio transport. The protocol surface exists so external clients (Claude Desktop, other agentic harnesses) can drive the refund agent through a standard interface. It runs **in-process** with FastAPI — not as a sidecar — bound to the FastAPI lifespan.

The graph (L6) does NOT call tools through MCP. The graph calls `app.tools.executor.run_tool(...)` directly. MCP exists for protocol compliance and external connectivity, not for the hot path.

## Contract

```python
from app.mcp import build_mcp_server, mcp_lifespan_task
```

- `build_mcp_server() -> mcp.Server` — constructs an MCP Server object, iterates `app.tools.TOOLS`, registers each tool via `server.add_tool(name, description, input_schema, handler)`. Returns the configured server.
- `async mcp_lifespan_task() -> AsyncIterator[None]` — an async context manager. On `__aenter__`: spawn the MCP server's stdio loop as a backgrounded `asyncio.Task` (named `mcp-server`). On `__aexit__`: cancel the task, await its cancellation, swallow `CancelledError`. The FastAPI `lifespan` (owned by `SPEC_EXECUTION`) awaits this in its boot sequence.

## Behaviors

- **In-process, same Python interpreter** as the FastAPI app. The MCP server's stdio handlers run on the same `asyncio` event loop. This eliminates IPC and start-order complexity that a sidecar would impose.
- **Tool registration** — for each `tool in app.tools.TOOLS`:
  - `name = tool.name`
  - `description` — the contents of `app/tools/tool_cards/<tool.name>.md` if present, else `tool.description` (the inline one). The tool card is the longer, human-readable contract the protocol exposes.
  - `input_schema = tool.Input.model_json_schema()` — Pydantic 2's JSON Schema export.
  - `handler` — an async wrapper that takes the validated input as a `dict`, constructs `tool.Input(**payload)`, calls `await tool.run(input)`, returns the result as a `dict`. The wrapper goes through the same `run_tool` executor envelope as the graph, so the structured-error contract is uniform across both call paths.
- **Lifespan cancellation safety** — on FastAPI shutdown, `mcp_lifespan_task` cancels the MCP task and awaits it. Pending tool calls receive `CancelledError`; the protocol layer's response is "connection closed."
- **Boot timing** — the server must be ready (tools registered + listening) within 2 seconds of `mcp_lifespan_task.__aenter__`. Test 4 enforces this with a timed assertion.

## Events emitted

- `L3_TOOLS / mcp_tool_registered` — payload: `{tool_name: str}` — one emit per tool registered at startup. Used by the dashboard's "MCP tools available" panel (informational).

## Files

```
app/mcp/__init__.py        # exports build_mcp_server, mcp_lifespan_task
app/mcp/server.py          # build_mcp_server() + mcp_lifespan_task() + handler wrapper
```

## Dependencies

- `app.tools` — `TOOLS`, `BaseTool`, the executor envelope
- `app.observability` — `get_emitter`, `get_logger`
- `mcp` (the MCP Python SDK, already in pyproject)
- `asyncio`

Out of scope: an MCP CLIENT (we're the server). Authentication / authorization on the MCP transport (single-user demo). Multi-transport (we ship stdio only).

## Tests

`tests/test_mcp_server.py` — minimum tests:

1. `test_build_mcp_server_registers_all_eight_tools` — call `build_mcp_server()`; assert 8 tools registered, names match `[t.name for t in TOOLS]`.
2. `test_tool_input_schema_exposes_required_fields` — for a representative tool (`lookup_customer`), assert the registered `input_schema` contains the required fields per its Pydantic Input model.
3. `test_tool_description_includes_tool_card_content` — verify a known tool card's first paragraph appears in the registered `description`.
4. `test_mcp_lifespan_task_cancels_on_exit` — enter the lifespan context, capture the task, exit; assert task is `done()` AND `cancelled()` within 1 second. Also assert the enter completed within 2 seconds (boot timing).
5. `test_mcp_tool_registered_event_emitted_per_tool` — capture LayerEvents during `build_mcp_server`; assert exactly 8 `mcp_tool_registered` events with the matching `tool_name` payloads.

## Done criteria

- [ ] Both files (`app/mcp/__init__.py`, `app/mcp/server.py`) exist.
- [ ] All 5 tests pass under `pytest -m "unit or integration" tests/test_mcp_server.py`.
- [ ] Test 4's timing assertion (boot ≤ 2 s) passes on a developer machine; documented as a regression sentinel.
- [ ] No tool import from `app.graph`, `app.api`, or `app.verification` (one-way dependency — MCP wraps Tools, not the other way around).
- [ ] `mypy --strict app/mcp/` passes (best-effort).
