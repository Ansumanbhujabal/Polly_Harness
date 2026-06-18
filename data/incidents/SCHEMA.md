# Incident YAML Schema

Every incident written by `app.learning.write_incident` produces a YAML file here.
Filenames follow the pattern: `<UTC-ISO-timestamp>_<reason_slug>_<incident_id_short8>.yaml`

Example filename: `20260618_180000_policy_assertion_return_9c2c1fae.yaml`

## Fields

```yaml
incident_id: 9c2c1fae-...           # UUID4 — primary key; idempotency anchor
conversation_id: conv-abc-123       # The LangGraph thread this incident came from
triggered_by: verification_failure  # One of: verification_failure | hitl_override
                                    #          tool_failure | injection_detected
layer: L9_VERIFICATION              # LayerName value of the originating layer
summary: One-line human description.
detail:                             # Free-form structured context for the distiller
  failed_check: policy_assertion_return_window
  cited: [POLICY-001]
  expected: [POLICY-002]
created_at: 2026-06-18T18:00:00    # UTC ISO timestamp (no timezone suffix)
```

## Notes

- Files here are for **human inspection** and the Loom demo.  The distiller reads from SQLite (`incidents` table) — not from these files.
- Do not delete files manually; they are the audit trail.  The `processed_incidents` table tracks which have been distilled.
- The `detail` dict shape is open-ended: include whatever context the distiller needs to write a meaningful diff.
