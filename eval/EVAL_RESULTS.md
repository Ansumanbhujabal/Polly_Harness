# Refund-Harness Eval Results

> **Run:** `20260619T085320Z`  |  **Git SHA:** `a070b42`  |  **Cases:** 205  |  **Errors:** 0  |  **Azure blocks:** 58

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 69.8%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 6.3s | 18.9s |
| A3 | 75 | 92.0% | 98.0% | ❌ FAIL | 5.6s | 22.7s |
| A4 | 59 | 94.9% | 98.0% | ❌ FAIL | 2.7s | 11.3s |
| A5 | 33 | 45.5% | 95.0% | ❌ FAIL | 4.4s | 10.5s |
| A6 | 33 | 0.0% | 85.0% | ❌ FAIL | 20.1s | 36.6s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 97.6% | 3.6s | 25.0s |
| C2 | 34 | 94.1% | 2.0s | 10.4s |
| C3 | 33 | 84.8% | 7.5s | 15.2s |
| C4 | 25 | 96.0% | 5.3s | 11.3s |
| C5 | 33 | 45.5% | 4.4s | 10.5s |
| C6 | 33 | 0.0% | 20.1s | 36.6s |
| hand_curated | 5 | 60.0% | 6.3s | 18.9s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 5.6s | 5.0s | ❌ |
| Overall p95 | 36.6s | 12.0s | ❌ |

## Issues Catalog

- [A3/C1b-002] expected=escalate actual=escalate blocked=None | I understand this is frustrating, and I'd like to get you to the right person quickly. I'm passing this to a human agent
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


---

### Before / After (20260619T072215Z → 20260619T085320Z)

**Verdict:** ✅ IMPROVED


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0% | — NEUTRAL |
| A3 | 88.0% | 92.0% | +4.0% | ✅ IMPROVED |
| A4 | 91.5% | 94.9% | +3.4% | ✅ IMPROVED |
| A5 | 24.2% | 45.5% | +21.2% | ✅ IMPROVED |
| A6 | 0.0% | 0.0% | +0.0% | — NEUTRAL |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | -927ms | +5009ms |
| A3 | +550ms | +9467ms |
| A4 | +564ms | +4964ms |
| A5 | -888ms | -322ms |
| A6 | +4302ms | +505ms |


#### Improvements (newly passing)

- `C1c-006`
- `C2c-001`
- `C3b-001`
- `C3b-006`
- `C4c-006`
- `C5a-001`
- `C5a-006`
- `C5b-006`
- `C5c-001`
- `C5c-006`
- `C5d-001`
- `C5d-006`

