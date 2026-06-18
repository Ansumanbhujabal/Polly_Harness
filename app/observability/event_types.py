"""Frozen event-type registry.

Every ``(layer, event_type)`` tuple that any spec may emit MUST appear here.
No layer may emit an unlisted tuple; a unit test asserts this invariant.
"""

from __future__ import annotations

from app.domain.models import LayerName

EVENT_TYPE_CATALOG: frozenset[tuple[LayerName, str]] = frozenset(
    {
        # L1 — Instructions
        (LayerName.INSTRUCTIONS, "prompt_loaded"),
        # L2 — Context
        (LayerName.CONTEXT, "retrieval_performed"),
        (LayerName.CONTEXT, "compaction_triggered"),
        # L3 — Tools
        (LayerName.TOOLS, "tool_invoked"),
        (LayerName.TOOLS, "tool_succeeded"),
        (LayerName.TOOLS, "mcp_tool_registered"),
        # L4 — Execution
        (LayerName.EXECUTION, "tool_retry"),
        (LayerName.EXECUTION, "tool_failed"),
        (LayerName.EXECUTION, "boot_step_completed"),
        # L5 — State
        (LayerName.STATE, "write_performed"),
        (LayerName.STATE, "migration_applied"),
        # L6 — Orchestration
        (LayerName.ORCHESTRATION, "node_entered"),
        (LayerName.ORCHESTRATION, "node_exited"),
        (LayerName.ORCHESTRATION, "interrupt_raised"),
        # L7 — Subagents
        (LayerName.SUBAGENTS, "fraud_check_started"),
        (LayerName.SUBAGENTS, "fraud_check_completed"),
        # L8 — Skills
        (LayerName.SKILLS, "skill_loaded"),
        (LayerName.SKILLS, "skill_routed"),
        # L9 — Verification
        (LayerName.VERIFICATION, "check_started"),
        (LayerName.VERIFICATION, "check_passed"),
        (LayerName.VERIFICATION, "check_failed"),
        (LayerName.VERIFICATION, "pipeline_completed"),
        # Cross-cutting: Incident loop
        (LayerName.INCIDENT_LOOP, "incident_written"),
        (LayerName.INCIDENT_LOOP, "distillation_proposed"),
        # Cross-cutting: Semantic cache (feature-flag OFF by default)
        (LayerName.CACHE, "cache_hit"),
        (LayerName.CACHE, "cache_miss"),
        (LayerName.CACHE, "cache_set"),
    }
)

__all__ = ["EVENT_TYPE_CATALOG"]
