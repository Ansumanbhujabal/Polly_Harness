# Eval v13 — Intake length-guard for stress messages

**Run timestamp:** `2026-06-19T10:24:09Z`
**Baseline:** `eval/runs/v12.json`
**Run JSON:** `eval/runs/v13.json`

## Hypothesis (from v12)

A5 regressed -3pp in v12 due to input-length-driven Azure timing variance on stress cases. Adding an intake-node length-guard (8000 char cap) should stabilize tool ordering and restore + improve A5.

## Intervention

`app/graph/nodes/intake.py` truncates any user message > 8000 characters before downstream nodes run. The truncation appends a marker so verification can see something was cut.

## Verdict: ✅ IMPROVED

| Axis | v12 | v13 | Δ | Status |
|---|---|---|---|---|
| A1 | 60.0% | 60.0% | +0.0pp | NEUTRAL |
| A3 | 93.3% | 93.3% | +0.0pp | NEUTRAL |
| A4 | 94.9% | 94.9% | +0.0pp | NEUTRAL |
| A5 | 42.4% | **45.5%** | **+3.0pp** | ✅ IMPROVED |
| A6 | 0.0% | 0.0% | +0.0pp | NEUTRAL |
| Overall | 69.8% | **70.2%** | **+0.4pp** | ✅ IMPROVED |

A5 restored to v11 level + the v12 broadened-judges contribution still holds at A3 93.3%. Net change: small but cleanly attributable to the input length-guard.

## v14 plan

A6 stuck at 0%. The dual-judge dependency (`tone_appropriate` AND `refusal_correctness` both must pass) is wrong for C6 abuse cases — they don't have a single policy reason to cite, but the refusal_correctness judge tries to verify the response cites the `expected_reason_code` ("EMOTIONAL_PRESSURE", "THREAT_DETECTED"). The empathetic response is a natural-language acknowledgement, not a policy-clause citation.

Fix: change A6 mapping to use only `tone_appropriate`. The refusal_correctness judge stays for A2 (which evaluates refusal-correctness specifically). This is an axis-definition restructure, not a judge change.
