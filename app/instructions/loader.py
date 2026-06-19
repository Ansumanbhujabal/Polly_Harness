"""Prompt loader with local-disk fallback and in-memory TTL cache.

Resolution order:
  1. If settings.langfuse_configured is True → fetch from Langfuse prompt registry.
  2. Else → read from local prompts/<name>.md.

Both paths populate a module-level TTL cache keyed on (prompt_name, version).
The cache entry expires after settings.PROMPT_CACHE_TTL_SECONDS seconds
(monotonic clock). On expiry the next call re-fetches and refreshes the entry.

Internal helpers are prefixed with _ and not exported from __init__.py.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from app.config import settings
from app.domain.models import LayerEvent, LayerName
from app.observability import get_emitter

# Module-level import so tests can patch `app.instructions.loader.Langfuse`.
# The import is guarded so processes without the package installed don't fail;
# in practice langfuse is always present (it is a required dependency).
try:
    from langfuse import Langfuse  # noqa: F401 — re-exported for test patching
except ImportError:  # pragma: no cover
    Langfuse = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level TTL cache: {(prompt_name, version_str): (content, fetched_at)}
# ---------------------------------------------------------------------------
_prompt_cache: dict[tuple[str, str | None], tuple[str, float]] = {}

# Tracks the last-resolved version string (used by get_prompt_version).
_last_resolved_version: str = "local-unversioned"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_last_resolved_version() -> str:
    """Return the version string resolved by the most recent loader call."""
    return _last_resolved_version


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _cache_key(name: str, version: str | None) -> tuple[str, str | None]:
    return (name, version)


def _is_cached(key: tuple[str, str | None]) -> bool:
    if key not in _prompt_cache:
        return False
    _content, fetched_at = _prompt_cache[key]
    age = time.monotonic() - fetched_at
    return age < settings.PROMPT_CACHE_TTL_SECONDS


def _put_cache(key: tuple[str, str | None], content: str) -> None:
    _prompt_cache[key] = (content, time.monotonic())


def _load_from_disk(prompt_name: str) -> str:
    """Read a prompt file from the local prompts/ directory."""
    prompt_path: Path = settings.PROMPTS_DIR / f"{prompt_name}.md"
    if not prompt_path.exists():
        raise RuntimeError(
            f"Local prompt file not found: {prompt_path}. "
            "Langfuse is also unconfigured — cannot load prompt."
        )
    return prompt_path.read_text(encoding="utf-8")


def _load_from_langfuse(prompt_name: str, version: str | None) -> tuple[str, str]:
    """Fetch a prompt from Langfuse.

    Returns (content, version_str).
    Raises any Langfuse exception to the caller — caller handles fallback.
    """
    client = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )
    kwargs: dict[str, Any] = {}
    if version is not None:
        kwargs["version"] = version

    prompt_obj = client.get_prompt(prompt_name, **kwargs)
    content: str = prompt_obj.prompt  # type: ignore[attr-defined]
    resolved_version: str = str(getattr(prompt_obj, "version", "langfuse-latest"))
    return content, resolved_version


def _resolve_prompt(prompt_name: str, version: str | None) -> tuple[str, str, str]:
    """Core resolution logic. Returns (content, version_str, source)."""
    global _last_resolved_version

    key = _cache_key(prompt_name, version)

    # Cache hit
    if _is_cached(key):
        logger.debug("prompt_cache_hit", extra={"prompt": prompt_name, "version": version})
        content, _fetched = _prompt_cache[key]
        return content, _last_resolved_version, "cached"

    logger.debug("prompt_cache_miss", extra={"prompt": prompt_name, "version": version})

    # Langfuse path
    if settings.langfuse_configured:
        try:
            content, resolved_version = _load_from_langfuse(prompt_name, version)
            _last_resolved_version = resolved_version
            _put_cache(key, content)
            _emit_loaded_event(prompt_name, resolved_version, "langfuse")
            return content, resolved_version, "langfuse"
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "langfuse_prompt_fetch_failed",
                extra={"prompt": prompt_name, "error": str(exc)},
            )
            # Fall through to local fallback

    # Local fallback
    logger.warning(
        "Langfuse not configured — falling back to local prompts/%s.md",
        prompt_name,
    )
    content = _load_from_disk(prompt_name)
    _last_resolved_version = "local-unversioned"
    _put_cache(key, content)
    _emit_loaded_event(prompt_name, "local-unversioned", "local")
    return content, "local-unversioned", "local"


def _emit_loaded_event(name: str, version: str, source: str) -> None:
    """Emit a prompt_loaded LayerEvent through the observability spine."""
    try:
        emitter = get_emitter()
        emitter.emit(
            conversation_id="system",
            layer=LayerName.INSTRUCTIONS,
            event_type="prompt_loaded",
            payload={"name": name, "version": version, "source": source},
        )
    except Exception as exc:  # noqa: BLE001 — never let observability break the loader
        logger.warning("prompt_event_emit_failed", extra={"error": str(exc)})


# ---------------------------------------------------------------------------
# Public load functions
# ---------------------------------------------------------------------------


def load_system_prompt(prompt_name: str = "system_refund_agent", version: str | None = None) -> str:
    """Return the resolved system prompt string.

    Args:
        prompt_name: The prompt identifier in Langfuse / local prompts/<name>.md.
                     Defaults to "system_refund_agent" (the main agent prompt) for
                     backward compatibility. Sub-agents pass their own prompt name
                     (e.g. "fraud_check_subagent") to load a different prompt.
        version: Optional version string to pin Langfuse fetch. Defaults to latest.

    Langfuse-first when configured; local prompts/<prompt_name>.md otherwise.
    Raises RuntimeError only if both Langfuse and local file are absent.
    """
    content, _version, _source = _resolve_prompt(prompt_name, version)
    return content


def load_skill_router_prompt(version: str | None = None) -> str:
    """Return the intent classifier prompt used by the skill router.

    Targets the "intent_classifier" prompt in Langfuse / prompts/intent_classifier.md locally.
    """
    content, _version, _source = _resolve_prompt("intent_classifier", version)
    return content
