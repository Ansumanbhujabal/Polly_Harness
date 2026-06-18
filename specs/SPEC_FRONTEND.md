# SPEC: Frontend

**Layer:** Cross-cutting (the user-facing surface — the Loom shows this)
**Owner:** `frontend/`

The Frontend layer is the Gradio app that renders the chat tab and the admin dashboard. It mounts under the FastAPI app at `/`. The chat tab is a standard chatbot. The admin tab is four panels: a live SSE-driven reasoning log, the dynamic Mermaid architecture diagram that pulses the active layer, a pending-approvals table with Approve/Deny buttons, and an incidents table with a "Run Distiller" button.

Demo Mode (controlled by `settings.DEMO_MODE`) shows three "try one of these" chips seeded from the 5 holding-the-line cases — a Loom-friendly affordance.

## Contract

```python
from frontend.app import build_gradio_app
```

- `build_gradio_app() -> gr.Blocks` — constructs the top-level Gradio Blocks app: one `gr.Tabs` container with two tabs (Chat, Admin). The Admin tab itself contains four nested `gr.Tab`s. Returns the unmounted Blocks object — the FastAPI layer mounts it.

## Components

### Chat tab (root `/`)

- `gr.Chatbot` for the conversation history.
- `gr.Textbox` (with submit on Enter) for the user input.
- `gr.Markdown` showing the resolved `conversation_id` (for support / debugging).
- An approval banner (`gr.HTML` element, default hidden) that becomes visible when an SSE event of type `interrupt_raised` arrives. The banner text: *"Approval required for approval_id={id}. Switch to the Admin tab → Pending Approvals."*
- Demo-mode chips: when `settings.DEMO_MODE=True`, three `gr.Button` chips with the first three demo case prompts from `data/demo/seed_prompts.json`. Clicking a chip fills the input.

The chat handler `on_submit(message, conversation_id)`:
1. POSTs to `/api/v1/chat` with the (optional) `conversation_id` and the message.
2. Receives the AgentStateSummary; appends to chatbot history.
3. Persists the returned `conversation_id` in `gr.State` for the next turn.
4. The SSE listener (separate path) is opened on the conversation_id at chat start.

### Admin tab

Four sub-tabs inside a `gr.Tabs`:

1. **Live Trace**
   - Top: filter input for `conversation_id`.
   - Body: scrollable list of `LayerEvent` rows, each a colored chip + expandable JSON payload.
   - Chip color is keyed by `LayerName` (palette defined in `frontend/static/styles.css`).
   - SSE-driven — opens `EventSource("/events/stream?conversation_id=...")`.

2. **Architecture Diagram**
   - `gr.HTML` containing the inline Mermaid source from `frontend/static/mermaid_diagram.html` + a `<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js">` loader (CDN).
   - The Mermaid graph renders all 9 layers as nodes; the SSE listener tags the active layer's node with class `.active-layer` for the duration of one CSS pulse animation.
   - Animation defined in `styles.css`: `@keyframes pulse { 0%,100% { filter: none; } 50% { filter: drop-shadow(0 0 8px var(--accent)); } }`.

3. **Pending Approvals**
   - `gr.Dataframe` fed from `/admin/api/pending_approvals`.
   - Per row: Approve / Deny / View Reasoning buttons.
   - Approve and Deny POST to `/api/v1/approve`; on success, refresh the table.

4. **Incidents**
   - `gr.Dataframe` fed from `/admin/api/incidents?limit=20`.
   - "Run Distiller" button → POST `/admin/api/distill` → opens a modal (`gr.Group`) showing the returned `ProposedRemediation` list, each with `kind`, `target_file`, `markdown_diff` (in a `gr.Code`), and `justification`.

## Behaviors

- **SSE consumed via vanilla JS** — `frontend/static/sse_listener.js` defines `subscribeToEvents(conversationId)` and `subscribeToLayerPulses()`. The listener pushes events into a hidden `gr.State` that Gradio reads on the next event-loop tick, enabling reactive updates.
- **Mermaid diagram rebuild** is not full-rebuild — we toggle a class on the existing `<div>` element. Reduces flicker.
- **Approval banner** subscribes to all SSE events for the current `conversation_id`; reveals on any event with `event_type=interrupt_raised`.
- **Demo mode chips** render only when `settings.DEMO_MODE=True`. Source of truth is `data/demo/seed_prompts.json`, an array of objects with `{case_id, label, prompt}` for each of the 5 demo cases (the first three render as chips; all five are listed in the Admin → Incidents help text).
- **`DEMO_MODE` setting** is added to `app/config.Settings` by the E1 builder — flagged here so the cross-spec touchpoint is visible to the reviewer.
- **No real network calls in tests** — the panel-factory tests just construct the `gr.Blocks` object and assert structure; live behavior is verified manually during integration burn.

## Files

```
frontend/__init__.py
frontend/app.py                       # build_gradio_app() — composes Chat + Admin
frontend/components/__init__.py
frontend/components/chat_panel.py     # chat_panel_factory()
frontend/components/admin_panel.py    # admin_panel_factory() — 4 inner tabs
frontend/components/approval_panel.py # pending-approvals panel
frontend/components/incidents_panel.py# incidents + distiller modal
frontend/static/mermaid_diagram.html  # inline mermaid graph source + script tag
frontend/static/sse_listener.js       # subscribeToEvents / subscribeToLayerPulses
frontend/static/styles.css            # chip colors, pulse animation
```

Plus `data/demo/seed_prompts.json` (owned by SPEC_DEMO_SCRIPT, referenced here).

## Dependencies

- `gradio>=5.0.0`
- `httpx` (for the chat panel's POSTs to the API)
- `app.config.settings` for `DEMO_MODE`
- `app.domain.models.LayerName` for the chip palette mapping

Out of scope: a React/Next.js frontend (explicit scope cut), mobile-responsive styling, dark mode toggle.

## Tests

`tests/test_frontend.py` — minimum tests:

1. `test_chat_panel_factory_returns_blocks` — `chat_panel_factory()` returns a `gr.Blocks` with at least one `gr.Chatbot` and one `gr.Textbox`.
2. `test_admin_panel_factory_returns_blocks_with_four_tabs` — admin factory's returned tree contains exactly 4 nested `gr.Tab` children (Live Trace, Architecture, Pending Approvals, Incidents).
3. `test_mermaid_diagram_html_includes_all_nine_layers` — read `frontend/static/mermaid_diagram.html`; assert each `LayerName` value appears as a node identifier.
4. `test_sse_listener_js_subscribes_to_correct_url` — read `frontend/static/sse_listener.js`; assert `EventSource("/events/stream?conversation_id=" + conversationId)` appears.
5. `test_demo_seed_prompts_match_five_cases` — load `data/demo/seed_prompts.json`; assert exactly 5 entries; each `case_id` matches one of the 5 case ids from SPEC_DEMO_SCRIPT.

## Done criteria

- [ ] All 10 files (4 component files + 3 static files + `frontend/__init__.py` + `frontend/app.py` + `frontend/components/__init__.py`) exist.
- [ ] All 5 tests pass under `pytest -m "unit or integration" tests/test_frontend.py`.
- [ ] `python -c "from frontend.app import build_gradio_app; build_gradio_app()"` runs without raising.
- [ ] Integration-burn manual smoke: chat works, dashboard renders, SSE events arrive in Live Trace, Mermaid diagram pulses on a real refund flow, approval banner appears for the $1,200 case.
- [ ] `DEMO_MODE` setting added to `app/config.Settings` with default `False`.
- [ ] `mypy --strict frontend/` passes (best-effort).
