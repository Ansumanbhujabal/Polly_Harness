"""Top-level Gradio app — build_gradio_app() composes Chat + Admin tabs.

The FastAPI layer mounts the returned gr.Blocks at the root path via
``gr.mount_gradio_app(fastapi_app, gradio_blocks, path="/")``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import gradio as gr
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_PROMPTS_PATH = REPO_ROOT / "data" / "demo" / "seed_prompts.json"
MERMAID_HTML_PATH = REPO_ROOT / "frontend" / "static" / "mermaid_diagram.html"
SSE_JS_PATH = REPO_ROOT / "frontend" / "static" / "sse_listener.js"


def _load_demo_prompts() -> list[dict[str, str]]:
    try:
        with SEED_PROMPTS_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)  # type: ignore[no-any-return]
    except Exception:  # noqa: BLE001
        return []


def build_gradio_app() -> gr.Blocks:
    """Construct and return the top-level Gradio Blocks app.

    Structure:
        gr.Blocks
          └── gr.Tabs
                ├── gr.Tab("Chat")
                └── gr.Tab("Admin")  — 4 inner gr.Tab children

    Returns the unmounted Blocks object.
    """
    demo_prompts = _load_demo_prompts() if settings.DEMO_MODE else []

    mermaid_html = ""
    if MERMAID_HTML_PATH.exists():
        mermaid_html = MERMAID_HTML_PATH.read_text(encoding="utf-8")

    sse_js = ""
    if SSE_JS_PATH.exists():
        sse_js = SSE_JS_PATH.read_text(encoding="utf-8")

    with gr.Blocks(
        title="Refund Agent — Harness-Engineered Customer Support",
    ) as app:
        gr.Markdown(
            "# Refund Agent\n"
            "_Harness-engineered AI customer support — 9 layers around the LLM._"
        )

        with gr.Tabs():
            # ------------------------------------------------------------------ #
            # Tab 1 — Chat
            # ------------------------------------------------------------------ #
            with gr.Tab("Chat"):
                conversation_id_state = gr.State(value=None)
                conv_id_display = gr.Markdown(value="_No conversation started yet._")

                approval_banner = gr.HTML(value="", visible=False, elem_id="approval-banner")

                chatbot = gr.Chatbot(
                    label="Refund Agent",
                    layout="bubble",
                    height=420,
                )

                with gr.Row():
                    msg_input = gr.Textbox(
                        placeholder="Describe your refund request…",
                        label="Your message",
                        scale=8,
                        submit_btn=True,
                    )

                if settings.DEMO_MODE and demo_prompts:
                    gr.Markdown("**Try one of these:**")
                    with gr.Row():
                        for entry in demo_prompts[:3]:
                            chip = gr.Button(value=entry["label"], size="sm")

                            def _make_fill(prompt: str) -> Any:
                                def _fill() -> str:
                                    return prompt
                                return _fill

                            chip.click(fn=_make_fill(entry["prompt"]), inputs=[], outputs=[msg_input])

                async def on_submit(
                    message: str,
                    history: list[dict[str, str]],
                    conv_id: str | None,
                ) -> tuple[list[dict[str, str]], str | None, str, str, dict[str, Any]]:
                    if not message.strip():
                        return history, conv_id, "", conv_id_display.value, gr.update(visible=False)  # type: ignore[return-value]

                    payload: dict[str, Any] = {"message": message}
                    if conv_id:
                        payload["conversation_id"] = conv_id

                    try:
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            resp = await client.post(
                                "http://localhost:8000/api/v1/chat",
                                json=payload,
                            )
                            resp.raise_for_status()
                            data = resp.json()
                    except Exception as exc:  # noqa: BLE001
                        logger.error("chat on_submit error: %s", exc)
                        history = list(history) + [
                            {"role": "user", "content": message},
                            {"role": "assistant", "content": f"Agent error: {exc}"},
                        ]
                        return history, conv_id, "", "_Error_", gr.update(visible=False)  # type: ignore[return-value]

                    returned_conv_id: str = data.get("conversation_id", conv_id or "")
                    summary = data.get("final_state_summary", {})
                    agent_reply: str = summary.get("response_text") or "(no response)"

                    history = list(history) + [
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": agent_reply},
                    ]

                    awaiting = summary.get("awaiting_human_approval", False)
                    approval_id_val = summary.get("approval_id", "")
                    if awaiting:
                        banner_html = (
                            f'<div class="approval-banner-visible">'
                            f"Approval required for approval_id={approval_id_val}. "
                            f"Switch to the Admin tab &rarr; Pending Approvals."
                            f"</div>"
                        )
                        banner_update = gr.update(value=banner_html, visible=True)
                    else:
                        banner_update = gr.update(value="", visible=False)

                    return (  # type: ignore[return-value]
                        history,
                        returned_conv_id,
                        "",
                        f"_Conversation ID: `{returned_conv_id}`_",
                        banner_update,
                    )

                msg_input.submit(
                    fn=on_submit,
                    inputs=[msg_input, chatbot, conversation_id_state],
                    outputs=[chatbot, conversation_id_state, msg_input, conv_id_display, approval_banner],
                )

            # ------------------------------------------------------------------ #
            # Tab 2 — Admin (4 inner tabs)
            # ------------------------------------------------------------------ #
            with gr.Tab("Admin"):
                gr.Markdown("# Admin Dashboard")

                with gr.Tabs():
                    # ---- Live Trace ----
                    with gr.Tab("Live Trace"):
                        gr.Markdown("## Live Trace\nSSE-driven log of all LayerEvents.")
                        conv_filter = gr.Textbox(
                            label="Filter by conversation_id",
                            placeholder="Paste conversation_id…",
                        )
                        trace_output = gr.HTML(
                            value="<p><em>Enter a conversation_id to stream events.</em></p>",
                        )

                        def _apply_filter(conv_id: str) -> str:
                            if not conv_id.strip():
                                return "<p><em>Enter a conversation_id.</em></p>"
                            return (
                                f'<p>Subscribed to events for <code>{conv_id}</code></p>'
                                f'<div id="trace-container" data-conversation-id="{conv_id}"></div>'
                            )

                        conv_filter.change(
                            fn=_apply_filter, inputs=[conv_filter], outputs=[trace_output]
                        )

                    # ---- Architecture Diagram ----
                    with gr.Tab("Architecture Diagram"):
                        gr.Markdown(
                            "## Architecture Diagram\n"
                            "Mermaid graph of all 9 harness layers. "
                            "SSE listener pulses the active layer node."
                        )
                        gr.HTML(
                            value=mermaid_html or "<p>Mermaid diagram not found.</p>",
                            elem_id="architecture-diagram",
                        )

                    # ---- Pending Approvals ----
                    with gr.Tab("Pending Approvals"):
                        gr.Markdown("## Pending Approvals")
                        approvals_df = gr.Dataframe(
                            headers=["approval_id", "conversation_id", "amount_usd", "decision_kind", "created_at"],
                            label="Pending Approvals",
                            interactive=False,
                            wrap=True,
                        )
                        with gr.Row():
                            approval_id_input = gr.Textbox(
                                label="Approval ID",
                                placeholder="Paste approval_id…",
                                scale=4,
                            )
                            approver_input = gr.Textbox(
                                label="Approver",
                                value="admin",
                                scale=2,
                            )
                        with gr.Row():
                            approve_btn = gr.Button("Approve", variant="primary")
                            deny_btn = gr.Button("Deny", variant="stop")
                            refresh_approvals_btn = gr.Button("Refresh")
                        approval_result = gr.Markdown(value="")

                        async def _fetch_approvals() -> list[list[Any]]:
                            try:
                                async with httpx.AsyncClient(timeout=10.0) as client:
                                    r = await client.get("http://localhost:8000/admin/api/pending_approvals")
                                    r.raise_for_status()
                                    items = r.json().get("items", [])
                            except Exception as exc:  # noqa: BLE001
                                logger.error("fetch_approvals: %s", exc)
                                items = []
                            return [
                                [
                                    i.get("approval_id", ""),
                                    i.get("conversation_id", ""),
                                    i.get("candidate_decision", {}).get("amount_usd", 0.0),
                                    i.get("candidate_decision", {}).get("kind", ""),
                                    i.get("created_at", ""),
                                ]
                                for i in items
                            ]

                        async def _resolve_approval(
                            approval_id: str, resolution: str, approver: str
                        ) -> tuple[str, list[list[Any]]]:
                            if not approval_id.strip():
                                return "Please enter an approval_id.", []
                            try:
                                async with httpx.AsyncClient(timeout=10.0) as client:
                                    r = await client.post(
                                        "http://localhost:8000/api/v1/approve",
                                        json={
                                            "approval_id": approval_id.strip(),
                                            "resolution": resolution,
                                            "approver": approver.strip() or "admin",
                                        },
                                    )
                                    r.raise_for_status()
                                msg = f"'{resolution}' recorded for {approval_id}."
                            except Exception as exc:  # noqa: BLE001
                                msg = f"Error: {exc}"
                            rows = await _fetch_approvals()
                            return msg, rows

                        async def on_approve_click(a: str, ap: str) -> tuple[str, list[list[Any]]]:
                            return await _resolve_approval(a, "approved", ap)

                        async def on_deny_click(a: str, ap: str) -> tuple[str, list[list[Any]]]:
                            return await _resolve_approval(a, "denied", ap)

                        approve_btn.click(
                            fn=on_approve_click,
                            inputs=[approval_id_input, approver_input],
                            outputs=[approval_result, approvals_df],
                        )
                        deny_btn.click(
                            fn=on_deny_click,
                            inputs=[approval_id_input, approver_input],
                            outputs=[approval_result, approvals_df],
                        )
                        refresh_approvals_btn.click(
                            fn=_fetch_approvals, inputs=[], outputs=[approvals_df]
                        )

                    # ---- Incidents ----
                    with gr.Tab("Incidents"):
                        gr.Markdown("## Incidents")
                        incidents_df = gr.Dataframe(
                            headers=["incident_id", "triggered_by", "layer", "summary", "created_at"],
                            label="Recent Incidents (last 20)",
                            interactive=False,
                            wrap=True,
                        )
                        with gr.Row():
                            refresh_inc_btn = gr.Button("Refresh")
                            distill_btn = gr.Button("Run Distiller", variant="primary")
                        distill_status = gr.Markdown(value="")

                        with gr.Group(visible=False) as distill_modal:
                            gr.Markdown("### Distiller Proposals")
                            proposals_md = gr.Markdown(value="")
                            proposal_diff = gr.Code(
                                label="Unified Diff (first proposal)",
                                language="shell",
                                interactive=False,
                            )

                        async def _fetch_incidents() -> list[list[Any]]:
                            try:
                                async with httpx.AsyncClient(timeout=10.0) as client:
                                    r = await client.get(
                                        "http://localhost:8000/admin/api/incidents",
                                        params={"limit": 20},
                                    )
                                    r.raise_for_status()
                                    items = r.json().get("items", [])
                            except Exception as exc:  # noqa: BLE001
                                logger.error("fetch_incidents: %s", exc)
                                items = []
                            return [
                                [
                                    i.get("incident_id", ""),
                                    i.get("triggered_by", ""),
                                    i.get("layer", ""),
                                    i.get("summary", ""),
                                    i.get("created_at", ""),
                                ]
                                for i in items
                            ]

                        async def on_distill() -> tuple[str, dict[str, Any], str, str, dict[str, Any]]:
                            try:
                                async with httpx.AsyncClient(timeout=60.0) as client:
                                    r = await client.post("http://localhost:8000/admin/api/distill")
                                    r.raise_for_status()
                                    data = r.json()
                            except Exception as exc:  # noqa: BLE001
                                return (  # type: ignore[return-value]
                                    f"Distiller error: {exc}",
                                    gr.update(visible=False),
                                    "",
                                    "",
                                    gr.update(visible=False),
                                )

                            props = data.get("proposals", [])
                            if not props:
                                return (  # type: ignore[return-value]
                                    "No proposals generated.",
                                    gr.update(visible=True),
                                    "_No proposals._",
                                    "",
                                    gr.update(visible=True),
                                )

                            md_lines = [
                                f"**{i}. {p.get('kind','')}** — `{p.get('target_file','')}`\n\n> {p.get('justification','')}"
                                for i, p in enumerate(props, 1)
                            ]
                            first_diff = props[0].get("markdown_diff", "") if props else ""
                            return (  # type: ignore[return-value]
                                f"Distiller produced {len(props)} proposal(s).",
                                gr.update(visible=True),
                                "\n\n---\n\n".join(md_lines),
                                first_diff,
                                gr.update(visible=True),
                            )

                        refresh_inc_btn.click(fn=_fetch_incidents, inputs=[], outputs=[incidents_df])
                        distill_btn.click(
                            fn=on_distill,
                            inputs=[],
                            outputs=[distill_status, distill_modal, proposals_md, proposal_diff, distill_modal],
                        )

        # Inject SSE listener JS into the page head
        if sse_js:
            app.head = f"<script>{sse_js}</script>"

    return app
