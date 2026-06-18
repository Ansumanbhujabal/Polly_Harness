# Tool: compute_refund_amount

**Layer:** L3 — Tool Interfaces

Pure function that applies policy math to compute the refund amount and decision kind from pre-fetched data. This tool does NOT call other tools — the caller must already have determined the `within_window` flag (via `check_return_window`) and the `eligibility` string (via `check_item_condition`). The decision tree maps eligibility + within_window + customer tier to a `RefundDecisionKind` and a `float` amount: full refund at `total_usd` for approved-full cases, 75% of `total_usd` for VIP opened-unused beyond 14 days (POLICY-007 + POLICY-002), 50% for used items within window (POLICY-008), zero for denials (POLICY-003, POLICY-004), and `total_usd` as store credit for late-defect escalations (POLICY-011). The `cited_clauses` list always contains the clause IDs that drove the calculation, suitable for inclusion in the final customer response.

**Inputs:** `order: Order`, `customer: Customer`, `within_window: bool`, `item_condition: str`, `eligibility: str`
**Output:** `{kind: RefundDecisionKind, amount_usd: float, cited_clauses: list[str]}`
**Failure modes:** Unknown eligibility strings resolve to `RefundDecisionKind.ESCALATE` with zero amount and an empty clauses list. No exception is raised.
**Emits:** `L3_TOOLS / tool_invoked` with `{kind, amount_usd, cited_clauses}`.
