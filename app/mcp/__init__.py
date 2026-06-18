"""MCP layer — in-process Model Context Protocol server.

Exports
-------
    build_mcp_server  — construct + register all 8 harness tools.
    mcp_lifespan_task — async context manager for FastAPI lifespan binding.
"""

from app.mcp.server import build_mcp_server, mcp_lifespan_task

__all__ = ["build_mcp_server", "mcp_lifespan_task"]
