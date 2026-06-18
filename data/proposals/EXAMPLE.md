# Proposed Remediation: policy_clarification

**Target file:** `data/policy/refund_policy_v1.md`

**Source incidents:** `a1b2c3d4-0001-0000-0000-000000000000`, `a1b2c3d4-0002-0000-0000-000000000000`, `a1b2c3d4-0003-0000-0000-000000000000`

**Created at:** 2026-06-18T18:00:00+00:00

## Justification

Three incidents show the verification pipeline blocking on `policy_assertion_return_window`
for Premium-tier customers whose orders were delivered within a 30-day window. The current
policy only specifies windows for Standard (14 days, POLICY-001) and VIP (60 days,
POLICY-002) tiers. Premium customers fall through to the Standard cap even though business
rules intend a 30-day window for them. POLICY-024 closes this gap.

## markdown_diff

```diff
--- a/data/policy/refund_policy_v1.md
+++ b/data/policy/refund_policy_v1.md
@@ -94,6 +94,8 @@
 ## Section 10 — Change Control
 
 **POLICY-023** — Changes to this document require an ADR in `docs/decisions/` and a corresponding update to the Langfuse policy dataset used by the eval suite.
+**POLICY-024** — Grace period for Premium customers: customers with `tier=premium` (lifetime_value ≥ $1,000) receive a 30-day return window, bridging POLICY-001 (14-day standard) and POLICY-002 (60-day VIP). The agent must check `customer.tier` before falling back to POLICY-001.
+
 
 ---
 
```
