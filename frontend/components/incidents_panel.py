"""Incidents panel — gr.Blocks with incidents dataframe + distiller modal."""

from __future__ import annotations

import logging
from typing import Any

import gradio as gr
import httpx

logger = logging.getLogger(__name__)


def incidents_panel_factory() -> gr.Blocks:
    """Build and return the Incidents panel as a gr.Blocks.

    Fetches from /admin/api/incidents?limit=20.
    'Run Distiller' button POSTs to /admin/api/distill and shows proposals
    in an expandable gr.Group modal.
    """
    with gr.Blocks() as panel:
        gr.Markdown("## Incidents")
        gr.Markdown(
            "Recent structured incidents logged by the failure-to-infrastructure loop. "
            "The **Run Distiller** button sends these to the LLM distiller to generate "
            "PR-ready remediation proposals.\n\n"
            "_Demo cases that log incidents: Case 3 (serial refunder), "
            "Case 4 ($1,200 interrupt), Case 5 (injection + emotional pressure)._"
        )

        incidents_df = gr.Dataframe(
            headers=["incident_id", "triggered_by", "layer", "summary", "created_at"],
            label="Recent Incidents (last 20)",
            interactive=False,
            wrap=True,
        )

        with gr.Row():
            refresh_btn = gr.Button("Refresh Incidents")
            distill_btn = gr.Button("Run Distiller", variant="primary")

        distill_status = gr.Markdown(value="")

        # Distiller results modal
        with gr.Group(visible=False) as distill_modal:
            gr.Markdown("### Distiller Proposals")
            proposals_md = gr.Markdown(value="")
            proposal_diff = gr.Code(
                label="Unified Diff (first proposal)",
                language="shell",
                interactive=False,
            )

        # ---------------------------------------------------------------------------
        # Helpers
        # ---------------------------------------------------------------------------

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

        async def on_refresh() -> list[list[Any]]:
            return await _fetch_incidents()

        async def on_distill() -> tuple[str, dict[str, Any], str, str, dict[str, Any]]:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post("http://localhost:8000/admin/api/distill")
                    resp.raise_for_status()
                    data = resp.json()
            except Exception as exc:  # noqa: BLE001
                error_msg = f"Distiller error: {exc}"
                return error_msg, gr.update(visible=False), "", "", gr.update(visible=False)

            proposals = data.get("proposals", [])
            if not proposals:
                return (
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

            proposals_text = "\n\n---\n\n".join(md_lines)
            status_msg = f"Distiller produced {len(proposals)} proposal(s)."

            return status_msg, gr.update(visible=True), proposals_text, first_diff, gr.update(visible=True)  # type: ignore[return-value]

        # Wire buttons
        refresh_btn.click(fn=on_refresh, inputs=[], outputs=[incidents_df])
        distill_btn.click(
            fn=on_distill,
            inputs=[],
            outputs=[distill_status, distill_modal, proposals_md, proposal_diff, distill_modal],
        )

    return panel
