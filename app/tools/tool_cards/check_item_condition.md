# Tool: check_item_condition

**Layer:** L3 — Tool Interfaces

Read the warehouse-attested item condition from the order and map it to a refund eligibility verdict per policy. The `item_condition_reported` field on the order is the authoritative source — customer attestation alone does not override it. The tool first checks whether the item's category is in the non-refundable set (POLICY-004: `final_sale`, `digital_download`, `personal_care_opened`, `custom_made`, `perishable`). If not non-refundable, it maps the condition string to an eligibility verdict: `damaged_on_arrival` or `defective` → `full_refund_if_within_14d` (POLICY-009), `used` → `partial_50_within_window` (POLICY-008), `opened_unused` → `full_refund_if_within_14d_or_75pct_vip` (POLICY-007), `new_unopened` → `full_refund` (POLICY-006), `defect_discovered_post_use` → `store_credit_escalate` (POLICY-011).

**Inputs:** `order: Order`
**Output:** `{condition: str, eligibility: str, applied_clause: str}`
**Failure modes:** Unknown condition strings map to `eligibility="unknown_condition"` with clause `POLICY-006` as a conservative default. No exception is raised.
**Emits:** `L3_TOOLS / tool_invoked` with `{condition, eligibility, applied_clause}`.
