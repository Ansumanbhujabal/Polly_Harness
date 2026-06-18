# Tool: escalate_to_human

**Layer:** L3 — Tool Interfaces

Mark the current conversation for human review by writing an escalation record to the `human_approvals` table in SQLite and emitting a LayerEvent. The `reason_code` must be one of the eight validated codes that map to specific policy triggers: `ABUSE_FLAG_PRESENT` (POLICY-014), `ACTIVE_CHARGEBACK` (POLICY-015), `AMOUNT_EXCEEDS_CAP` (POLICY-012), `IDENTITY_MISMATCH` (POLICY-017), `THREAT_DETECTED` (POLICY-020), `INJECTION_DETECTED` (Layer 9 detection), `FRAUD_RISK_HIGH` (POLICY-016), `OUT_OF_SCOPE` (general boundary). An invalid reason code raises `ValueError` before any database write. The orchestration layer monitors the `human_approvals` table via HITL polling; when a human resolves the escalation, the graph node resumes with the approval outcome.

**Inputs:** `conversation_id: str`, `order_id: str`, `reason_code: str`, `notes: str`
**Output:** `{escalation_id: str, reason_code: str}`
**Failure modes:** `ValueError` for an invalid reason_code (before DB write). SQLite write errors propagate as exceptions and are caught by the sandbox executor.
**Emits:** `L3_TOOLS / tool_invoked` with `{escalation_id, reason_code, order_id}`.
