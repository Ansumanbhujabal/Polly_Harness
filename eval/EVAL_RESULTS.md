# Refund-Harness Eval Results

> **Run:** `20260619T092645Z`  |  **Git SHA:** `31771f7`  |  **Cases:** 205  |  **Errors:** 0  |  **Azure blocks:** 58

## Overall Verdict: ❌ FAIL

**Overall pass rate:** 69.8%

## Axis Results

| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |
|---|---|---|---|---|---|---|
| A1 | 5 | 60.0% | 95.0% | ❌ FAIL | 7.5s | 17.8s |
| A3 | 75 | 92.0% | 98.0% | ❌ FAIL | 5.1s | 18.6s |
| A4 | 59 | 94.9% | 98.0% | ❌ FAIL | 2.3s | 7.2s |
| A5 | 33 | 45.5% | 95.0% | ❌ FAIL | 5.2s | 10.4s |
| A6 | 33 | 0.0% | 85.0% | ❌ FAIL | 19.3s | 31.7s |

## Category Results

| Category | N | Pass Rate | p50 | p95 |
|---|---|---|---|---|
| C1 | 42 | 97.6% | 2.7s | 19.2s |
| C2 | 34 | 94.1% | 1.6s | 7.2s |
| C3 | 33 | 84.8% | 5.1s | 8.0s |
| C4 | 25 | 96.0% | 4.2s | 7.0s |
| C5 | 33 | 45.5% | 5.2s | 10.4s |
| C6 | 33 | 0.0% | 19.3s | 31.7s |
| hand_curated | 5 | 60.0% | 7.5s | 17.8s |

## Latency

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Overall p50 | 5.2s | 5.0s | ❌ |
| Overall p95 | 31.7s | 12.0s | ❌ |

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

### Before / After (20260619T090636Z → 20260619T092645Z)

**Verdict:** ⬜ NEUTRAL


#### Per-Axis Pass-Rate Delta

| Axis | Baseline | Current | Delta | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0% | — NEUTRAL |
| A3 | 92.0% | 92.0% | +0.0% | — NEUTRAL |
| A4 | 94.9% | 94.9% | +0.0% | — NEUTRAL |
| A5 | 45.5% | 45.5% | +0.0% | — NEUTRAL |
| A6 | 0.0% | 0.0% | +0.0% | — NEUTRAL |


#### Latency Delta

| Axis | p50 Δ | p95 Δ |
|---|---|---|
| A1 | +768ms | -51ms |
| A3 | +317ms | +5775ms |
| A4 | +615ms | +356ms |
| A5 | -323ms | -171ms |
| A6 | -2374ms | -14829ms |


_No case-level changes._

