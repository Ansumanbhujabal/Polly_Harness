"""Tests for the frontend layer (factory-shape assertions, no live Gradio server).

All five tests are marked `unit` — they only inspect code structure + static files.
No network calls or DB access.
"""

from __future__ import annotations

import json
from pathlib import Path

import gradio as gr
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Test 1 — chat_panel_factory returns a Blocks containing Chatbot + Textbox
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_chat_panel_factory_returns_blocks() -> None:
    """chat_panel_factory() must return a gr.Blocks with at least one Chatbot and one Textbox."""
    from frontend.components.chat_panel import chat_panel_factory

    blocks = chat_panel_factory()
    assert isinstance(blocks, gr.Blocks), "Expected gr.Blocks return type"

    # Walk the component tree looking for Chatbot and Textbox
    def _collect(root: gr.Blocks) -> list[object]:
        comps: list[object] = []
        for block in root.blocks.values():
            comps.append(block)
        return comps

    components = _collect(blocks)
    has_chatbot = any(isinstance(c, gr.Chatbot) for c in components)
    has_textbox = any(isinstance(c, gr.Textbox) for c in components)

    assert has_chatbot, "No gr.Chatbot found in chat_panel_factory() Blocks"
    assert has_textbox, "No gr.Textbox found in chat_panel_factory() Blocks"


# ---------------------------------------------------------------------------
# Test 2 — admin_panel_factory returns Blocks with exactly 4 nested Tab children
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_admin_panel_factory_returns_blocks_with_four_tabs() -> None:
    """admin_panel_factory() must return a gr.Blocks whose tree contains exactly 4 gr.Tab children."""
    from frontend.components.admin_panel import admin_panel_factory

    blocks = admin_panel_factory()
    assert isinstance(blocks, gr.Blocks), "Expected gr.Blocks return type"

    tab_components = [c for c in blocks.blocks.values() if isinstance(c, gr.Tab)]
    assert len(tab_components) == 4, (
        f"Expected exactly 4 gr.Tab children, got {len(tab_components)}: "
        f"{[type(c).__name__ for c in tab_components]}"
    )


# ---------------------------------------------------------------------------
# Test 3 — mermaid_diagram.html includes all 9 LayerName values as node ids
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_mermaid_diagram_html_includes_all_nine_layers() -> None:
    """frontend/static/mermaid_diagram.html must reference every LayerName value."""
    from app.domain.models import LayerName

    html_path = REPO_ROOT / "frontend" / "static" / "mermaid_diagram.html"
    assert html_path.exists(), f"Missing file: {html_path}"

    content = html_path.read_text(encoding="utf-8")

    # The 9 harness layers (INCIDENT_LOOP and CACHE are cross-cutting, not numbered layers)
    harness_layers = [
        LayerName.INSTRUCTIONS,
        LayerName.CONTEXT,
        LayerName.TOOLS,
        LayerName.EXECUTION,
        LayerName.STATE,
        LayerName.ORCHESTRATION,
        LayerName.SUBAGENTS,
        LayerName.SKILLS,
        LayerName.VERIFICATION,
    ]

    for layer in harness_layers:
        assert layer.value in content, (
            f"LayerName.{layer.name} ({layer.value!r}) not found in mermaid_diagram.html"
        )


# ---------------------------------------------------------------------------
# Test 4 — sse_listener.js subscribes to the correct URL pattern
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sse_listener_js_subscribes_to_correct_url() -> None:
    """frontend/static/sse_listener.js must contain the EventSource subscription string."""
    js_path = REPO_ROOT / "frontend" / "static" / "sse_listener.js"
    assert js_path.exists(), f"Missing file: {js_path}"

    content = js_path.read_text(encoding="utf-8")
    expected_fragment = '/events/stream?conversation_id=" + conversationId'
    assert expected_fragment in content, (
        f"Expected EventSource URL pattern not found.\n"
        f"Looking for: {expected_fragment!r}\n"
        f"File content (first 800 chars):\n{content[:800]}"
    )


# ---------------------------------------------------------------------------
# Test 5 — seed_prompts.json has exactly 5 entries matching SPEC_DEMO_SCRIPT case ids
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_demo_seed_prompts_match_five_cases() -> None:
    """data/demo/seed_prompts.json must have exactly 5 entries with the correct case_ids."""
    prompts_path = REPO_ROOT / "data" / "demo" / "seed_prompts.json"
    assert prompts_path.exists(), f"Missing file: {prompts_path}"

    with prompts_path.open(encoding="utf-8") as fh:
        entries = json.load(fh)

    assert len(entries) == 5, f"Expected 5 seed_prompt entries, got {len(entries)}"

    expected_case_ids = {
        "case_1_30_day_claim",
        "case_2_used_hygiene_non_returnable",
        "case_3_serial_refunder_fraud",
        "case_4_above_cap_interrupt",
        "case_5_injection_emotional",
    }

    actual_case_ids = {e["case_id"] for e in entries}
    assert actual_case_ids == expected_case_ids, (
        f"case_id mismatch.\nExpected: {sorted(expected_case_ids)}\nActual:   {sorted(actual_case_ids)}"
    )

    # Each entry must also have label and prompt
    for entry in entries:
        assert "label" in entry and entry["label"], f"Missing 'label' in entry {entry}"
        assert "prompt" in entry and entry["prompt"], f"Missing 'prompt' in entry {entry}"
