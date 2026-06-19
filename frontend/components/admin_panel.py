"""Admin panel factory — 4 inner sub-tabs: Live Trace, Architecture Diagram,
Pending Approvals, Incidents.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import gradio as gr
import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MERMAID_HTML_PATH = REPO_ROOT / "frontend" / "static" / "mermaid_diagram.html"
SSE_JS_PATH = REPO_ROOT / "frontend" / "static" / "sse_listener.js"

logger = logging.getLogger(__name__)


def admin_panel_factory() -> gr.Blocks:
    """Build and return the Admin tab as a gr.Blocks containing exactly 4 gr.Tab children."""
    mermaid_html = ""
    if MERMAID_HTML_PATH.exists():
        mermaid_html = MERMAID_HTML_PATH.read_text(encoding="utf-8")

    sse_js = ""
    if SSE_JS_PATH.exists():
        sse_js = SSE_JS_PATH.read_text(encoding="utf-8")

    with gr.Blocks(title="Refund Agent — Admin") as panel:
        gr.Markdown("# Admin Dashboard")

        with gr.Tabs():
            # ---------------------------------------------------------------- #
            # Tab 1 — Live Trace
            # ---------------------------------------------------------------- #
            with gr.Tab("Live Trace"):
                gr.Markdown("## Live Trace\nSSE-driven log of all LayerEvents for a conversation.")
                conv_filter = gr.Textbox(
                    label="Filter by conversation_id",
                    placeholder="Paste conversation_id…",
                )
                trace_output = gr.HTML(
                    value="<p><em>Enter a conversation_id above, then events will appear here.</em></p>",
                    label="Event stream",
                )

                # SSE JS is injected via panel.head below (Gradio 6 scripts run via head, not HTML body)

                def _apply_filter(conv_id: str) -> str:
                    if not conv_id.strip():
                        return "<p><em>Enter a conversation_id to start streaming events.</em></p>"
                    return (
                        f'<p>Subscribed to events for <code>{conv_id}</code></p>'
                        f'<div id="trace-container" data-conversation-id="{conv_id}"></div>'
                    )

                conv_filter.change(fn=_apply_filter, inputs=[conv_filter], outputs=[trace_output])

            # ---------------------------------------------------------------- #
            # Tab 2 — Architecture Diagram
            # ---------------------------------------------------------------- #
            with gr.Tab("Architecture Diagram"):
                gr.Markdown(
                    "## Architecture Diagram\n"
                    "Mermaid graph of all 9 harness layers. "
                    "The SSE listener pulses the active layer node with a CSS drop-shadow."
                )
                gr.HTML(
                    value=mermaid_html if mermaid_html else "<p>Mermaid diagram not found.</p>",
                    elem_id="architecture-diagram",
                )

            # ---------------------------------------------------------------- #
            # Tab 3 — Pending Approvals
            # ---------------------------------------------------------------- #
            with gr.Tab("Pending Approvals"):
                gr.Markdown("## Pending Approvals")
                gr.Markdown(
                    "Refund decisions that exceed the auto-approval cap and require human sign-off."
                )

                approvals_df = gr.Dataframe(
                    headers=["approval_id", "conversation_id", "amount_usd", "decision_kind", "created_at"],
                    label="Pending Approvals",
                    interactive=False,
                    wrap=True,
                )

                with gr.Row():
                    approval_id_input = gr.Textbox(
                        label="Approval ID",
                        placeholder="Paste approval_id from the table above…",
                        scale=4,
                    )
                    approver_input = gr.Textbox(
                        label="Approver name",
                        placeholder="Your name / role",
                        value="admin",
                        scale=2,
                    )

                with gr.Row():
                    approve_btn = gr.Button("Approve", variant="primary")
                    deny_btn = gr.Button("Deny", variant="stop")
                    refresh_approvals_btn = gr.Button("Refresh Table")

                approval_result = gr.Markdown(value="")

                async def _fetch_approvals() -> list[list[Any]]:
                    try:
                        async with httpx.AsyncClient(timeout=10.0) as client:
                            resp = await client.get("http://localhost:8000/admin/api/pending_approvals")
                            resp.raise_for_status()
                            items = resp.json().get("items", [])
                    except Exception as exc:  # noqa: BLE001
                        logger.error("fetch_approvals error: %s", exc)
                        items = []
                    rows: list[list[Any]] = []
                    for item in items:
                        cd = item.get("candidate_decision", {})
                        rows.append([
                            item.get("approval_id", ""),
                            item.get("conversation_id", ""),
                            cd.get("amount_usd", 0.0),
                            cd.get("kind", ""),
                            item.get("created_at", ""),
                        ])
                    return rows

                async def _resolve(
                    approval_id: str, resolution: str, approver: str
                ) -> tuple[str, list[list[Any]]]:
                    if not approval_id.strip():
                        return "Please enter an approval_id.", []
                    try:
                        async with httpx.AsyncClient(timeout=10.0) as client:
                            resp = await client.post(
                                "http://localhost:8000/api/v1/approve",
                                json={
                                    "approval_id": approval_id.strip(),
                                    "resolution": resolution,
                                    "approver": approver.strip() or "admin",
                                },
                            )
                            resp.raise_for_status()
                            msg = f"Resolution '{resolution}' recorded for {approval_id}."
                    except Exception as exc:  # noqa: BLE001
                        msg = f"Error: {exc}"
                    rows = await _fetch_approvals()
                    return msg, rows

                async def on_approve(approval_id: str, approver: str) -> tuple[str, list[list[Any]]]:
                    return await _resolve(approval_id, "approved", approver)

                async def on_deny(approval_id: str, approver: str) -> tuple[str, list[list[Any]]]:
                    return await _resolve(approval_id, "denied", approver)

                approve_btn.click(
                    fn=on_approve,
                    inputs=[approval_id_input, approver_input],
                    outputs=[approval_result, approvals_df],
                )
                deny_btn.click(
                    fn=on_deny,
                    inputs=[approval_id_input, approver_input],
                    outputs=[approval_result, approvals_df],
                )
                refresh_approvals_btn.click(
                    fn=_fetch_approvals,
                    inputs=[],
                    outputs=[approvals_df],
                )

            # ---------------------------------------------------------------- #
            # Tab 4 — Incidents
            # ---------------------------------------------------------------- #
            with gr.Tab("Incidents"):
                gr.Markdown("## Incidents")
                gr.Markdown(
                    "Recent structured incidents logged by the failure-to-infrastructure loop. "
                    "**Run Distiller** sends these to the LLM distiller to generate "
                    "PR-ready remediation proposals.\n\n"
                    "_Demo cases: Case 3 (serial refunder), "
                    "Case 4 ($1,200 interrupt), Case 5 (injection + emotional pressure)._"
                )

                incidents_df = gr.Dataframe(
                    headers=["incident_id", "triggered_by", "layer", "summary", "created_at"],
                    label="Recent Incidents (last 20)",
                    interactive=False,
                    wrap=True,
                )

                with gr.Row():
                    refresh_inc_btn = gr.Button("Refresh Incidents")
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
                            resp = await client.get(
                                "http://localhost:8000/admin/api/incidents",
                                params={"limit": 20},
                            )
                            resp.raise_for_status()
                            items = resp.json().get("items", [])
                    except Exception as exc:  # noqa: BLE001
                        logger.error("fetch_incidents error: %s", exc)
                        items = []
                    rows: list[list[Any]] = []
                    for item in items:
                        rows.append([
                            item.get("incident_id", ""),
                            item.get("triggered_by", ""),
                            item.get("layer", ""),
                            item.get("summary", ""),
                            item.get("created_at", ""),
                        ])
                    return rows

                async def on_distill() -> tuple[str, dict[str, Any], str, str, dict[str, Any]]:
                    try:
                        async with httpx.AsyncClient(timeout=60.0) as client:
                            resp = await client.post("http://localhost:8000/admin/api/distill")
                            resp.raise_for_status()
                            data = resp.json()
                    except Exception as exc:  # noqa: BLE001
                        return (
                            f"Distiller error: {exc}",
                            gr.update(visible=False),
                            "",
                            "",
                            gr.update(visible=False),
                        )  # type: ignore[return-value]

                    proposals = data.get("proposals", [])
                    if not proposals:
                        return (  # type: ignore[return-value]
                            "Distiller ran — no proposals generated.",
                            gr.update(visible=True),
                            "_No proposals._",
                            "",
                            gr.update(visible=True),
                        )

                    md_lines: list[str] = []
                    first_diff = ""
                    for i, p in enumerate(proposals, start=1):
                        md_lines.append(
                            f"**{i}. {p.get('kind', '')}** — `{p.get('target_file', '')}`\n\n"
                            f"> {p.get('justification', '')}"
                        )
                        if i == 1:
                            first_diff = p.get("markdown_diff", "")

                    return (  # type: ignore[return-value]
                        f"Distiller produced {len(proposals)} proposal(s).",
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

        # Inject SSE listener into the page head (Gradio 6 — scripts in HTML body are inert)
        if sse_js:
            panel.head = f"<script>{sse_js}</script>"

    return panel
