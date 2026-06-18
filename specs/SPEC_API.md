# SPEC: API

**Layer:** Cross-cutting (the HTTP surface; Gradio mounts under here)
**Owner:** `app/api/`

The API layer is the FastAPI app that exposes the agent over HTTP and Server-Sent Events. It mounts Gradio at the root path, exposes chat + approval write-side endpoints under `/api/v1`, streams live `LayerEvent` traces under `/events`, and exposes admin endpoints for the dashboard. The lifespan boot order is owned by `SPEC_EXECUTION`; this spec owns the routes, response shapes, and request validation.

Auth is intentionally out of scope (single-user demo) — documented in ADR-0006.

## Contract

```python
from app.api.main import app  # FastAPI ASGI app — used by uvicorn
```

Mounting:

```python
import gradio as gr
from frontend.app import build_gradio_app
gradio_app = build_gradio_app()
gr.mount_gradio_app(app, gradio_app, path="/")
```

After mount: root path serves the chat tab, `/admin/*` (Gradio sub-routes) serves the dashboard tabs, `/api/v1/*` and `/events/*` and `/admin/api/*` serve the backend routes specified below.

## Endpoints

| Method | Path | Purpose | Body | Response |
|---|---|---|---|---|
| GET | `/healthz` | Liveness + dep status | — | `{ok: bool, version: str, qdrant: "up"\|"down", langfuse: "up"\|"down"}` |
| POST | `/api/v1/chat` | Drive one conversation turn | `{conversation_id?: str, message: str}` | `{accepted: true, conversation_id: str, final_state_summary: AgentStateSummary}` |
| POST | `/api/v1/approve` | Resolve a pending approval | `{approval_id: str, resolution: "approved"\|"denied", approver: str}` | `{accepted: true, resource_id: str (= approval_id)}` |
| GET | `/events/stream?conversation_id=...` | Live SSE trace | — | `text/event-stream` of `LayerEvent` JSON |
| GET | `/admin/api/pending_approvals` | List unresolved approvals | — | `{items: list[PendingApproval]}` |
| GET | `/admin/api/incidents?limit=20` | List recent incidents | — | `{items: list[IncidentRecord]}` |
| GET | `/admin/api/conversations/{conversation_id}/trace` | Chronological events for a conversation | — | `{items: list[LayerEvent]}` |
| POST | `/admin/api/distill` | Trigger distillation, return proposals | — | `{accepted: true, proposals: list[ProposedRemediation]}` |

Notes:

- `AgentStateSummary` is a small Pydantic projection of `AgentState` (id, final_decision, response_text, num_tool_invocations, awaiting_human_approval). Defined inline in `app/api/routes/chat.py`. NOT exported.
- The SSE stream uses `sse-starlette.EventSourceResponse`, yielding `LayerEvent.model_dump_json()` per event. Connection keep-alive 15s.
- `conversation_id` is auto-generated (`uuid4()`) when omitted on the first `/api/v1/chat` call. The response always includes the resolved id.

## Behaviors

- **No auth.** The CORS middleware allows only `settings.CORS_ALLOWED_ORIGINS` (default: `["http://localhost:7860"]`). Documented as an explicit scope cut in ADR-0006.
- **All write endpoints** return `{accepted: true, resource_id: ...}` envelopes so the Gradio frontend can poll or subscribe to SSE for the actual result. Errors return `{accepted: false, error_code: str, detail: str}` with appropriate 4xx/5xx status.
- **`/healthz` is fast** — does NOT block on Langfuse if it's slow; uses a 1 s timeout and reports `"down"` on timeout/error.
- **`/api/v1/chat` is async** — awaits `RefundGraph.ainvoke`; if the graph returns with `awaiting_human_approval=True`, the response surfaces this in the summary and the frontend renders the approval banner.
- **`/api/v1/approve` validates** that the approval_id exists in `pending_approvals` and is unresolved. Returns 404 if not found, 409 if already resolved.
- **`/events/stream`** subscribes via `app.observability.sse_event_stream(conversation_id=...)`. Disconnect by client just cancels the generator — no cleanup needed beyond what SSE-Starlette handles.
- **`/admin/api/distill`** awaits `distill_incidents()` and returns the resulting `ProposedRemediation` list inline (not async-deferred — distillation completes in seconds for the demo).

