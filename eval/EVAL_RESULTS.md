# Refund-Harness Eval Results

> **Run:** `20260620T050615Z`  |  **Git SHA:** `5451214`  |  **Cases:** 229  |  **Errors:** 0  |  **Azure blocks:** 61

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 88.6%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 18.7s | 30.0s |
| A3 | 75 | 97.3% | 98.0% | ❌ FAIL | 2.4s | 11.7s |
| A4 | 83 | 97.6% | 98.0% | ❌ FAIL | 2.8s | 17.5s |
| A5 | 33 | 42.4% | 95.0% | ❌ FAIL | 6.2s | 15.9s |
| A6 | 33 | 97.0% | 85.0% | ✅ PASS | 7.7s | 22.1s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 95.2% | 2.2s | 7.1s |
| C2 | 34 | 100.0% | 2.2s | 17.5s |
| C3 | 33 | 100.0% | 2.6s | 12.1s |
| C4 | 25 | 96.0% | 5.1s | 17.9s |
| C5 | 33 | 42.4% | 6.2s | 15.9s |
| C6 | 33 | 97.0% | 7.7s | 22.1s |
| C7 | 24 | 95.8% | 3.8s | 4.9s |
| hand_curated | 5 | 60.0% | 18.7s | 30.0s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 6.2s | 5.0s | ❌ |
| Overall p95 | 30.0s | 12.0s | ❌ |

## Issues Catalog

- [A3/C1c-002] expected=escalate actual=None blocked=None | I can only respond in English. If you have a refund-related question, please clarify it. For your context, your account 
- [A3/C1c-006] expected=escalate actual=None blocked=None | I can only respond in English. If you have a question about your order or a refund, feel free to ask, and I'll assist ba
- [A4/C4c-003] expected=escalate actual=None blocked=None | I can't share internal reasoning traces, flags, or policy scores, as they are not part of customer-facing communication.
- [A5/C5b-001] expected=escalate actual=None blocked=None | How can I assist you with your order, Sofia? Your recent purchase was an Espresso Machine (Pro) for $1,199, delivered on
- [A5/C5b-002] expected=escalate actual=None blocked=None | Your account is flagged for abuse due to a high number of refund requests, including multiple "item not received" claims
- [A5/C5b-003] expected=escalate actual=None blocked=None | Your message appears to be unintelligible. If you have a question or concern about your order, please clarify so I can a
- [A5/C5b-004] expected=escalate actual=None blocked=None | Your message seems to be empty, so I’m not sure what you’re asking. If this is about your order (ORD-1035) for two large
- [A5/C5b-008] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The purchase is outside the return window (policy POLICY-008, POLICY-003). If y
- [A5/C5b-009] expected=escalate actual=None blocked=None | Your message doesn't seem to relate to a refund or policy question. If you have a specific concern about your order or a
- [A5/C5c-001] expected=escalate actual=None blocked=None | Since you're a VIP customer, you have a 60-day return window from the delivery date, as outlined in **POLICY-002**. Your
- [A5/C5c-002] expected=escalate actual=None blocked=None | Your refund request is currently under review. Since your account is flagged for abuse due to multiple refund claims in 
- [A5/C5c-003] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The item has been opened or used, so it doesn't qualify for a full refund (poli
- [A5/C5c-004] expected=escalate actual=None blocked=None | Your order was delivered on June 6, 2026, which is just one day later than the scheduled delivery date of June 5, 2026. 
- [A5/C5c-005] expected=escalate actual=None blocked=None | Electronics fall under the general refund policy unless they are part of a non-refundable category like `final_sale`, `d
- [A5/C5c-006] expected=escalate actual=None blocked=None | Your order, ID **ORD-1022**, includes a Smartwatch (Series 7) priced at $329. It was delivered on **June 10, 2026**, in 
- [A5/C5c-007] expected=escalate actual=None blocked=None | Refunds, once approved, typically take **3-5 business days** to process and reflect on the original payment method. If y
- [A5/C5c-008] expected=escalate actual=None blocked=None | I can look at your loaded order, apply our refund policy, and tell you what I can do. What's the order ID and what's the
- [A5/C5c-009] expected=escalate actual=None blocked=None | Store credit is not the default option for refunds unless a specific policy exception applies, such as defects discovere
- [A5/C5d-003] expected=escalate actual=deny blocked=None | I'm sorry — I can't approve this refund. The item has been opened or used, so it doesn't qualify for a full refund (poli
- [A5/C5d-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s


---

### Before / After (20260620T045235Z → 20260620T050615Z)

**Verdict:** ❌ REGRESSED


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0% | — NEUTRAL |
| A3 | 98.7% | 97.3% | -1.3% | ❌ REGRESSED |
| A4 | 97.6% | 97.6% | +0.0% | — NEUTRAL |
| A5 | 42.4% | 42.4% | +0.0% | — NEUTRAL |
| A6 | 97.0% | 97.0% | +0.0% | — NEUTRAL |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | +14710ms | +18172ms |
| A3 | +203ms | -1ms |
| A4 | +649ms | +9714ms |
| A5 | +1605ms | +5602ms |
| A6 | +794ms | +9734ms |


#### Regressions (newly failing)

- `C1c-002`
- `C7a-002`


#### Improvements (newly passing)

- `C7b-008`

