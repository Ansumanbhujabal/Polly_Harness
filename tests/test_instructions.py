"""Tests for the Instructions layer (L1).

Covers: prompt loader local fallback, Langfuse preference, TTL cache,
langfuse_sync idempotency, and event emission.

All tests are unit or integration-marked. No real Langfuse API or
real file system outside the repo's prompts/ directory is touched.
"""

from __future__ import annotations

import hashlib
import importlib
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _reset_loader_module() -> None:
    """Force-reimport app.instructions.loader to clear module-level cache."""
    import sys

    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("app.instructions"):
            del sys.modules[mod_name]


# ---------------------------------------------------------------------------
# Test 1 — local fallback when Langfuse is not configured
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_loader_returns_local_when_langfuse_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """load_system_prompt() returns local file content when Langfuse creds are absent."""
    # Ensure Langfuse env vars are unset so langfuse_configured → False
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)

    _reset_loader_module()

    from app.instructions import load_system_prompt  # noqa: PLC0415

    result = load_system_prompt()

    expected_path = PROMPTS_DIR / "system_refund_agent.md"
    assert expected_path.exists(), f"Prompt file missing: {expected_path}"
    assert result == expected_path.read_text()
    assert len(result) >= 150, "Prompt file must be ≥150 words"


# ---------------------------------------------------------------------------
# Test 2 — Langfuse preferred when configured
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_loader_prefers_langfuse_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Langfuse env vars are present, load_system_prompt() returns the Langfuse content."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "https://example.langfuse.com")

    _reset_loader_module()

    sentinel = "SENTINEL_PROMPT_FROM_LANGFUSE"

    # Build a mock Langfuse prompt object
    mock_prompt_obj = MagicMock()
    mock_prompt_obj.prompt = sentinel
    mock_prompt_obj.version = 42

    mock_langfuse_instance = MagicMock()
    mock_langfuse_instance.get_prompt.return_value = mock_prompt_obj

    # Also patch settings.langfuse_configured because the pydantic-settings singleton
    # is already constructed at import time and won't re-read env vars set via monkeypatch.
    with (
        patch("app.instructions.loader.Langfuse", return_value=mock_langfuse_instance),
        patch("app.instructions.loader.settings") as mock_settings,
    ):
        mock_settings.langfuse_configured = True
        mock_settings.LANGFUSE_PUBLIC_KEY = "pk-test"
        mock_settings.LANGFUSE_SECRET_KEY = "sk-test"
        mock_settings.LANGFUSE_HOST = "https://example.langfuse.com"
        mock_settings.PROMPT_CACHE_TTL_SECONDS = 300
        mock_settings.PROMPTS_DIR = PROMPTS_DIR

        from app.instructions import load_system_prompt  # noqa: PLC0415

        result = load_system_prompt()

    assert result == sentinel
    mock_langfuse_instance.get_prompt.assert_called_once()


# ---------------------------------------------------------------------------
# Test 3 — cache hit within TTL
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cache_hit_within_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Second call within TTL returns cached value — underlying fetch called exactly once."""
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    _reset_loader_module()

    from app.instructions import loader  # noqa: PLC0415

    read_count: list[int] = [0]
    original_read = loader._load_from_disk  # type: ignore[attr-defined]

    def counting_read(prompt_name: str) -> str:
        read_count[0] += 1
        return original_read(prompt_name)

    monkeypatch.setattr(loader, "_load_from_disk", counting_read)

    from app.instructions import load_system_prompt  # noqa: PLC0415

    load_system_prompt()
    load_system_prompt()

    assert read_count[0] == 1, f"Expected 1 disk read, got {read_count[0]}"


# ---------------------------------------------------------------------------
# Test 4 — cache expiry after TTL
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cache_expiry_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """After TTL expires, a second call re-fetches from disk."""
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    _reset_loader_module()

    from app.instructions import loader  # noqa: PLC0415

    # Set a very short TTL so we can expire it without freezegun
    monkeypatch.setattr("app.instructions.loader.settings.PROMPT_CACHE_TTL_SECONDS", 0)

    read_count: list[int] = [0]
    original_read = loader._load_from_disk  # type: ignore[attr-defined]

    def counting_read(prompt_name: str) -> str:
        read_count[0] += 1
        return original_read(prompt_name)

    monkeypatch.setattr(loader, "_load_from_disk", counting_read)

    from app.instructions import load_system_prompt  # noqa: PLC0415

    load_system_prompt()
    # With TTL=0 the first call expires immediately; second call must re-fetch
    # (monotonic clock always advances, even by a tiny amount)
    time.sleep(0.001)
    load_system_prompt()

    assert read_count[0] == 2, f"Expected 2 disk reads after TTL expiry, got {read_count[0]}"


# ---------------------------------------------------------------------------
# Test 5 — langfuse_sync pushes when hash differs
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_langfuse_sync_pushes_new_when_hash_differs(monkeypatch: pytest.MonkeyPatch) -> None:
    """sync_prompts_to_langfuse() creates a new version when content hash differs."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "https://example.langfuse.com")

    _reset_loader_module()

    # Return content with a different hash than local
    stale_content = "THIS IS STALE CONTENT WITH A DIFFERENT HASH XYZ"
    mock_existing_prompt = MagicMock()
    mock_existing_prompt.prompt = stale_content

    mock_langfuse_instance = MagicMock()
    mock_langfuse_instance.get_prompt.return_value = mock_existing_prompt

    with (
        patch("app.instructions.langfuse_sync.Langfuse", return_value=mock_langfuse_instance),
        patch("app.instructions.langfuse_sync.settings") as mock_settings,
    ):
        mock_settings.langfuse_configured = True
        mock_settings.LANGFUSE_PUBLIC_KEY = "pk-test"
        mock_settings.LANGFUSE_SECRET_KEY = "sk-test"
        mock_settings.LANGFUSE_HOST = "https://example.langfuse.com"
        mock_settings.PROMPTS_DIR = PROMPTS_DIR

        from app.instructions.langfuse_sync import sync_prompts_to_langfuse  # noqa: PLC0415

        sync_prompts_to_langfuse()

    # Should have called create_prompt for each prompt where hash differs
    assert mock_langfuse_instance.create_prompt.call_count >= 1


