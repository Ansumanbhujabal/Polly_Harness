"""app.learning — failure-to-infrastructure feedback loop.

Public API (C2 stub; D3 will expand with distiller):
    write_incident — write a structured incident to YAML + SQLite

# TODO(D3): distill_incidents lives in incident_distiller.py — placeholder shipped with C2
#           for fail-closed pipeline.
"""

from app.learning.incident_logger import write_incident

__all__ = ["write_incident"]
