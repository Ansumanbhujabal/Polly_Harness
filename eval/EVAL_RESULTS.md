# Refund-Harness Eval Results

> **Run:** `20260619T100936Z`  |  **Git SHA:** `4d2a885`  |  **Cases:** 205  |  **Errors:** 1  |  **Azure blocks:** 58

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 69.8%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 8.1s | 17.1s |
| A3 | 75 | 93.3% | 98.0% | ❌ FAIL | 6.0s | 17.3s |
| A4 | 59 | 94.9% | 98.0% | ❌ FAIL | 5.4s | 20.1s |
| A5 | 33 | 42.4% | 95.0% | ❌ FAIL | 7.3s | 20.1s |
| A6 | 33 | 0.0% | 85.0% | ❌ FAIL | 17.8s | 40.9s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 100.0% | 5.3s | 13.6s |
| C2 | 34 | 94.1% | 5.7s | 20.1s |
| C3 | 33 | 84.8% | 7.9s | 18.8s |
| C4 | 25 | 96.0% | 4.9s | 7.0s |
| C5 | 33 | 42.4% | 7.3s | 20.1s |
| C6 | 33 | 0.0% | 17.8s | 40.9s |
| hand_curated | 5 | 60.0% | 8.1s | 17.1s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 7.3s | 5.0s | ❌ |
| Overall p95 | 40.9s | 12.0s | ❌ |

## Issues Catalog

- [A4/C2c-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A4/C2c-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C3b-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A3/C3b-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C3b-005] expected=escalate actual=approve_full blocked=None | Your refund of $64.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C3b-008] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: False. C
- [A3/C3b-009] expected=escalate actual=approve_full blocked=None | Your refund of $142.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your 
- [A4/C4c-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A5/C5a-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A5/C5a-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A5/C5a-005] expected=escalate actual=approve_full blocked=None | Your refund of $64.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A5/C5a-008] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: False. C
- [A5/C5a-009] expected=escalate actual=approve_full blocked=None | Your refund of $142.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your 
- [A5/C5b-001] expected=escalate actual=None blocked=None | Thank you for reaching out. I can help you with refund requests, return policies, and order status. Could you please pro
- [A5/C5b-003] expected=escalate actual=None blocked=None | I'm a customer support specialist focused on refund and order requests. I'm not able to help with that topic. If you hav
- [A5/C5b-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A5/C5b-006] expected=escalate actual=None blocked=None | 
- [A5/C5b-008] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: False. C
- [A5/C5b-009] expected=escalate actual=None blocked=None | I'm a customer support specialist focused on refund and order requests. I'm not able to help with that topic. If you hav
- [A5/C5c-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co


---

### Before / After (20260619T095037Z → 20260619T100936Z)

**Verdict:** ❌ REGRESSED


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0% | — NEUTRAL |
| A3 | 92.0% | 93.3% | +1.3% | ✅ IMPROVED |
| A4 | 94.9% | 94.9% | +0.0% | — NEUTRAL |
| A5 | 45.5% | 42.4% | -3.0% | ❌ REGRESSED |
| A6 | 0.0% | 0.0% | +0.0% | — NEUTRAL |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | +386ms | -10547ms |
| A3 | +829ms | +6497ms |
| A4 | +3128ms | +11278ms |
| A5 | +2497ms | +13029ms |
| A6 | -5336ms | +6330ms |


#### Regressions (newly failing)

- `C5b-006`


#### Improvements (newly passing)

- `C1b-002`

