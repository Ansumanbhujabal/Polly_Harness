# ADR-0003: MCP as the Tool Protocol Surface (in-process)

**Status:** Accepted
**Date:** 2026-06-18

## Context

The harness doc explicitly names the **Model Context Protocol (MCP)** as the structured-schema pattern for Layer 3 (Tool Interfaces). Honoring that is a senior-engineering signal. The question was *how* to integrate MCP — as a sidecar process, or in-process with FastAPI.

## Decision

Run the MCP server **in-process** with FastAPI, bound to the FastAPI `lifespan` hook. Stdio transport. Same Python interpreter, same `asyncio` event loop.

The graph's hot path does NOT route through MCP — `app/graph/nodes/*` calls `app.tools.executor.run_tool(...)` directly. MCP exists for protocol compliance and external client connectivity (e.g., Claude Desktop reading the same tool list).

## Consequences

**Why in-process:**
- No IPC overhead, no boot-order races between FastAPI and MCP — both reach ready state inside a single `lifespan.__aenter__`.
- HF Spaces deploys a single Docker container; a sidecar would require either docker-compose (not supported in Spaces single-container mode) or a more complex base image.
- Tool registration is one async loop: `for tool in TOOLS: server.add_tool(...)`. The reviewer sees the same 8 tools in both `app.tools.TOOLS` and the MCP `inputSchema` JSON.

**What we gave up:** Process isolation between FastAPI request handling and the MCP transport. In a production deployment, a noisy MCP client could starve the FastAPI worker; the mitigation lives in the executor's structured timeout + retry envelope.

**Verification:** `tests/test_mcp_server.py::test_mcp_lifespan_task_cancels_on_exit` enforces the ≤ 2 s boot sentinel. The 8 tool cards under `app/tools/tool_cards/` are loaded into the MCP `description` field — the protocol surface is human-readable, not just schema-blob.
