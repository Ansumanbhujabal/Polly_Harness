"""Pending Approvals panel — gr.Blocks with dataframe + Approve/Deny/View-Reasoning buttons."""

from __future__ import annotations

import logging
from typing import Any

import gradio as gr
import httpx

logger = logging.getLogger(__name__)


def approval_panel_factory() -> gr.Blocks:
    """Build and return the Pending Approvals panel as a gr.Blocks.

    Fetches from /admin/api/pending_approvals.
    Each row has Approve / Deny / View-Reasoning actions.
    On Approve or Deny, POSTs to /api/v1/approve then refreshes the table.
    """
    with gr.Blocks() as panel:
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
            refresh_btn = gr.Button("Refresh Table")

        action_result = gr.Markdown(value="")
        reasoning_box = gr.Textbox(
            label="Reasoning (read-only)",
            interactive=False,
            visible=False,
            lines=6,
        )

        # ---------------------------------------------------------------------------
        # Helpers
        # ---------------------------------------------------------------------------

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

        async def _resolve(approval_id: str, resolution: str, approver: str) -> tuple[str, list[list[Any]]]:
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

        async def on_refresh() -> list[list[Any]]:
            return await _fetch_approvals()

        # Wire buttons
        approve_btn.click(
            fn=on_approve,
            inputs=[approval_id_input, approver_input],
            outputs=[action_result, approvals_df],
        )
        deny_btn.click(
            fn=on_deny,
            inputs=[approval_id_input, approver_input],
            outputs=[action_result, approvals_df],
        )
        refresh_btn.click(
            fn=on_refresh,
            inputs=[],
            outputs=[approvals_df],
        )

    return panel
