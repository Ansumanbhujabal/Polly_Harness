"""Minimal incident logger stub — ships with C2 to satisfy the fail-closed pipeline dependency.

# TODO(D3): distill_incidents lives in incident_distiller.py — placeholder shipped with C2
#           for fail-closed pipeline. D3 will expand this with the full distiller logic
#           that reads from data/incidents/, summarises patterns, and proposes skill/policy
#           updates as PR-ready diffs.

Public API:
    write_incident(triggered_by, layer, summary, detail, *, conversation_id, incident_id=None)
        -> str  (incident_id)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml

from app.domain.models import IncidentRecord, LayerName
from app.observability import get_emitter


def _get_incidents_dir() -> Path:
    """Return the incidents directory, creating it if needed.

    Deferred import so monkeypatching settings.INCIDENTS_DIR in tests works correctly.
    """
    from app.config import settings

    incidents_dir = Path(settings.INCIDENTS_DIR)
    incidents_dir.mkdir(parents=True, exist_ok=True)
    return incidents_dir


def _get_repo():  # type: ignore[return]
    """Lazy import to allow test monkeypatching of get_repository."""
    from app.state import get_repository

    return get_repository()


def write_incident(
    triggered_by: Literal[
        "verification_failure",
        "hitl_override",
        "tool_failure",
        "injection_detected",
    ],
    layer: LayerName,
    summary: str,
    detail: dict[str, Any],
    *,
    conversation_id: str,
    incident_id: str | None = None,
) -> str:
    """Write a structured incident to YAML + SQLite and emit an INCIDENT_LOOP event.

    Args:
        triggered_by: What triggered this incident.
        layer: The harness layer where the incident originated.
        summary: One-line human-readable summary.
        detail: Structured detail dict (check name, payload, etc.).
        conversation_id: The active conversation ID.
        incident_id: Optional — generated as a UUID4 if not supplied.

    Returns:
        The incident_id (generated or passed in).
    """
    if incident_id is None:
        incident_id = str(uuid.uuid4())

    now = datetime.utcnow()
    short_id = incident_id[:8]

    # Derive a safe filename segment from the summary
    # e.g. "injection_check failed: ..." -> "injection_check"
    reason_slug = summary.split(":")[0].strip().replace(" ", "_").lower()[:40]
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp_str}_{reason_slug}_{short_id}.yaml"

    record = IncidentRecord(
        incident_id=incident_id,
        conversation_id=conversation_id,
        triggered_by=triggered_by,
        layer=layer,
        summary=summary,
        detail=detail,
        created_at=now,
    )

    # Write YAML file
    incidents_dir = _get_incidents_dir()
    yaml_path = incidents_dir / filename
    yaml_path.write_text(
        yaml.safe_dump(
            {
                "incident_id": incident_id,
                "conversation_id": conversation_id,
                "triggered_by": triggered_by,
                "layer": layer.value if hasattr(layer, "value") else str(layer),
                "summary": summary,
                "detail": detail,
                "created_at": now.isoformat(),
            },
            allow_unicode=True,
            default_flow_style=False,
        )
    )

    # Persist to SQLite via repository
    try:
        repo = _get_repo()
        repo.save_incident(record)
    except Exception:  # noqa: BLE001 — incident logger must never raise into caller
        pass

    # Emit observability event
    try:
        get_emitter().emit(
            conversation_id=conversation_id,
            layer=LayerName.INCIDENT_LOOP,
            event_type="incident_written",
            payload={
                "incident_id": incident_id,
                "triggered_by": triggered_by,
                "summary": summary,
                "layer": layer.value if hasattr(layer, "value") else str(layer),
            },
        )
    except Exception:  # noqa: BLE001
        pass

    return incident_id
