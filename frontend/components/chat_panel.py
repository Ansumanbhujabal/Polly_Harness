"""Chat panel factory — gr.Blocks with chatbot, input, and optional demo chips."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import gradio as gr
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SEED_PROMPTS_PATH = REPO_ROOT / "data" / "demo" / "seed_prompts.json"


def _load_demo_prompts() -> list[dict[str, str]]:
    """Load seed_prompts.json; return empty list on any error."""
    try:
        with SEED_PROMPTS_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)  # type: ignore[no-any-return]
    except Exception:  # noqa: BLE001
        return []


def chat_panel_factory() -> gr.Blocks:
    """Build and return the Chat tab as a gr.Blocks.

    Contains:
    - gr.State for conversation_id
    - gr.Markdown for conversation_id display
    - gr.HTML approval banner (hidden by default)
    - gr.Chatbot for the conversation history
    - gr.Textbox for user input
    - Optional demo-mode chips (3 buttons, shown only when settings.DEMO_MODE=True)
    """
    demo_prompts = _load_demo_prompts() if settings.DEMO_MODE else []

    with gr.Blocks(title="Refund Agent — Chat") as panel:
        # Persistent state
        conversation_id_state = gr.State(value=None)

        # Debug / support line
        conv_id_display = gr.Markdown(
            value="_No conversation started yet._",
            label="Conversation ID",
        )

        # Approval banner — hidden until SSE fires interrupt_raised
        approval_banner = gr.HTML(
            value="",
            visible=False,
            elem_id="approval-banner",
        )

        # Main chat history
        chatbot = gr.Chatbot(
            label="Refund Agent",
            layout="bubble",
            height=420,
        )

        # User input row
        with gr.Row():
            msg_input = gr.Textbox(
                placeholder="Describe your refund request…",
                label="Your message",
                scale=8,
                submit_btn=True,
            )

        # Demo-mode chips (first 3 prompts from seed_prompts.json)
        if settings.DEMO_MODE and demo_prompts:
            gr.Markdown("**Try one of these:**")
            with gr.Row():
                for entry in demo_prompts[:3]:
                    chip = gr.Button(value=entry["label"], size="sm")

                    # Clicking the chip fills the input textbox
                    def _make_fill(prompt: str) -> Any:
                        def _fill() -> str:
                            return prompt

                        return _fill

                    chip.click(
                        fn=_make_fill(entry["prompt"]),
                        inputs=[],
                        outputs=[msg_input],
                    )

        # ---------------------------------------------------------------------------
        # Submit handler
        # ---------------------------------------------------------------------------

        async def on_submit(
            message: str,
            history: list[dict[str, str]],
            conv_id: str | None,
        ) -> tuple[list[dict[str, str]], str | None, str, str, dict[str, Any]]:
            """POST to /api/v1/chat, update chatbot history and conversation_id."""
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
                logger.error("chat_panel on_submit error: %s", exc)
                error_msg = f"Error communicating with agent: {exc}"
                history = list(history) + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": error_msg},
                ]
                return history, conv_id, "", f"_Error — no conversation_id_", gr.update(visible=False)  # type: ignore[return-value]

            returned_conv_id: str = data.get("conversation_id", conv_id or "")
            summary = data.get("final_state_summary", {})
            agent_reply: str = summary.get("response_text") or "(no response text)"

            history = list(history) + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": agent_reply},
            ]

            awaiting = summary.get("awaiting_human_approval", False)
            approval_id = summary.get("approval_id", "")
            if awaiting:
                banner_html = (
                    f'<div class="approval-banner-visible">'
                    f"Approval required for approval_id={approval_id}. "
                    f"Switch to the Admin tab &rarr; Pending Approvals."
                    f"</div>"
                )
                banner_update = gr.update(value=banner_html, visible=True)
            else:
                banner_update = gr.update(value="", visible=False)

            conv_id_md = f"_Conversation ID: `{returned_conv_id}`_"

            return history, returned_conv_id, "", conv_id_md, banner_update  # type: ignore[return-value]

        msg_input.submit(
            fn=on_submit,
            inputs=[msg_input, chatbot, conversation_id_state],
            outputs=[chatbot, conversation_id_state, msg_input, conv_id_display, approval_banner],
        )

    return panel
