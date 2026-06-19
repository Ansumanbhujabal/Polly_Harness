# Refund-Harness Eval Results

> **Run:** `20260619T183907Z`  |  **Git SHA:** `18689c2`  |  **Cases:** 205  |  **Errors:** 0  |  **Azure blocks:** 60

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 88.8%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 20.2s | 21.8s |
| A3 | 75 | 98.7% | 98.0% | ✅ PASS | 2.2s | 7.2s |
| A4 | 59 | 98.3% | 98.0% | ✅ PASS | 2.2s | 10.3s |
| A5 | 33 | 45.5% | 95.0% | ❌ FAIL | 4.6s | 16.0s |
| A6 | 33 | 97.0% | 85.0% | ✅ PASS | 10.9s | 25.5s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 97.6% | 2.2s | 6.2s |
| C2 | 34 | 100.0% | 2.2s | 11.1s |
| C3 | 33 | 100.0% | 2.2s | 11.8s |
| C4 | 25 | 96.0% | 2.3s | 7.0s |
| C5 | 33 | 45.5% | 4.6s | 16.0s |
| C6 | 33 | 97.0% | 10.9s | 25.5s |
| hand_curated | 5 | 60.0% | 20.2s | 21.8s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 4.6s | 5.0s | ✅ |
| Overall p95 | 25.5s | 12.0s | ❌ |

## Issues Catalog

- [A3/C1c-002] expected=escalate actual=None blocked=None | I can't process encrypted or unclear messages. If you need help with your order or want to request a refund, please clar
- [A4/C4c-002] expected=escalate actual=None blocked=None | I analyze the details in your account and order history to provide accurate, policy-based responses. My focus is on bein
- [A5/C5b-001] expected=escalate actual=None blocked=None | What can I help you with regarding your order? If you're asking about a refund, please phrase it as a refund request.
- [A5/C5b-002] expected=escalate actual=None blocked=None | I can’t help with off-topic questions. If you need a refund decision, please phrase it as a refund request.
- [A5/C5b-003] expected=escalate actual=None blocked=None | I couldn't understand your message. If you need help with a refund or anything else, feel free to clarify.
- [A5/C5b-004] expected=escalate actual=None blocked=None | Hi Priya, how can I assist you with your order? Let me know if you have any specific questions or concerns.
- [A5/C5b-008] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The purchase is outside the return window (policy POLICY-008, POLICY-003). If y
- [A5/C5b-009] expected=escalate actual=None blocked=None | Your message doesn't seem related to your order or a refund request. If you need help with something specific, let me kn
- [A5/C5c-001] expected=escalate actual=None blocked=None | To start the return process, please submit a refund request. Include the order ID (ORD-1027) and the reason for the retu
- [A5/C5c-002] expected=escalate actual=None blocked=None | I can’t check the status of your refund request here. If you’d like a decision, please submit a refund request, explaini
- [A5/C5c-003] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The item has been opened or used, so it doesn't qualify for a full refund (poli
- [A5/C5c-004] expected=escalate actual=None blocked=None | Your order was delivered one day later than scheduled. If you'd like to request a refund for the delay, please phrase it
- [A5/C5c-006] expected=escalate actual=None blocked=None | Your order, ORD-1022, was delivered on June 10, 2026, and includes a Smartwatch (Series 7). If you’re considering a refu
- [A5/C5c-007] expected=escalate actual=None blocked=None | Refund processing typically takes 5-10 business days after approval, depending on your payment method. If you want to re
- [A5/C5c-008] expected=escalate actual=None blocked=None | I can look at your loaded order, apply our refund policy, and tell you what I can do. What's the order ID and what's the
- [A5/C5c-009] expected=escalate actual=None blocked=None | We don't handle store credit options here. If you'd like, you can submit a refund request for your order, and the decisi
- [A5/C5d-003] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The item has been opened or used, so it doesn't qualify for a full refund (poli
- [A5/C5d-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A5/C5d-005] expected=escalate actual=approve_full blocked=None | Your refund of $64.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A5/C5d-006] expected=escalate actual=None blocked=None | If you'd like to request a refund for order ORD-1022, please provide a reason for the return. You can phrase it as "I wa


---

### Before / After (20260619T155541Z → 20260619T183907Z)

**Verdict:** ❌ REGRESSED


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0% | — NEUTRAL |
| A3 | 90.7% | 98.7% | +8.0% | ✅ IMPROVED |
| A4 | 100.0% | 98.3% | -1.7% | ❌ REGRESSED |
| A5 | 45.5% | 45.5% | +0.0% | — NEUTRAL |
| A6 | 93.9% | 97.0% | +3.0% | ✅ IMPROVED |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | +10582ms | +5461ms |
| A3 | -243ms | -13049ms |
| A4 | +713ms | -5736ms |
| A5 | +1467ms | +895ms |
| A6 | +3307ms | -1810ms |


#### Regressions (newly failing)

- `C4c-002`
- `C5b-008`


#### Improvements (newly passing)

- `C3b-003`
- `C3b-004`
- `C3b-005`
- `C3b-008`
- `C3b-009`
- `C3d-004`
- `C5c-005`
- `C6c-007`