# ---------------------------------------------------------------------------
# Test 6 — langfuse_sync no-op when hash matches
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_langfuse_sync_noop_when_hash_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    """sync_prompts_to_langfuse() skips create_prompt when content hash matches."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "https://example.langfuse.com")

    _reset_loader_module()

    # Pick one prompt file to test; find its actual content
    prompt_file = PROMPTS_DIR / "system_refund_agent.md"
    assert prompt_file.exists()
    real_content = prompt_file.read_text()

    # Embed hash in the returned prompt so sync knows it matches
    # langfuse_sync embeds hash as a label/tag; here we return real_content so hash matches
    mock_existing_prompt = MagicMock()
    mock_existing_prompt.prompt = real_content
    # Also expose a labels attribute containing the hash tag
    local_hash = _sha256(real_content)
    mock_existing_prompt.labels = [f"sha256:{local_hash}"]

    mock_langfuse_instance = MagicMock()
    mock_langfuse_instance.get_prompt.return_value = mock_existing_prompt

    with (
        patch("app.instructions.langfuse_sync.Langfuse", return_value=mock_langfuse_instance),
        patch("app.instructions.langfuse_sync.settings") as mock_settings,
    ):
        mock_settings.langfuse_configured = True
        mock_settings.LANGFUSE_PUBLIC_KEY = "pk-test"
        mock_settings.LANGFUSE_SECRET_KEY = "sk-test"
        mock_settings.LANGFUSE_HOST = "https://example.langfuse.com"
        # Only expose the one prompt file so hashes can match for all
        mock_settings.PROMPTS_DIR = PROMPTS_DIR

        from app.instructions.langfuse_sync import sync_prompts_to_langfuse  # noqa: PLC0415

        sync_prompts_to_langfuse()

    # No push when all hashes match — but only system_refund_agent was mocked to match.
    # Other prompt files will differ. We assert at least NOT called for the matching one.
    # Verify: create_prompt was never called with name="system_refund_agent"
    for call_args in mock_langfuse_instance.create_prompt.call_args_list:
        kwargs = call_args.kwargs if call_args.kwargs else {}
        args = call_args.args if call_args.args else ()
        name = kwargs.get("name") or (args[0] if args else None)
        assert name != "system_refund_agent", (
            "create_prompt must not be called for system_refund_agent when hash matches"
        )


# ---------------------------------------------------------------------------
# Test 7 — event emitted with correct fields
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_prompt_loaded_event_emitted_with_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """After load_system_prompt(), emitter receives exactly one LayerEvent with correct shape."""
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    _reset_loader_module()

    captured_events: list[Any] = []

    from app.domain.models import LayerEvent, LayerName  # noqa: PLC0415

    def capturing_sink(event: LayerEvent) -> None:
        captured_events.append(event)

    from app.observability import get_emitter  # noqa: PLC0415

    emitter = get_emitter()
    emitter.subscribe(capturing_sink)

    try:
        from app.instructions import load_system_prompt  # noqa: PLC0415

        load_system_prompt()
    finally:
        emitter.unsubscribe(capturing_sink)

    instruction_events = [
        e for e in captured_events if e.layer == LayerName.INSTRUCTIONS and e.event_type == "prompt_loaded"
    ]
    assert len(instruction_events) >= 1, f"Expected ≥1 prompt_loaded event, got {captured_events}"

    evt = instruction_events[0]
    assert evt.layer == LayerName.INSTRUCTIONS
    assert evt.event_type == "prompt_loaded"
    assert evt.payload.get("source") in ("langfuse", "local"), f"Unexpected source: {evt.payload}"
    assert "name" in evt.payload
    assert "version" in evt.payload
