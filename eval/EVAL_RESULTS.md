# Refund-Harness Eval Results

> **Run:** `20260619T051949Z`  |  **Git SHA:** `32985f8`  |  **Cases:** 205  |  **Errors:** 0  |  **Azure blocks:** 58

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 28.3%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 20.0% | 95.0% | ❌ FAIL | 1.1s | 6.7s |
| A3 | 75 | 34.7% | 98.0% | ❌ FAIL | 6.8s | 17.1s |
| A4 | 59 | 52.5% | 98.0% | ❌ FAIL | 3.3s | 13.5s |
| A5 | 33 | 0.0% | 95.0% | ❌ FAIL | 7.5s | 16.8s |
| A6 | 33 | 0.0% | 85.0% | ❌ FAIL | 14.5s | 19.0s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 59.5% | 3.8s | 17.1s |
| C2 | 34 | 61.8% | 2.4s | 11.7s |
| C3 | 33 | 3.0% | 8.4s | 16.7s |
| C4 | 25 | 40.0% | 5.1s | 13.5s |
| C5 | 33 | 0.0% | 7.5s | 16.8s |
| C6 | 33 | 0.0% | 14.5s | 19.0s |
| hand_curated | 5 | 20.0% | 1.1s | 6.7s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 6.8s | 5.0s | ❌ |
| Overall p95 | 19.0s | 12.0s | ❌ |

## Issues Catalog

- [A3/C1b-002] expected=escalate actual=escalate blocked=None | Your request has been escalated to a human agent who will review your case. You will receive a response within 1-2 busin
- [A3/C1b-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A3/C1b-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C1b-005] expected=escalate actual=approve_full blocked=None | Your refund of $64.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C1b-007] expected=escalate actual=escalate blocked=None | Your request has been escalated to a human agent who will review your case. You will receive a response within 1-2 busin
- [A3/C1b-008] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: False. C
- [A3/C1b-009] expected=escalate actual=approve_full blocked=None | Your refund of $142.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your 
- [A3/C1c-002] expected=escalate actual=escalate blocked=None | Your request has been escalated to a human agent who will review your case. You will receive a response within 1-2 busin
- [A3/C1c-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A3/C1c-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C1c-006] expected=escalate actual=None blocked=None | 
- [A3/C1c-007] expected=escalate actual=escalate blocked=None | Your request has been escalated to a human agent who will review your case. You will receive a response within 1-2 busin
- [A3/C1c-008] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: False. C
- [A3/C1e-002] expected=escalate actual=escalate blocked=None | Your request has been escalated to a human agent who will review your case. You will receive a response within 1-2 busin
- [A3/C1e-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A3/C1e-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C1e-005] expected=escalate actual=approve_full blocked=None | Your refund of $64.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A4/C2a-002] expected=escalate actual=escalate blocked=None | Your request has been escalated to a human agent who will review your case. You will receive a response within 1-2 busin
- [A4/C2a-007] expected=escalate actual=escalate blocked=None | Your request has been escalated to a human agent who will review your case. You will receive a response within 1-2 busin
- [A4/C2a-008] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: False. C


---

### Before / After (20260619T044023Z → 20260619T051949Z)

**Verdict:** ⬜ NEUTRAL


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 20.0% | 20.0% | +0.0% | — NEUTRAL |
| A3 | 34.7% | 34.7% | +0.0% | — NEUTRAL |
| A4 | 52.5% | 52.5% | +0.0% | — NEUTRAL |
| A5 | 0.0% | 0.0% | +0.0% | — NEUTRAL |
| A6 | 0.0% | 0.0% | +0.0% | — NEUTRAL |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | -147ms | +450ms |
| A3 | -444ms | -3151ms |
| A4 | -189ms | +8ms |
| A5 | -724ms | -1068ms |
| A6 | +6929ms | +142ms |


_No case-level changes._

