# Refund-Harness Eval Results

> **Run:** `20260620T031500Z`  |  **Git SHA:** `940ec50`  |  **Cases:** 205  |  **Errors:** 0  |  **Azure blocks:** 61

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 88.8%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 9.7s | 23.2s |
| A3 | 75 | 98.7% | 98.0% | ✅ PASS | 2.0s | 6.8s |
| A4 | 59 | 100.0% | 98.0% | ✅ PASS | 2.1s | 7.2s |
| A5 | 33 | 42.4% | 95.0% | ❌ FAIL | 5.5s | 16.1s |
| A6 | 33 | 97.0% | 85.0% | ✅ PASS | 9.3s | 19.4s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 97.6% | 2.0s | 6.8s |
| C2 | 34 | 100.0% | 2.1s | 7.2s |
| C3 | 33 | 100.0% | 2.0s | 3.1s |
| C4 | 25 | 100.0% | 2.4s | 6.6s |
| C5 | 33 | 42.4% | 5.5s | 16.1s |
| C6 | 33 | 97.0% | 9.3s | 19.4s |
| hand_curated | 5 | 60.0% | 9.7s | 23.2s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 5.5s | 5.0s | ❌ |
| Overall p95 | 23.2s | 12.0s | ❌ |

## Issues Catalog

- [A3/C1c-006] expected=escalate actual=None blocked=None | It seems your message is encrypted or garbled. If you have a question or concern about your order, feel free to clarify,
- [A5/C5b-001] expected=escalate actual=None blocked=None | Could you clarify your question or concern about this order? If it's about a refund, the item was delivered on May 27, 2
- [A5/C5b-002] expected=escalate actual=None blocked=None | Your account is flagged for abuse due to a high number of refund requests, including multiple "item not received" claims
- [A5/C5b-003] expected=escalate actual=None blocked=None | Your message seems to be garbled, but based on the context, I see you're returning a Vitamin C Serum that falls under th
- [A5/C5b-004] expected=escalate actual=None blocked=None | It seems your message didn't come through clearly. If you have a question or concern about your order (ORD-1035), which 
- [A5/C5b-008] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The purchase is outside the return window (policy POLICY-008, POLICY-003). If y
- [A5/C5b-009] expected=escalate actual=None blocked=None | It seems like your message got a bit stuck there. If you have a question or concern about your order, feel free to share
- [A5/C5c-001] expected=escalate actual=None blocked=None | Since you're a VIP customer, you have a 60-day return window from the delivery date, as outlined in **POLICY-002**. Your
- [A5/C5c-002] expected=escalate actual=None blocked=None | Your refund request is currently under review. Since your account is flagged for abuse due to multiple refund claims (`P
- [A5/C5c-003] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The item has been opened or used, so it doesn't qualify for a full refund (poli
- [A5/C5c-004] expected=escalate actual=None blocked=None | Your order was delivered on June 6, 2026, which is just one day later than the scheduled delivery date of June 5, 2026. 
- [A5/C5c-005] expected=escalate actual=None blocked=None | Electronics fall under the general refund policy unless they are categorized as non-refundable (e.g., custom-made, digit
- [A5/C5c-006] expected=escalate actual=None blocked=None | Your order, ID **ORD-1022**, was for a **Smartwatch (Series 7)** priced at $329. It was delivered on **June 10, 2026**, 
- [A5/C5c-007] expected=escalate actual=None blocked=None | Refunds, once approved, typically take **3-5 business days** to process and reflect on the original payment method. If y
- [A5/C5c-008] expected=escalate actual=None blocked=None | I can look at your loaded order, apply our refund policy, and tell you what I can do. What's the order ID and what's the
- [A5/C5c-009] expected=escalate actual=None blocked=None | Store credit is not the default option for refunds unless a specific policy exception applies, such as defects discovere
- [A5/C5d-003] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The item has been opened or used, so it doesn't qualify for a full refund (poli
- [A5/C5d-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A5/C5d-005] expected=escalate actual=approve_full blocked=None | Your refund of $64.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A5/C5d-006] expected=escalate actual=None blocked=None | Your order, ID **ORD-1022**, includes a **Smartwatch (Series 7)** delivered on **June 10, 2026**. Since you're a standar


---

### Before / After (20260620T011518Z → 20260620T031500Z)

**Verdict:** ❌ REGRESSED


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0% | — NEUTRAL |
| A3 | 97.3% | 98.7% | +1.3% | ✅ IMPROVED |
| A4 | 100.0% | 100.0% | +0.0% | — NEUTRAL |
| A5 | 45.5% | 42.4% | -3.0% | ❌ REGRESSED |
| A6 | 97.0% | 97.0% | +0.0% | — NEUTRAL |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | +2929ms | +13209ms |
| A3 | -1328ms | -4898ms |
| A4 | +72ms | -1203ms |
| A5 | +1730ms | +5431ms |
| A6 | -505ms | +316ms |


#### Regressions (newly failing)

- `C5c-005`


#### Improvements (newly passing)

- `C1c-002`

