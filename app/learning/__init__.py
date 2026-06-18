"""app.learning — failure-to-infrastructure feedback loop.

Public API:
    write_incident     — write a structured incident to YAML + SQLite (C2)
    distill_incidents  — distil un-processed incidents into PR-ready proposals (D3)
    ProposedRemediation — Pydantic model for a distiller proposal (D3)
"""

from app.domain.models import ProposedRemediation
from app.learning.incident_distiller import distill_incidents
from app.learning.incident_logger import write_incident

__all__ = ["write_incident", "distill_incidents", "ProposedRemediation"]
