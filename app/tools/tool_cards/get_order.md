# Tool: get_order

**Layer:** L3 — Tool Interfaces

Fetch an order record by `order_id`, verifying that it belongs to the specified `customer_id`. The customer-scope check is a security gate: if the order exists but its `customer_id` field does not match the supplied value, the tool returns `None` rather than the order — it does not distinguish "order not found" from "order belongs to a different customer" at the return-value level. The caller (graph orchestration layer) is responsible for escalating a `None` return with reason code `IDENTITY_MISMATCH` when the agent has already established the customer identity.

**Inputs:** `order_id: str`, `customer_id: str`
**Output:** `{order: Order | None}`
**Failure modes:** Returns `{order: None}` for an unknown order_id or a customer_id mismatch. The mismatch path emits an event with `{mismatch: True}` for downstream detection.
**Emits:** `L3_TOOLS / tool_invoked` with `{order_id, found}` or `{order_id, mismatch: True}`.
