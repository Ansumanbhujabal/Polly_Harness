# Refund-Harness Eval Results

> **Run:** `20260619T053236Z`  |  **Git SHA:** `d4474f1`  |  **Cases:** 205  |  **Errors:** 0  |  **Azure blocks:** 58

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 33.2%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 20.0% | 95.0% | ❌ FAIL | 1.1s | 2.5s |
| A3 | 75 | 48.0% | 98.0% | ❌ FAIL | 7.4s | 18.5s |
| A4 | 59 | 52.5% | 98.0% | ❌ FAIL | 5.0s | 15.8s |
| A5 | 33 | 0.0% | 95.0% | ❌ FAIL | 7.7s | 19.1s |
| A6 | 33 | 0.0% | 85.0% | ❌ FAIL | 7.6s | 17.7s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 66.7% | 2.2s | 14.0s |
| C2 | 34 | 61.8% | 2.3s | 12.1s |
| C3 | 33 | 24.2% | 12.3s | 18.6s |
| C4 | 25 | 40.0% | 6.3s | 18.2s |
| C5 | 33 | 0.0% | 7.7s | 19.1s |
| C6 | 33 | 0.0% | 7.6s | 17.7s |
| hand_curated | 5 | 20.0% | 1.1s | 2.5s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 7.4s | 5.0s | ❌ |
| Overall p95 | 19.1s | 12.0s | ❌ |

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
- [A4/C2a-007] expected=escalate actual=escalate blocked=None | Your request has been escalated to a human agent who will review your case. You will receive a response within 1-2 busin
- [A4/C2a-008] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: False. C
- [A4/C2a-009] expected=escalate actual=approve_full blocked=None | Your refund of $142.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your 
- [A4/C2c-001] expected=escalate actual=None blocked=None | 
- [A4/C2c-002] expected=escalate actual=escalate blocked=None | Your request has been escalated to a human agent who will review your case. You will receive a response within 1-2 busin


---

### Before / After (20260619T051949Z → 20260619T053236Z)

**Verdict:** ✅ IMPROVED


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 20.0% | 20.0% | +0.0% | — NEUTRAL |
| A3 | 34.7% | 48.0% | +13.3% | ✅ IMPROVED |
| A4 | 52.5% | 52.5% | +0.0% | — NEUTRAL |
| A5 | 0.0% | 0.0% | +0.0% | — NEUTRAL |
| A6 | 0.0% | 0.0% | +0.0% | — NEUTRAL |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | -6ms | -4176ms |
| A3 | +591ms | +1455ms |
| A4 | +1762ms | +2359ms |
| A5 | +184ms | +2298ms |
| A6 | -6899ms | -1280ms |


#### Improvements (newly passing)

- `C1c-002`
- `C1c-007`
- `C1e-002`
- `C3a-002`
- `C3a-007`
- `C3b-002`
- `C3b-007`
- `C3c-002`
- `C3c-007`
- `C3d-002`

