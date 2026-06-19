# Refund-Harness Eval Results

> **Run:** `20260619T072215Z`  |  **Git SHA:** `7dfb41f`  |  **Cases:** 205  |  **Errors:** 0  |  **Azure blocks:** 58

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 63.9%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 7.2s | 13.8s |
| A3 | 75 | 88.0% | 98.0% | ❌ FAIL | 5.0s | 13.3s |
| A4 | 59 | 91.5% | 98.0% | ❌ FAIL | 2.2s | 6.3s |
| A5 | 33 | 24.2% | 95.0% | ❌ FAIL | 5.3s | 10.8s |
| A6 | 33 | 0.0% | 85.0% | ❌ FAIL | 15.8s | 36.1s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 95.2% | 3.2s | 13.5s |
| C2 | 34 | 91.2% | 1.3s | 6.3s |
| C3 | 33 | 78.8% | 5.2s | 6.6s |
| C4 | 25 | 92.0% | 4.6s | 6.1s |
| C5 | 33 | 24.2% | 5.3s | 10.8s |
| C6 | 33 | 0.0% | 15.8s | 36.1s |
| hand_curated | 5 | 60.0% | 7.2s | 13.8s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 5.3s | 5.0s | ❌ |
| Overall p95 | 36.1s | 12.0s | ❌ |

## Issues Catalog

- [A3/C1b-002] expected=escalate actual=escalate blocked=None | I understand this is frustrating, and I'd like to get you to the right person quickly. I'm passing this to a human agent
- [A3/C1c-006] expected=escalate actual=None blocked=None | 
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
- [A5/C5a-008] expected=escalate actual=deny blocked=None | We are unable to process your refund request at this time. Reason: Refund computed: deny, $0.00. Within window: False. C


---

### Before / After (20260619T062750Z → 20260619T072215Z)

**Verdict:** ✅ IMPROVED


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0% | — NEUTRAL |
| A3 | 88.0% | 88.0% | +0.0% | — NEUTRAL |
| A4 | 89.8% | 91.5% | +1.7% | ✅ IMPROVED |
| A5 | 24.2% | 24.2% | +0.0% | — NEUTRAL |
| A6 | 0.0% | 0.0% | +0.0% | — NEUTRAL |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | +2732ms | +5727ms |
| A3 | +157ms | -4023ms |
| A4 | -1840ms | -4030ms |
| A5 | +384ms | +523ms |
| A6 | +4244ms | +13294ms |


#### Improvements (newly passing)

- `C2a-002`