## Files

```
app/api/__init__.py             # exists; modified to export `app`
app/api/main.py                 # FastAPI(app, lifespan=lifespan) + Gradio mount + CORS
app/api/lifespan.py             # owned here, boot order from SPEC_EXECUTION
app/api/routes/__init__.py      # exports an APIRouter aggregator
app/api/routes/health.py        # GET /healthz
app/api/routes/chat.py          # POST /api/v1/chat + AgentStateSummary
app/api/routes/approval.py      # POST /api/v1/approve
app/api/routes/events.py        # GET /events/stream
app/api/routes/admin.py         # /admin/api/* group
```

## Dependencies

- `app.graph` — `build_graph`, `RefundGraph`
- `app.state` — `get_repository` (for approval validation, pending/incidents listing)
- `app.observability` — `sse_event_stream`, `get_langfuse_client`, `get_logger`
- `app.learning` — `distill_incidents` (for the distill endpoint)
- `frontend.app.build_gradio_app` — the Gradio surface
- `fastapi`, `sse-starlette`, `uvicorn[standard]`, `httpx` (for healthz probes)

Out of scope: WebSocket transport (SSE is sufficient), file uploads, multipart forms.

## Tests

`tests/test_api.py` — minimum tests, using `httpx.AsyncClient(transport=ASGITransport(app=app))`:

1. `test_healthz_returns_ok_when_all_deps_up` — mock both deps healthy; assert 200 + `ok=true`.
2. `test_healthz_returns_qdrant_down_when_unreachable` — Qdrant probe raises; assert response includes `qdrant: "down"` but still 200.
3. `test_chat_route_invokes_graph_and_returns_response` — patch `RefundGraph.ainvoke` to return a known state; assert response summary fields match.
4. `test_chat_route_creates_conversation_id_when_missing` — omit `conversation_id`; response includes a freshly-minted UUID.
5. `test_approve_route_resumes_interrupted_graph` — seed a `pending_approvals` row; POST `/api/v1/approve`; assert `RefundGraph.aresume` was called with the matching resolution.
6. `test_approve_route_404_on_unknown_approval_id` — assert 404 status code.
7. `test_events_stream_emits_layer_events_for_conversation` — inject 3 events via `push_event` with `conversation_id="X"`; subscribe to `/events/stream?conversation_id=X`; assert 3 events parsed from the SSE stream.
8. `test_events_stream_filters_by_conversation_id` — inject for "X" and "Y"; subscribe with "X"; only X events arrive.
9. `test_admin_pending_approvals_lists_unresolved` — seed 2 unresolved + 1 resolved; assert response has 2 items.
10. `test_admin_incidents_returns_limit_filtered_list` — seed 30 incidents; request `?limit=20`; assert 20 items.
11. `test_admin_distill_endpoint_triggers_distillation` — patch `distill_incidents` to return a known proposal; assert it's in the response.
12. `test_admin_conversation_trace_returns_chronological_events` — seed events with mixed timestamps; assert response is sorted ascending by timestamp.

## Done criteria

- [ ] All 9 source files exist.
- [ ] All 12 tests pass under `pytest -m "unit or integration" tests/test_api.py`.
- [ ] `GET /docs` returns the OpenAPI schema and includes every named endpoint above (smoke test in `test_api.py` is acceptable).
- [ ] `uvicorn app.api.main:app` boots cleanly within 3 seconds in a `timeout 5 ...` shell check — verified during Wave 3 integration smoke.
- [ ] CORS middleware is wired and reads from `settings.CORS_ALLOWED_ORIGINS`.
- [ ] `mypy --strict app/api/` passes (best-effort).
