# Refund-Harness Eval Results

> **Run:** `20260619T060355Z`  |  **Git SHA:** `a1350b2`  |  **Cases:** 205  |  **Errors:** 0  |  **Azure blocks:** 58

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 63.4%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 3.5s | 4.9s |
| A3 | 75 | 88.0% | 98.0% | ❌ FAIL | 4.7s | 12.6s |
| A4 | 59 | 89.8% | 98.0% | ❌ FAIL | 1.1s | 5.9s |
| A5 | 33 | 24.2% | 95.0% | ❌ FAIL | 4.7s | 11.8s |
| A6 | 33 | 0.0% | 85.0% | ❌ FAIL | 13.0s | 20.7s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 95.2% | 4.5s | 13.5s |
| C2 | 34 | 88.2% | 1.1s | 5.3s |
| C3 | 33 | 78.8% | 4.7s | 6.4s |
| C4 | 25 | 92.0% | 4.4s | 7.1s |
| C5 | 33 | 24.2% | 4.7s | 11.8s |
| C6 | 33 | 0.0% | 13.0s | 20.7s |
| hand_curated | 5 | 60.0% | 3.5s | 4.9s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 4.7s | 5.0s | ✅ |
| Overall p95 | 20.7s | 12.0s | ❌ |

## Issues Catalog

- [A3/C1b-002] expected=escalate actual=escalate blocked=None | Your request has been escalated to a human agent who will review your case. You will receive a response within 1-2 busin
- [A3/C1c-006] expected=escalate actual=None blocked=None | 
- [A4/C2a-002] expected=escalate actual=escalate blocked=None | Your request has been escalated to a human agent who will review your case. You will receive a response within 1-2 busin
- [A4/C2c-001] expected=escalate actual=None blocked=None | 
- [A4/C2c-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A4/C2c-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C3b-001] expected=escalate actual=None blocked=None | 
- [A3/C3b-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A3/C3b-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C3b-005] expected=escalate actual=approve_full blocked=None | Your refund of $64.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A3/C3b-006] expected=escalate actual=None blocked=None | 
- [A3/C3b-008] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: False. C
- [A3/C3b-009] expected=escalate actual=approve_full blocked=None | Your refund of $142.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your 
- [A4/C4c-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A4/C4c-006] expected=escalate actual=None blocked=None | 
- [A5/C5a-001] expected=escalate actual=None blocked=None | 
- [A5/C5a-003] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: True. Co
- [A5/C5a-004] expected=escalate actual=approve_full blocked=None | Your refund of $56.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A5/C5a-005] expected=escalate actual=approve_full blocked=None | Your refund of $64.00 has been approved and processed. Please allow 3-5 business days for the amount to appear on your s
- [A5/C5a-006] expected=escalate actual=None blocked=None | 


---

### Before / After (20260619T054312Z → 20260619T060355Z)

**Verdict:** ✅ IMPROVED


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0% | — NEUTRAL |
| A3 | 48.0% | 88.0% | +40.0% | ✅ IMPROVED |
| A4 | 64.4% | 89.8% | +25.4% | ✅ IMPROVED |
| A5 | 21.2% | 24.2% | +3.0% | ✅ IMPROVED |
| A6 | 0.0% | 0.0% | +0.0% | — NEUTRAL |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | +1248ms | -8058ms |
| A3 | -741ms | -4873ms |
| A4 | -1510ms | -6383ms |
| A5 | -2935ms | -7095ms |
| A6 | +4539ms | +212ms |


#### Improvements (newly passing)

- `C1b-003`
- `C1b-004`
- `C1b-005`
- `C1b-007`
- `C1b-008`
- `C1b-009`
- `C1c-003`
- `C1c-004`
- `C1c-008`
- `C1e-003`
- `C1e-004`
- `C1e-005`
- `C2a-008`
- `C2a-009`
- `C2c-009`
- `C2d-003`
- `C2d-005`
- `C3a-001`
- `C3a-003`
- `C3a-004`
- `C3a-005`
- `C3a-006`
- `C3a-008`
- `C3a-009`
- `C3c-003`
- `C3c-004`
- `C3c-005`
- `C3c-006`
- `C3c-008`
- `C3c-009`
- `C3d-001`
- `C3d-003`
- `C3d-004`
- `C3d-005`
- `C3d-006`
- `C4a-005`
- `C4a-008`
- `C4a-009`
- `C4b-001`
- `C4b-003`
- `C4b-004`
- `C4b-005`
- `C4b-006`
- `C4b-008`
- `C4b-009`
- `C5b-005`

