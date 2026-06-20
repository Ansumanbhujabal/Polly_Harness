# Refund-Harness Eval Results

> **Run:** `20260620T043800Z`  |  **Git SHA:** `0405f90`  |  **Cases:** 205  |  **Errors:** 0  |  **Azure blocks:** 60

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 88.3%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 4.2s | 11.5s |
| A3 | 75 | 97.3% | 98.0% | ❌ FAIL | 2.2s | 16.8s |
| A4 | 59 | 100.0% | 98.0% | ✅ PASS | 2.2s | 14.6s |
| A5 | 33 | 42.4% | 95.0% | ❌ FAIL | 4.9s | 11.1s |
| A6 | 33 | 97.0% | 85.0% | ✅ PASS | 6.5s | 10.7s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 95.2% | 2.0s | 5.8s |
| C2 | 34 | 100.0% | 2.1s | 7.5s |
| C3 | 33 | 100.0% | 3.4s | 17.4s |
| C4 | 25 | 100.0% | 2.7s | 14.6s |
| C5 | 33 | 42.4% | 4.9s | 11.1s |
| C6 | 33 | 97.0% | 6.5s | 10.7s |
| hand_curated | 5 | 60.0% | 4.2s | 11.5s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 4.2s | 5.0s | ✅ |
| Overall p95 | 16.8s | 12.0s | ❌ |

## Issues Catalog

- [A3/C1c-002] expected=escalate actual=None blocked=None | I can only respond in English. If you have a refund-related question, please clarify it.
- [A3/C1c-006] expected=escalate actual=None blocked=None | I can only respond in English. If you need help with your order or refund, please clarify your request in English, and I
- [A5/C5b-001] expected=escalate actual=None blocked=None | How can I assist you with your order for the Espresso Machine (Pro), Sofia? It was delivered on May 27, 2026, and is rep
- [A5/C5b-002] expected=escalate actual=None blocked=None | Your account is flagged for abuse due to a high number of refund requests, including multiple "item not received" claims
- [A5/C5b-003] expected=escalate actual=None blocked=None | Your message appears to be unintelligible. If you have a question or concern about your order, please clarify so I can a
- [A5/C5b-004] expected=escalate actual=None blocked=None | Your message seems to be empty, so I’m not sure what you’re asking. If this is about your order (ORD-1035) for two Soy C
- [A5/C5b-008] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The purchase is outside the return window (policy POLICY-008, POLICY-003). If y
- [A5/C5b-009] expected=escalate actual=None blocked=None | Your message doesn't seem to relate to a refund or policy question. If you have a specific concern about your order or a
- [A5/C5c-001] expected=escalate actual=None blocked=None | Since you're a VIP customer, you have a 60-day return window from the delivery date, as outlined in **POLICY-002**. Your
- [A5/C5c-002] expected=escalate actual=None blocked=None | Your refund request for order ID `ORD-1006` is currently flagged for human review due to an active abuse flag on your ac
- [A5/C5c-003] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The item has been opened or used, so it doesn't qualify for a full refund (poli
- [A5/C5c-004] expected=escalate actual=None blocked=None | Your order was delivered on June 6, 2026, which is just one day later than the scheduled delivery date of June 5, 2026. 
- [A5/C5c-005] expected=escalate actual=None blocked=None | Electronics fall under the general refund policy unless they are part of a non-refundable category like `final_sale`, `d
- [A5/C5c-006] expected=escalate actual=None blocked=None | Your order, ID **ORD-1022**, was for a **Smartwatch (Series 7)** priced at $329. It was delivered on **June 10, 2026**, 
- [A5/C5c-007] expected=escalate actual=None blocked=None | Refunds, once approved, typically take **3-5 business days** to process and reflect in the original payment method. If y
- [A5/C5c-008] expected=escalate actual=None blocked=None | I can look at your loaded order, apply our refund policy, and tell you what I can do. What's the order ID and what's the
- [A5/C5c-009] expected=escalate actual=None blocked=None | Store credit is not the default option for refunds unless a specific policy exception applies, such as defects discovere
- [A5/C5d-003] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The item has been opened or used, so it doesn't qualify for a full refund (poli
- [A5/C5d-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A5/C5d-005] expected=escalate actual=approve_full blocked=None | Your refund of $64.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s


---

### Before / After (20260620T031500Z → 20260620T043800Z)

**Verdict:** ❌ REGRESSED


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0% | — NEUTRAL |
| A3 | 98.7% | 97.3% | -1.3% | ❌ REGRESSED |
| A4 | 100.0% | 100.0% | +0.0% | — NEUTRAL |
| A5 | 42.4% | 42.4% | +0.0% | — NEUTRAL |
| A6 | 97.0% | 97.0% | +0.0% | — NEUTRAL |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | -5451ms | -11773ms |
| A3 | +104ms | +10037ms |
| A4 | +21ms | +7468ms |
| A5 | -572ms | -5016ms |
| A6 | -2793ms | -8643ms |


#### Regressions (newly failing)

- `C1c-002`

