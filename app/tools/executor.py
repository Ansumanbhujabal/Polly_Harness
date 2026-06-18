"""L4 Sandbox Executor — timeout, retry, structured error envelope.

Every tool call in the harness goes through `run_tool()`. It:
  1. Validates input against the tool's Pydantic Input model.
  2. Runs the tool with asyncio.wait_for(timeout=settings.TOOL_TIMEOUT_SECONDS).
  3. On failure, retries with exponential backoff (2^attempt * 0.1 s) up to
     settings.TOOL_MAX_RETRIES times.
  4. Emits L3_TOOLS / L4_EXECUTION LayerEvents on every transition.
  5. Returns a structured envelope — exceptions NEVER escape this function.

Envelope schema:
  {
    "ok": bool,
    "output": dict | None,
    "error_code": str | None,
    "latency_ms": float,
    "retries": int,
  }
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.config import settings
from app.domain.models import LayerName
from app.observability.layer_event_emitter import get_emitter
from app.tools.base import BaseTool


async def run_tool(
    tool: BaseTool,
    payload: dict[str, Any],
    *,
    conversation_id: str = "unknown",
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
) -> dict[str, Any]:
    """Run a tool inside the L4 sandbox.

    Args:
        tool: The BaseTool instance to execute.
        payload: Raw dict that will be parsed into tool.Input.
        conversation_id: Correlation ID for event emission.
        timeout_seconds: Override for settings.TOOL_TIMEOUT_SECONDS.
        max_retries: Override for settings.TOOL_MAX_RETRIES.

    Returns:
        Envelope dict: {ok, output, error_code, latency_ms, retries}
    """
    emitter = get_emitter()
    _timeout = timeout_seconds if timeout_seconds is not None else settings.TOOL_TIMEOUT_SECONDS
    _max_retries = max_retries if max_retries is not None else settings.TOOL_MAX_RETRIES

    emitter.emit(
        conversation_id=conversation_id,
        layer=LayerName.TOOLS,
        event_type="tool_invoked",
        payload={"tool": tool.name, "input": payload},
    )

    start = time.monotonic()
    last_error: Exception | None = None
    attempt = 0

    while attempt <= _max_retries:
        try:
            parsed_input = tool.parse_input(payload)
            output = await asyncio.wait_for(tool.run(parsed_input), timeout=_timeout)
            latency_ms = (time.monotonic() - start) * 1000

            emitter.emit(
                conversation_id=conversation_id,
                layer=LayerName.TOOLS,
                event_type="tool_succeeded",
                payload={
                    "tool": tool.name,
                    "latency_ms": latency_ms,
                    "retries": attempt,
                    "output_type": type(output).__name__,
                },
            )

            return {
                "ok": True,
                "output": output.model_dump(),
                "error_code": None,
                "latency_ms": latency_ms,
                "retries": attempt,
            }

        except asyncio.TimeoutError as exc:
            last_error = exc
            error_msg = f"timeout after {_timeout}s"
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            error_msg = str(exc)

        if attempt < _max_retries:
            emitter.emit(
                conversation_id=conversation_id,
                layer=LayerName.EXECUTION,
                event_type="tool_retry",
                payload={
                    "tool": tool.name,
                    "attempt": attempt + 1,
                    "error": error_msg,
                },
            )
            # Exponential backoff: 0.1s, 0.2s, 0.4s, …
            backoff = (2**attempt) * 0.05
            await asyncio.sleep(backoff)

        attempt += 1

    latency_ms = (time.monotonic() - start) * 1000
    final_error = str(last_error) if last_error else "unknown error"

    emitter.emit(
        conversation_id=conversation_id,
        layer=LayerName.EXECUTION,
        event_type="tool_failed",
        payload={
            "tool": tool.name,
            "error": final_error,
            "retries": _max_retries,
            "latency_ms": latency_ms,
        },
    )

    return {
        "ok": False,
        "output": None,
        "error_code": final_error,
        "latency_ms": latency_ms,
        "retries": _max_retries,
    }
