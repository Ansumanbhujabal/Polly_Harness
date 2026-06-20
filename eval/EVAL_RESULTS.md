# Refund-Harness Eval Results

> **Run:** `20260620T011518Z`  |  **Git SHA:** `4e2ed27`  |  **Cases:** 205  |  **Errors:** 0  |  **Azure blocks:** 61

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 88.8%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 6.8s | 10.0s |
| A3 | 75 | 97.3% | 98.0% | ❌ FAIL | 3.4s | 11.7s |
| A4 | 59 | 100.0% | 98.0% | ✅ PASS | 2.1s | 8.4s |
| A5 | 33 | 45.5% | 95.0% | ❌ FAIL | 3.7s | 10.6s |
| A6 | 33 | 97.0% | 85.0% | ✅ PASS | 9.8s | 19.1s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 95.2% | 3.2s | 7.4s |
| C2 | 34 | 100.0% | 2.2s | 8.4s |
| C3 | 33 | 100.0% | 3.8s | 13.3s |
| C4 | 25 | 100.0% | 2.0s | 2.6s |
| C5 | 33 | 45.5% | 3.7s | 10.6s |
| C6 | 33 | 97.0% | 9.8s | 19.1s |
| hand_curated | 5 | 60.0% | 6.8s | 10.0s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 3.7s | 5.0s | ✅ |
| Overall p95 | 19.1s | 12.0s | ❌ |

## Issues Catalog

- [A3/C1c-002] expected=escalate actual=None blocked=None | I can't process encrypted or unclear messages. If you need help with your order or want to request a refund, please clar
- [A3/C1c-006] expected=escalate actual=None blocked=None | I can't process your message as it's written. If you want to request a refund for your order, please explain why and inc
- [A5/C5b-001] expected=escalate actual=None blocked=None | What can I help you with regarding your order? If you're asking about a refund, please phrase it as a refund request.
- [A5/C5b-002] expected=escalate actual=None blocked=None | I can answer questions about your order or our refund policy, but I can't make refund decisions here. If you want a refu
- [A5/C5b-003] expected=escalate actual=None blocked=None | I couldn't understand your message. If you have a question or need help with your order, feel free to clarify.
- [A5/C5b-004] expected=escalate actual=None blocked=None | Hi Priya, I don’t see a specific question or concern in your message. Let me know if you need help with your order or wa
- [A5/C5b-008] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The purchase is outside the return window (policy POLICY-008, POLICY-003). If y
- [A5/C5b-009] expected=escalate actual=None blocked=None | Your message doesn't seem related to your order or a refund request. If you need help with something specific, let me kn
- [A5/C5c-001] expected=escalate actual=None blocked=None | To start the return process, please submit a refund request. Include the order ID (ORD-1027) and the reason for the retu
- [A5/C5c-002] expected=escalate actual=None blocked=None | I can’t check the status of refund requests here. If you’d like a decision, please submit a refund request, explaining w
- [A5/C5c-003] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The item has been opened or used, so it doesn't qualify for a full refund (poli
- [A5/C5c-004] expected=escalate actual=None blocked=None | Your order was delivered one day later than scheduled. If you'd like to request a refund for the delay, please phrase it
- [A5/C5c-006] expected=escalate actual=None blocked=None | Your order is a Smartwatch (Series 7), delivered on June 10, 2026, in new and unopened condition. If you’re considering 
- [A5/C5c-007] expected=escalate actual=None blocked=None | Refunds typically take 5-10 business days to process, depending on your payment method. If you want to request a refund 
- [A5/C5c-008] expected=escalate actual=None blocked=None | I can look at your loaded order, apply our refund policy, and tell you what I can do. What's the order ID and what's the
- [A5/C5c-009] expected=escalate actual=None blocked=None | We don't offer store credit as an alternative to refunds. If you'd like to request a refund for your order, please let m
- [A5/C5d-003] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The item has been opened or used, so it doesn't qualify for a full refund (poli
- [A5/C5d-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A5/C5d-005] expected=escalate actual=approve_full blocked=None | Your refund of $64.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A5/C5d-006] expected=escalate actual=None blocked=None | If you'd like to request a refund for your Smartwatch (Series 7), please provide a reason for the return. You can phrase


---

### Before / After (20260619T183907Z → 20260620T011518Z)

**Verdict:** ❌ REGRESSED


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0% | — NEUTRAL |
| A3 | 98.7% | 97.3% | -1.3% | ❌ REGRESSED |
| A4 | 98.3% | 100.0% | +1.7% | ✅ IMPROVED |
| A5 | 45.5% | 45.5% | +0.0% | — NEUTRAL |
| A6 | 97.0% | 97.0% | +0.0% | — NEUTRAL |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | -13473ms | -11790ms |
| A3 | +1180ms | +4479ms |
| A4 | -152ms | -1968ms |
| A5 | -899ms | -5335ms |
| A6 | -1117ms | -6484ms |


#### Regressions (newly failing)

- `C1c-006`


#### Improvements (newly passing)

- `C4c-002`

