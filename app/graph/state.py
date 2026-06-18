"""L6 Orchestration — AgentState re-export.

Provides a graph-side import alias so node files can do:
    from app.graph.state import AgentState
without importing from app.domain.models directly (cleaner dependency boundary).
"""

from app.domain.models import AgentState

__all__ = ["AgentState"]
