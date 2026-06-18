# Tool: issue_refund

**Layer:** L3 — Tool Interfaces

Write a confirmed refund record to the durable SQLite state database and emit a LayerEvent. This tool is idempotent on `(conversation_id, order_id)`: submitting the same pair a second time returns the same `refund_id` without inserting a duplicate row, making it safe to call again after a retry or transient failure. The generated refund ID follows the format `REF-{conversation_id}-{n}` where `n` is a per-conversation sequence counter. The tool creates the `refunds` table on first use if it does not exist, matching the schema that `app.state.repositories` will own when SPEC_STATE is implemented. In production, the orchestration layer should only call this tool after the verification gate (Layer 9) has passed.

**Inputs:** `conversation_id: str`, `order_id: str`, `amount_usd: float`, `kind: RefundDecisionKind`
**Output:** `{refund_id: str, status: "issued", amount_usd: float}`
**Failure modes:** SQLite write errors propagate as exceptions (caught by the sandbox executor). Idempotency lookup is performed before any write.
**Emits:** `L3_TOOLS / tool_invoked` with `{refund_id, amount_usd, order_id}` or `{refund_id, idempotent_hit: True}` on a repeat call.
