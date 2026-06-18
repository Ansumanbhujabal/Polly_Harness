"""Langfuse prompt registry sync.

Reads every *.md file under prompts/, computes a SHA-256 hash of the content,
compares it against the current production version in Langfuse, and pushes a
new version only when the hash differs.

Idempotent: calling this N times with the same local file content results in
exactly one Langfuse prompt version — no duplicate pushes.

Called from:
  - scripts/langfuse_bootstrap.py (manual bootstrap)
  - FastAPI lifespan when settings.LANGFUSE_PROMPT_AUTOSYNC is True

Safe to call when Langfuse is not configured — logs INFO and returns immediately.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level import so tests can patch `app.instructions.langfuse_sync.Langfuse`.
try:
    from langfuse import Langfuse  # noqa: F401 — re-exported for test patching
except ImportError:  # pragma: no cover
    Langfuse = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Hash helper
# ---------------------------------------------------------------------------


def _hash_content(content: str) -> str:
    """Return the SHA-256 hex digest of the UTF-8-encoded content string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sync_prompts_to_langfuse() -> None:
    """Read local prompts/*.md, compare SHA-256 to Langfuse, push if changed.

    No-op (with an INFO log) when settings.langfuse_configured is False.
    Never raises — all errors are caught and logged at WARNING level.
    """
    if not settings.langfuse_configured:
        logger.info(
            "langfuse_sync_skipped: Langfuse not configured "
            "(LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set)"
        )
        return

    try:
        _sync_all_prompts()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "langfuse_sync_failed",
            extra={"error": str(exc), "exc_type": type(exc).__name__},
        )


# ---------------------------------------------------------------------------
# Private implementation
# ---------------------------------------------------------------------------


def _sync_all_prompts() -> None:
    """Inner (may raise) implementation — always call via sync_prompts_to_langfuse()."""
    client = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    prompts_dir: Path = settings.PROMPTS_DIR
    prompt_files = sorted(prompts_dir.glob("*.md"))

    if not prompt_files:
        logger.warning("langfuse_sync: no prompt files found in %s", prompts_dir)
        return

    for prompt_path in prompt_files:
        prompt_name = prompt_path.stem  # e.g., "system_refund_agent"
        local_content = prompt_path.read_text(encoding="utf-8")
        local_hash = _hash_content(local_content)

        # Try to fetch the current production version from Langfuse
        remote_hash: str | None = None
        try:
            existing = client.get_prompt(prompt_name)
            remote_content: str = existing.prompt  # type: ignore[attr-defined]
            remote_hash = _hash_content(remote_content)
        except Exception as exc:  # noqa: BLE001
            # Prompt doesn't exist yet, or fetch failed — treat as "differs"
            logger.debug(
                "langfuse_sync: could not fetch remote prompt %s (%s) — will push",
                prompt_name,
                exc,
            )

        if remote_hash is None or remote_hash != local_hash:
            logger.info(
                "langfuse_sync: pushing new version of %s (hash changed or new)",
                prompt_name,
            )
            client.create_prompt(
                name=prompt_name,
                prompt=local_content,
                labels=["production", f"sha256:{local_hash}"],
            )
        else:
            logger.debug(
                "langfuse_sync: %s is up to date (hash match), skipping push",
                prompt_name,
            )
