# Tool: check_return_window

**Layer:** L3 — Tool Interfaces

Calculate how many days have elapsed since the confirmed delivery date and determine whether the order is still within the applicable return window. Applies three policy clauses in order: POLICY-001 (standard customers: 14-day window), POLICY-002 (VIP-tier customers: 60-day window), and POLICY-010 (carrier delay extension: if the carrier's confirmed delivery is more than 5 calendar days after the scheduled delivery, the return window is extended by the full delay duration). The `applied_clause` field in the output identifies which clause(s) drove the decision, enabling downstream citation.

**Inputs:** `order: Order`, `customer: Customer`
**Output:** `{within_window: bool, days_since_delivery: int, applied_clause: str}`
**Failure modes:** If `delivery_date` is `None` on the order, returns `{within_window: False, days_since_delivery: -1, applied_clause: "NOT_DELIVERED"}`. No exception is raised.
**Emits:** `L3_TOOLS / tool_invoked` with `{days_since_delivery, effective_window, within_window, applied_clause}`.
