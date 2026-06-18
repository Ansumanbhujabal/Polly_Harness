# SPEC: Observability

**Layer:** Cross-cutting (powers L9 + the admin dashboard + the dynamic architecture diagram)
**Owner:** `app/observability/`

The Observability layer is the single fan-out point for every `LayerEvent` the system emits. It owns the Langfuse client (lazy singleton, fails open), the in-memory SSE ring buffer (replay-on-reconnect), the structured logger (already on disk), and the public event-type catalog that all other layers emit against. The existing `LayerEventEmitter.emit()` on disk is extended — not replaced — to call into the new fan-out.

The event-type catalog in §"Event type catalog" below is the **frozen registry**: no spec may emit an event whose `(layer, event_type)` tuple is not on the list. A unit test asserts the registry has no duplicates and matches the code constant in `event_types.py`.

## Contract

```python
from app.observability import (
    get_emitter,
    get_logger,
    get_langfuse_client,
    sse_event_stream,
    push_event,
)
```

- `get_emitter() -> LayerEventEmitter` — already on disk; emit calls now propagate through `push_event`.
- `get_logger(name: str | None = None) -> structlog.BoundLogger` — already on disk.
- `get_langfuse_client() -> Langfuse | None` — lazy singleton. Returns `None` if `settings.langfuse_configured` is False. Reused for the process lifetime; closed by lifespan shutdown.
- `sse_event_stream(conversation_id: str | None = None) -> AsyncIterator[ServerSentEvent]` — async generator yielding `sse_starlette.ServerSentEvent` objects. If `conversation_id` is None: emits all events. If set: emits only events whose `event.conversation_id == conversation_id`. Replays the ring buffer first, then tails new events live.
- `push_event(event: LayerEvent) -> None` — the fan-out. Routes to (a) the SSE ring buffer, (b) the Langfuse client (if configured), (c) the structured logger. Never raises; Langfuse failures are caught, logged WARN, and swallowed.

## Behaviors

- **Existing `LayerEventEmitter.emit()`** is modified to call `push_event(event)` after constructing the `LayerEvent`. The emitter remains the only place where `LayerEvent` instances are created — `push_event` accepts them but does not construct them.
- **SSE ring buffer** — an in-memory `collections.deque(maxlen=500)` per conversation_id, plus a global deque (also maxlen=500) for unfiltered subscribers. Insertion is O(1); eviction is automatic on overflow.
- **SSE event stream replay-then-tail** — on subscriber connect, `sse_event_stream` first yields the current buffered events for the filter, then awaits an `asyncio.Event` that the publisher signals on every new push. The generator must remain valid across HTTP/2 long-poll lifetimes.
- **Langfuse client** — created lazily on first call to `get_langfuse_client()` using `settings.LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`. Span nesting follows event chronology + `LayerName` — the publisher maintains a per-`conversation_id` stack of open spans keyed by layer; entering a new layer opens a child span; exiting closes the matching span. (The exit signal is the symmetric pair-event — e.g., `node_exited` closes the `node_entered` span.)
- **Langfuse fail-open** — every Langfuse API call is wrapped in try/except. On exception: log WARN with the original event payload + exception type. Never raise — `push_event` must remain side-effect-only.

## Event type catalog

The frozen registry. Every spec listed below MUST emit only events from this table; no other `(layer, event_type)` tuple is allowed without first amending this spec.

| Layer | event_type | Owning spec |
|---|---|---|
| `L1_INSTRUCTIONS` | `prompt_loaded` | SPEC_INSTRUCTIONS |
| `L2_CONTEXT` | `retrieval_performed` | SPEC_CONTEXT |
| `L2_CONTEXT` | `compaction_triggered` | SPEC_CONTEXT |
| `L3_TOOLS` | `tool_invoked` | SPEC_TOOLS |
| `L3_TOOLS` | `tool_succeeded` | SPEC_TOOLS |
| `L3_TOOLS` | `mcp_tool_registered` | SPEC_MCP_SERVER |
| `L4_EXECUTION` | `tool_retry` | SPEC_TOOLS (executor) |
| `L4_EXECUTION` | `tool_failed` | SPEC_TOOLS (executor) |
| `L4_EXECUTION` | `boot_step_completed` | SPEC_EXECUTION |
| `L5_STATE` | `write_performed` | SPEC_STATE |
| `L5_STATE` | `migration_applied` | SPEC_STATE |
| `L6_ORCHESTRATION` | `node_entered` | SPEC_ORCHESTRATION |
| `L6_ORCHESTRATION` | `node_exited` | SPEC_ORCHESTRATION |
| `L6_ORCHESTRATION` | `interrupt_raised` | SPEC_ORCHESTRATION |
| `L7_SUBAGENTS` | `fraud_check_started` | SPEC_SUBAGENTS |
| `L7_SUBAGENTS` | `fraud_check_completed` | SPEC_SUBAGENTS |
| `L8_SKILLS` | `skill_loaded` | SPEC_SKILLS |
| `L8_SKILLS` | `skill_routed` | SPEC_SKILLS |
| `L9_VERIFICATION` | `check_started` | SPEC_VERIFICATION |
| `L9_VERIFICATION` | `check_passed` | SPEC_VERIFICATION |
| `L9_VERIFICATION` | `check_failed` | SPEC_VERIFICATION |
| `L9_VERIFICATION` | `pipeline_completed` | SPEC_VERIFICATION |
| `INCIDENT_LOOP` | `incident_written` | SPEC_INCIDENT_LOOP |
| `INCIDENT_LOOP` | `distillation_proposed` | SPEC_INCIDENT_LOOP |
| `CACHE` | `cache_hit` | (semantic cache, feature-flag OFF by default) |
| `CACHE` | `cache_miss` | (semantic cache) |
| `CACHE` | `cache_set` | (semantic cache) |

