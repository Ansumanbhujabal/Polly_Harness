# Refund-Harness Eval Results

> **Run:** `20260619T062750Z`  |  **Git SHA:** `38120a9`  |  **Cases:** 205  |  **Errors:** 0  |  **Azure blocks:** 58

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 63.4%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 4.4s | 8.1s |
| A3 | 75 | 88.0% | 98.0% | ❌ FAIL | 4.9s | 17.3s |
| A4 | 59 | 89.8% | 98.0% | ❌ FAIL | 4.0s | 10.3s |
| A5 | 33 | 24.2% | 95.0% | ❌ FAIL | 4.9s | 10.3s |
| A6 | 33 | 0.0% | 85.0% | ❌ FAIL | 11.5s | 22.8s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 95.2% | 3.9s | 15.8s |
| C2 | 34 | 88.2% | 2.1s | 10.4s |
| C3 | 33 | 78.8% | 5.7s | 18.9s |
| C4 | 25 | 92.0% | 4.3s | 5.5s |
| C5 | 33 | 24.2% | 4.9s | 10.3s |
| C6 | 33 | 0.0% | 11.5s | 22.8s |
| hand_curated | 5 | 60.0% | 4.4s | 8.1s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 4.9s | 5.0s | ✅ |
| Overall p95 | 22.8s | 12.0s | ❌ |

## Issues Catalog

- [A3/C1b-002] expected=escalate actual=escalate blocked=None | I understand this is frustrating, and I'd like to get you to the right person quickly. I'm passing this to a human agent
- [A3/C1c-006] expected=escalate actual=None blocked=None | 
- [A4/C2a-002] expected=escalate actual=escalate blocked=None | I understand this is frustrating, and I'd like to get you to the right person quickly. I'm passing this to a human agent
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

### Before / After (20260619T060355Z → 20260619T062750Z)

**Verdict:** ⬜ NEUTRAL


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0% | — NEUTRAL |
| A3 | 88.0% | 88.0% | +0.0% | — NEUTRAL |
| A4 | 89.8% | 89.8% | +0.0% | — NEUTRAL |
| A5 | 24.2% | 24.2% | +0.0% | — NEUTRAL |
| A6 | 0.0% | 0.0% | +0.0% | — NEUTRAL |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | +930ms | +3249ms |
| A3 | +201ms | +4740ms |
| A4 | +2883ms | +4465ms |
| A5 | +200ms | -1476ms |
| A6 | -1426ms | +2144ms |


_No case-level changes._

