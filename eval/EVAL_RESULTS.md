# Refund-Harness Eval Results

> **Run:** `20260619T054312Z`  |  **Git SHA:** `ed3f04f`  |  **Cases:** 205  |  **Errors:** 0  |  **Azure blocks:** 58

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 41.0%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 2.3s | 12.9s |
| A3 | 75 | 48.0% | 98.0% | ❌ FAIL | 5.4s | 17.4s |
| A4 | 59 | 64.4% | 98.0% | ❌ FAIL | 2.6s | 12.2s |
| A5 | 33 | 21.2% | 95.0% | ❌ FAIL | 7.7s | 18.8s |
| A6 | 33 | 0.0% | 85.0% | ❌ FAIL | 8.4s | 20.5s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 66.7% | 2.3s | 13.2s |
| C2 | 34 | 73.5% | 2.4s | 9.1s |
| C3 | 33 | 24.2% | 7.6s | 17.7s |
| C4 | 25 | 52.0% | 6.9s | 12.2s |
| C5 | 33 | 21.2% | 7.7s | 18.8s |
| C6 | 33 | 0.0% | 8.4s | 20.5s |
| hand_curated | 5 | 60.0% | 2.3s | 12.9s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 5.4s | 5.0s | ❌ |
| Overall p95 | 20.5s | 12.0s | ❌ |

## Issues Catalog

- [A3/C1b-002] expected=escalate actual=escalate blocked=None | Your request has been escalated to a human agent who will review your case. You will receive a response within 1-2 busin
- [A3/C1b-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A3/C1b-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C1b-005] expected=escalate actual=approve_full blocked=None | Your refund of $64.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C1b-007] expected=escalate actual=escalate blocked=None | Your request has been escalated to a human agent who will review your case. You will receive a response within 1-2 busin
- [A3/C1b-008] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: False. C
- [A3/C1b-009] expected=escalate actual=approve_full blocked=None | Your refund of $142.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your 
- [A3/C1c-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A3/C1c-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C1c-006] expected=escalate actual=None blocked=None | 
- [A3/C1c-008] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: False. C
- [A3/C1e-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A3/C1e-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C1e-005] expected=escalate actual=approve_full blocked=None | Your refund of $64.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A4/C2a-002] expected=escalate actual=escalate blocked=None | Your request has been escalated to a human agent who will review your case. You will receive a response within 1-2 busin
- [A4/C2a-008] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: False. C
- [A4/C2a-009] expected=escalate actual=approve_full blocked=None | Your refund of $142.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your 
- [A4/C2c-001] expected=escalate actual=None blocked=None | 
- [A4/C2c-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A4/C2c-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s


---

### Before / After (20260619T053236Z → 20260619T054312Z)

**Verdict:** ✅ IMPROVED


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 20.0% | 60.0% | +40.0% | ✅ IMPROVED |
| A3 | 48.0% | 48.0% | +0.0% | — NEUTRAL |
| A4 | 52.5% | 64.4% | +11.9% | ✅ IMPROVED |
| A5 | 0.0% | 21.2% | +21.2% | ✅ IMPROVED |
| A6 | 0.0% | 0.0% | +0.0% | — NEUTRAL |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | +1154ms | +10439ms |
| A3 | -1993ms | -1098ms |
| A4 | -2425ms | -3609ms |
| A5 | +1ms | -278ms |
| A6 | +796ms | +2756ms |


#### Improvements (newly passing)

- `C2a-007`
- `C2c-002`
- `C2c-006`
- `C2c-007`
- `C4b-002`
- `C4b-007`
- `C4c-007`
- `C5a-002`
- `C5a-007`
- `C5b-002`
- `C5b-007`
- `C5c-002`
- `C5c-007`
- `C5d-002`
- `case_3_serial_refunder_fraud`
- `case_4_above_cap_interrupt`

