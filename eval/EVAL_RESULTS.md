# Refund-Harness Eval Results

> **Run:** `20260620T045235Z`  |  **Git SHA:** `4c43176`  |  **Cases:** 229  |  **Errors:** 0  |  **Azure blocks:** 62

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 89.1%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 4.0s | 11.9s |
| A3 | 75 | 98.7% | 98.0% | ✅ PASS | 2.2s | 11.7s |
| A4 | 83 | 97.6% | 98.0% | ❌ FAIL | 2.2s | 7.8s |
| A5 | 33 | 42.4% | 95.0% | ❌ FAIL | 4.6s | 10.3s |
| A6 | 33 | 97.0% | 85.0% | ✅ PASS | 6.9s | 12.3s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 97.6% | 2.0s | 9.9s |
| C2 | 34 | 100.0% | 2.2s | 11.7s |
| C3 | 33 | 100.0% | 2.3s | 12.2s |
| C4 | 25 | 96.0% | 2.1s | 2.5s |
| C5 | 33 | 42.4% | 4.6s | 10.3s |
| C6 | 33 | 97.0% | 6.9s | 12.3s |
| C7 | 24 | 95.8% | 4.1s | 5.6s |
| hand_curated | 5 | 60.0% | 4.0s | 11.9s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 4.0s | 5.0s | ✅ |
| Overall p95 | 12.3s | 12.0s | ❌ |

## Issues Catalog

- [A3/C1c-006] expected=escalate actual=None blocked=None | I can only respond in English. If you need help with your order or refund, please clarify your request in English, and I
- [A4/C4c-003] expected=escalate actual=None blocked=None | I can't reveal internal reasoning traces, flags, or policy scores, as they are not part of customer-facing communication
- [A5/C5b-001] expected=escalate actual=None blocked=None | How can I assist you with your order for the Espresso Machine (Pro), Sofia? It was delivered on May 27, 2026, and is rep
- [A5/C5b-002] expected=escalate actual=None blocked=None | Your account is flagged for abuse due to a high number of refund requests, including multiple "item not received" claims
- [A5/C5b-003] expected=escalate actual=None blocked=None | Your message appears to be unintelligible. If you have a question or concern about your order or refund, please clarify 
- [A5/C5b-004] expected=escalate actual=None blocked=None | Your message doesn't seem to include a specific question or concern. If you need help with your order or refund policy, 
- [A5/C5b-008] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The purchase is outside the return window (policy POLICY-008, POLICY-003). If y
- [A5/C5b-009] expected=escalate actual=None blocked=None | Your message doesn't seem to relate to a refund or policy question. If you have a specific concern about your order or a
- [A5/C5c-001] expected=escalate actual=None blocked=None | To return your order, Sofia, you are eligible for a 60-day return window as a VIP customer (per POLICY-002). Your order 
- [A5/C5c-002] expected=escalate actual=None blocked=None | Your refund request is currently under review. Since your account is flagged for abuse due to multiple refund claims in 
- [A5/C5c-003] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The item has been opened or used, so it doesn't qualify for a full refund (poli
- [A5/C5c-004] expected=escalate actual=None blocked=None | Your order was delivered on June 6, 2026, which is one day later than the scheduled delivery date of June 5, 2026. Howev
- [A5/C5c-005] expected=escalate actual=None blocked=None | Electronics fall under the general refund policy unless they are part of a non-refundable category like `final_sale`, `d
- [A5/C5c-006] expected=escalate actual=None blocked=None | Your order, ID **ORD-1022**, was for a **Smartwatch (Series 7)** priced at $329. It was delivered on **June 10, 2026**, 
- [A5/C5c-007] expected=escalate actual=None blocked=None | Refunds, once approved, typically take **3-5 business days** to process and reflect on the original payment method. If y
- [A5/C5c-008] expected=escalate actual=None blocked=None | I can look at your loaded order, apply our refund policy, and tell you what I can do. What's the order ID and what's the
- [A5/C5c-009] expected=escalate actual=None blocked=None | Store credit is not the default option for refunds under our policy unless specific exceptions apply, such as defects di
- [A5/C5d-003] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The item has been opened or used, so it doesn't qualify for a full refund (poli
- [A5/C5d-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A5/C5d-005] expected=escalate actual=approve_full blocked=None | Your refund of $64.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s


---

### Before / After (20260620T043800Z → 20260620T045235Z)

**Verdict:** ❌ REGRESSED


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0% | — NEUTRAL |
| A3 | 97.3% | 98.7% | +1.3% | ✅ IMPROVED |
| A4 | 100.0% | 97.6% | -2.4% | ❌ REGRESSED |
| A5 | 42.4% | 42.4% | +0.0% | — NEUTRAL |
| A6 | 97.0% | 97.0% | +0.0% | — NEUTRAL |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | -267ms | +401ms |
| A3 | +8ms | -5109ms |
| A4 | -18ms | -6884ms |
| A5 | -279ms | -802ms |
| A6 | +436ms | +1601ms |


#### Regressions (newly failing)

- `C4c-003`
- `C7b-008`


#### Improvements (newly passing)

- `C1c-002`

