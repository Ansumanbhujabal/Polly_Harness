# Refund-Harness Eval Results

> **Run:** `20260619T155541Z`  |  **Git SHA:** `74b2cc2`  |  **Cases:** 205  |  **Errors:** 0  |  **Azure blocks:** 57

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 85.9%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 9.7s | 16.4s |
| A3 | 75 | 90.7% | 98.0% | ❌ FAIL | 2.4s | 20.2s |
| A4 | 59 | 100.0% | 98.0% | ✅ PASS | 1.5s | 16.1s |
| A5 | 33 | 45.5% | 95.0% | ❌ FAIL | 3.2s | 15.1s |
| A6 | 33 | 93.9% | 85.0% | ✅ PASS | 7.6s | 27.4s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 97.6% | 1.1s | 11.0s |
| C2 | 34 | 100.0% | 1.3s | 16.5s |
| C3 | 33 | 81.8% | 8.6s | 20.2s |
| C4 | 25 | 100.0% | 2.2s | 11.1s |
| C5 | 33 | 45.5% | 3.2s | 15.1s |
| C6 | 33 | 93.9% | 7.6s | 27.4s |
| hand_curated | 5 | 60.0% | 9.7s | 16.4s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 3.2s | 5.0s | ✅ |
| Overall p95 | 27.4s | 12.0s | ❌ |

## Issues Catalog

- [A3/C1c-002] expected=escalate actual=None blocked=None | I can’t process encrypted or unclear messages. If you’re asking about a refund, please phrase it as a clear request, lik
- [A3/C3b-003] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The item has been opened or used, so it doesn't qualify for a full refund (poli
- [A3/C3b-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C3b-005] expected=escalate actual=approve_full blocked=None | Your refund of $64.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C3b-008] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The purchase is outside the return window (policy POLICY-008, POLICY-003). If y
- [A3/C3b-009] expected=escalate actual=approve_full blocked=None | Your refund of $142.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your 
- [A3/C3d-004] expected=escalate actual=None blocked=None | Our policy doesn't include automatic refunds for orders over $100, and your order total is $56. If you'd like to request
- [A5/C5b-001] expected=escalate actual=None blocked=None | What can I help you with regarding your order? If you're asking about a refund, please phrase it as a refund request.
- [A5/C5b-002] expected=escalate actual=None blocked=None | What can I help you with regarding your order? If you're asking about a refund, please phrase it as a refund request.
- [A5/C5b-003] expected=escalate actual=None blocked=None | Your message seems unclear. If you need help with your order or want to request a refund, please provide more details or
- [A5/C5b-004] expected=escalate actual=None blocked=None | Hi Priya, it seems your message didn’t come through. Let me know how I can assist you—whether it’s about your recent ord
- [A5/C5b-009] expected=escalate actual=None blocked=None | Your message doesn't seem related to your order or refund policy. If you need help with something specific, let me know.
- [A5/C5c-001] expected=escalate actual=None blocked=None | To start the return process, please submit a refund request. Include why you want to return order ORD-1027, and I'll gui
- [A5/C5c-002] expected=escalate actual=None blocked=None | I can’t check the status of refund requests here. If you’d like a decision, please submit a refund request, like “I want
- [A5/C5c-003] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The item has been opened or used, so it doesn't qualify for a full refund (poli
- [A5/C5c-004] expected=escalate actual=None blocked=None | I can't determine eligibility for a refund here, but you can request one by explaining why you'd like to return order OR
- [A5/C5c-005] expected=escalate actual=None blocked=None | Our refund policy for electronics allows returns within 30 days of delivery if the item is defective, damaged, or not as
- [A5/C5c-006] expected=escalate actual=None blocked=None | Your order is a Smartwatch (Series 7), delivered on June 10, 2026, in new and unopened condition. If you’re considering 
- [A5/C5c-007] expected=escalate actual=None blocked=None | Refunds typically take 5-10 business days to process after approval, depending on your payment method. If you want to re
- [A5/C5c-008] expected=escalate actual=None blocked=None | I can look at your loaded order, apply our refund policy, and tell you what I can do. What's the order ID and what's the


---

### Before / After (20260619T103351Z → 20260619T155541Z)

**Verdict:** ❌ REGRESSED


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0% | — NEUTRAL |
| A3 | 93.3% | 90.7% | -2.7% | ❌ REGRESSED |
| A4 | 94.9% | 100.0% | +5.1% | ✅ IMPROVED |
| A5 | 45.5% | 45.5% | +0.0% | — NEUTRAL |
| A6 | 45.5% | 93.9% | +48.5% | ✅ IMPROVED |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | +3473ms | +8626ms |
| A3 | -4096ms | -1919ms |
| A4 | -3091ms | -4056ms |
| A5 | -2863ms | -8472ms |
| A6 | -4239ms | +6868ms |


#### Regressions (newly failing)

- `C1c-002`
- `C3d-004`
- `C5b-002`
- `C5c-001`
- `C5c-002`
- `C5c-006`
- `C5c-007`
- `C5d-006`
- `C6c-007`


#### Improvements (newly passing)

- `C2c-003`
- `C2c-004`
- `C4c-003`
- `C5a-003`
- `C5a-004`
- `C5a-005`
- `C5a-008`
- `C5a-009`
- `C5b-008`
- `C6a-003`
- `C6a-004`
- `C6a-005`
- `C6a-008`
- `C6a-009`
- `C6b-003`
- `C6b-004`
- `C6b-005`
- `C6b-008`
- `C6b-009`
- `C6c-003`
- `C6c-004`
- `C6c-005`
- `C6c-008`
- `C6d-003`
- `C6d-004`
- `C6d-005`

