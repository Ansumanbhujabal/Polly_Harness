"""Incident Loop Distiller — Task D3 hero feature.

Reads un-processed incidents from SQLite (older than `min_age_minutes`),
calls an Azure OpenAI LLM with a structured-output system prompt, validates
each raw proposal via Pydantic, writes proposals to data/proposals/, marks
source incidents as processed, and emits a distillation_proposed event.

Public API:
    distill_incidents(min_age_minutes, batch_size, *, llm, repo, proposals_dir)
        -> list[ProposedRemediation]

The `llm=`, `repo=`, and `proposals_dir=` parameters exist so tests can inject
stubs without touching global singletons.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.domain.models import IncidentRecord, LayerName, ProposedRemediation
from app.observability import get_emitter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default proposals directory (relative to repo root)
# ---------------------------------------------------------------------------

_DEFAULT_PROPOSALS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "proposals"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_default_llm() -> Any:
    """Build the real AzureChatOpenAI client from settings."""
    from langchain_openai import AzureChatOpenAI

    from app.config import settings

    return AzureChatOpenAI(
        azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT_CHAT,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY,  # type: ignore[arg-type]
        api_version=settings.AZURE_OPENAI_API_VERSION,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def _get_default_repo() -> Any:
    """Return the global Repository singleton."""
    from app.state import get_repository

    return get_repository()


def _build_prompt(incidents: list[IncidentRecord]) -> str:
    """Serialise incidents as a JSON array for the LLM context."""
    records = []
    for inc in incidents:
        records.append(
            {
                "incident_id": inc.incident_id,
                "triggered_by": inc.triggered_by,
                "layer": inc.layer.value if hasattr(inc.layer, "value") else str(inc.layer),
                "summary": inc.summary,
                "detail": inc.detail,
                "created_at": inc.created_at.isoformat(),
            }
        )
    return json.dumps({"incidents": records}, indent=2, ensure_ascii=False)


def _validate_proposals(raw: list[dict[str, Any]]) -> list[ProposedRemediation]:
    """Validate each raw dict as a ProposedRemediation.  Invalid entries are skipped."""
    proposals: list[ProposedRemediation] = []
    for item in raw:
        try:
            proposals.append(ProposedRemediation(**item))
        except Exception as exc:  # noqa: BLE001
            logger.warning("distiller_proposal_invalid: %s — item: %s", exc, item)
    return proposals


def _write_proposal_file(proposal: ProposedRemediation, proposals_dir: Path) -> Path:
    """Write a proposal to proposals_dir/<timestamp>_<kind>.md."""
    proposals_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}_{proposal.kind}.md"
    path = proposals_dir / filename

    content = (
        f"# Proposed Remediation: {proposal.kind}\n\n"
        f"**Target file:** `{proposal.target_file}`\n\n"
        f"**Source incidents:** {', '.join(proposal.source_incident_ids)}\n\n"
        f"**Created at:** {proposal.created_at.isoformat()}\n\n"
        f"## Justification\n\n"
        f"{proposal.justification}\n\n"
        f"## markdown_diff\n\n"
        f"```diff\n"
        f"{proposal.markdown_diff}\n"
        f"```\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def distill_incidents(
    min_age_minutes: int = 60,
    batch_size: int = 10,
    *,
    llm: Any | None = None,
    repo: Any | None = None,
    proposals_dir: Path | None = None,
) -> list[ProposedRemediation]:
    """Read un-processed incidents, distil them via LLM, and return proposals.

    Args:
        min_age_minutes: Minimum age in minutes for an incident to be eligible.
        batch_size: Maximum number of incidents to process in one distillation run.
        llm: Optional LLM override (for testing).  Falls back to AzureChatOpenAI.
        repo: Optional Repository override (for testing).
        proposals_dir: Where to write proposal .md files.  Defaults to data/proposals/.

    Returns:
        A list of validated ProposedRemediation objects (may be empty).
    """
    # Resolve defaults
    if repo is None:
        repo = _get_default_repo()
    if proposals_dir is None:
        proposals_dir = _DEFAULT_PROPOSALS_DIR

    # 1. Fetch eligible incidents from DB
    incidents = repo.list_unprocessed_incidents(min_age_minutes=min_age_minutes)
    incidents = incidents[:batch_size]

    if not incidents:
        logger.info("distiller: no eligible incidents — skipping run")
        return []

    # 2. Load the distiller system prompt
    try:
        from app.instructions import load_system_prompt as _lsp

        from app.instructions.loader import _resolve_prompt

        system_prompt, _, _ = _resolve_prompt("distiller", None)
    except Exception:  # noqa: BLE001
        # Fallback: read the local file directly
        _local = Path(__file__).resolve().parent.parent.parent / "prompts" / "distiller.md"
        system_prompt = _local.read_text(encoding="utf-8") if _local.exists() else ""

    # 3. Build the LLM
    if llm is None:
        llm = _get_default_llm()

    # 4. Call the LLM
    user_message = _build_prompt(incidents)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    try:
        response = await llm.ainvoke(messages)
        raw_content: str = response.content
    except Exception as exc:
        logger.error("distiller_llm_call_failed: %s", exc)
        return []

    # 5. Parse + validate
    try:
        parsed = json.loads(raw_content)
        raw_proposals: list[dict[str, Any]] = parsed.get("proposals", [])
    except json.JSONDecodeError as exc:
        logger.error("distiller_json_parse_failed: %s — content: %s", exc, raw_content[:500])
        return []

    proposals = _validate_proposals(raw_proposals)

    # 6. Write proposals to disk
    for proposal in proposals:
        _write_proposal_file(proposal, proposals_dir)

    # 7. Mark source incidents as processed (idempotent)
    batch_id = str(uuid.uuid4())
    processed_ids: set[str] = set()
    for proposal in proposals:
        for inc_id in proposal.source_incident_ids:
            if inc_id not in processed_ids:
                try:
                    repo.mark_incident_processed(inc_id, batch_id=batch_id)
                    processed_ids.add(inc_id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("distiller_mark_processed_failed: %s — %s", inc_id, exc)

    # 8. Emit observability event
    all_source_ids = list(processed_ids)
    try:
        get_emitter().emit(
            conversation_id="system",
            layer=LayerName.INCIDENT_LOOP,
            event_type="distillation_proposed",
            payload={
                "num_proposals": len(proposals),
                "source_incident_ids": all_source_ids,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("distiller_emit_failed: %s", exc)

    logger.info(
        "distiller: produced %d proposals from %d incidents",
        len(proposals),
        len(incidents),
    )
    return proposals
