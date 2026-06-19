# Refund-Harness Eval Results

> **Run:** `20260619T103351Z`  |  **Git SHA:** `f7a94bd`  |  **Cases:** 205  |  **Errors:** 0  |  **Azure blocks:** 58

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 77.6%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 6.2s | 7.7s |
| A3 | 75 | 93.3% | 98.0% | ❌ FAIL | 6.5s | 22.1s |
| A4 | 59 | 94.9% | 98.0% | ❌ FAIL | 4.6s | 20.1s |
| A5 | 33 | 45.5% | 95.0% | ❌ FAIL | 6.0s | 23.6s |
| A6 | 33 | 45.5% | 85.0% | ❌ FAIL | 11.8s | 20.5s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 100.0% | 2.2s | 12.4s |
| C2 | 34 | 94.1% | 5.2s | 20.1s |
| C3 | 33 | 84.8% | 7.7s | 23.1s |
| C4 | 25 | 96.0% | 4.6s | 17.1s |
| C5 | 33 | 45.5% | 6.0s | 23.6s |
| C6 | 33 | 45.5% | 11.8s | 20.5s |
| hand_curated | 5 | 60.0% | 6.2s | 7.7s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 6.2s | 5.0s | ❌ |
| Overall p95 | 23.6s | 12.0s | ❌ |

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

### Before / After (20260619T102409Z → 20260619T103351Z)

**Verdict:** ✅ IMPROVED


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0% | — NEUTRAL |
| A3 | 93.3% | 93.3% | +0.0% | — NEUTRAL |
| A4 | 94.9% | 94.9% | +0.0% | — NEUTRAL |
| A5 | 45.5% | 45.5% | +0.0% | — NEUTRAL |
| A6 | 0.0% | 45.5% | +45.5% | ✅ IMPROVED |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | -1936ms | -11118ms |
| A3 | +1698ms | +7596ms |
| A4 | +3322ms | +12636ms |
| A5 | +399ms | +12825ms |
| A6 | -8305ms | -15500ms |


#### Improvements (newly passing)

- `C6a-001`
- `C6a-002`
- `C6a-006`
- `C6a-007`
- `C6b-001`
- `C6b-002`
- `C6b-006`
- `C6b-007`
- `C6c-001`
- `C6c-002`
- `C6c-006`
- `C6c-007`
- `C6d-001`
- `C6d-002`
- `C6d-006`