The catalog is also exported as a Python constant in `app/observability/event_types.py`:

```python
EVENT_TYPE_CATALOG: frozenset[tuple[LayerName, str]] = frozenset({
    (LayerName.INSTRUCTIONS, "prompt_loaded"),
    (LayerName.CONTEXT, "retrieval_performed"),
    # ... full enumeration ...
})
```

## Files

```
app/observability/__init__.py          # modified — adds push_event, sse_event_stream, get_langfuse_client exports
app/observability/event_types.py       # NEW — EVENT_TYPE_CATALOG frozen registry
app/observability/langfuse_client.py   # NEW — lazy singleton + span nesting
app/observability/sse_publisher.py     # NEW — ring buffer + sse_event_stream
app/observability/structured_logger.py # exists, unchanged
app/observability/layer_event_emitter.py # modified — emit() now calls push_event
```

## Dependencies

- `app.domain.models` — `LayerEvent`, `LayerName`
- `app.config` — `settings` for Langfuse config
- `langfuse` (cloud SDK)
- `sse_starlette` — `ServerSentEvent`
- `structlog` (already pulled in transitively or added here)

Out of scope: dashboard JS subscriber (owned by `SPEC_FRONTEND`), the SSE HTTP route (owned by `SPEC_API`).

## Tests

`tests/test_observability.py` — minimum tests:

1. `test_push_event_writes_to_ring_buffer` — push 3 events; assert `sse_event_stream` immediately yields all 3.
2. `test_sse_event_stream_replays_buffered_then_tails_live` — push 2 events, start streaming, push 1 more concurrently; assert stream yields 2 buffered then 1 live.
3. `test_sse_event_stream_filtered_by_conversation_id` — push events with `conv_id="a"` and `conv_id="b"`; subscribe with `conversation_id="a"`; assert only a's events stream.
4. `test_push_event_swallows_langfuse_failure_and_logs_warn` — use `respx` to make Langfuse return 500; assert `push_event` does NOT raise, asserts a WARN log line was emitted.
5. `test_get_langfuse_client_returns_none_when_unconfigured` — patch settings to clear keys; assert `get_langfuse_client()` returns `None`.
6. `test_ring_buffer_evicts_oldest_when_full` — push 501 events; assert the buffer holds the latest 500, the first is dropped.
7. `test_langfuse_span_nesting_matches_event_chronology` — push `node_entered` then `tool_invoked` then `tool_succeeded` then `node_exited`; assert the Langfuse mock saw a `tool_*` span nested inside a `node_*` span.
8. `test_emitter_emit_propagates_to_push_event` — patch `push_event`; call `get_emitter().emit(...)`; assert `push_event` was called once with the matching event.
9. `test_event_type_catalog_unique` — assert `len(EVENT_TYPE_CATALOG) == len(set(EVENT_TYPE_CATALOG))` and every tuple's first element is a valid `LayerName`.

Existing `tests/test_event_emitter.py` must continue to pass unchanged.

## Done criteria

- [ ] All 3 NEW module files exist (`event_types.py`, `langfuse_client.py`, `sse_publisher.py`).
- [ ] `__init__.py` and `layer_event_emitter.py` modified per spec; `__init__.py` exports the 5 named contract symbols.
- [ ] All 9 new tests pass + existing `tests/test_event_emitter.py` continues to pass under `pytest -m "unit or integration" tests/test_observability.py tests/test_event_emitter.py`.
- [ ] `EVENT_TYPE_CATALOG` in `event_types.py` exactly mirrors the catalog table in this spec (asserted by test 9 plus a manual review at integration burn).
- [ ] `push_event` never raises — `test_push_event_swallows_langfuse_failure_and_logs_warn` proves it for the Langfuse-side failure mode.
- [ ] `mypy --strict app/observability/` passes (best-effort).
