# Refund-Harness Eval Results

> **Run:** `20260619T102409Z`  |  **Git SHA:** `17df8fe`  |  **Cases:** 205  |  **Errors:** 0  |  **Azure blocks:** 58

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 70.2%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 8.1s | 18.9s |
| A3 | 75 | 93.3% | 98.0% | ❌ FAIL | 4.8s | 14.5s |
| A4 | 59 | 94.9% | 98.0% | ❌ FAIL | 1.3s | 7.5s |
| A5 | 33 | 45.5% | 95.0% | ❌ FAIL | 5.6s | 10.7s |
| A6 | 33 | 0.0% | 85.0% | ❌ FAIL | 20.1s | 36.0s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 100.0% | 4.4s | 14.5s |
| C2 | 34 | 94.1% | 1.2s | 7.5s |
| C3 | 33 | 84.8% | 4.9s | 7.2s |
| C4 | 25 | 96.0% | 5.0s | 7.4s |
| C5 | 33 | 45.5% | 5.6s | 10.7s |
| C6 | 33 | 0.0% | 20.1s | 36.0s |
| hand_curated | 5 | 60.0% | 8.1s | 18.9s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 5.6s | 5.0s | ❌ |
| Overall p95 | 36.0s | 12.0s | ❌ |

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
- [A5/C5b-004] expected=escalate actual=None blocked=None | I'm a customer support specialist focused on refund and order requests. I'm not able to help with that topic. If you hav
- [A5/C5b-008] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: False. C
- [A5/C5b-009] expected=escalate actual=None blocked=None | I'm a customer support specialist focused on refund and order requests. I'm not able to help with that topic. If you hav
- [A5/C5c-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A5/C5c-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s


---

### Before / After (20260619T100936Z → 20260619T102409Z)

**Verdict:** ✅ IMPROVED


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0% | — NEUTRAL |
| A3 | 93.3% | 93.3% | +0.0% | — NEUTRAL |
| A4 | 94.9% | 94.9% | +0.0% | — NEUTRAL |
| A5 | 42.4% | 45.5% | +3.0% | ✅ IMPROVED |
| A6 | 0.0% | 0.0% | +0.0% | — NEUTRAL |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | -29ms | +1745ms |
| A3 | -1213ms | -2750ms |
| A4 | -4078ms | -12579ms |
| A5 | -1696ms | -9369ms |
| A6 | +2357ms | -4895ms |


#### Improvements (newly passing)

- `C5b-006`

