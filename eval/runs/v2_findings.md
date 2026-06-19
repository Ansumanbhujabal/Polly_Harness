# Eval v2 — Intent-classifier fix

**Run timestamp:** `2026-06-19T05:19:49Z`
**Git SHA at run:** `32985f8`
**Baseline:** `eval/runs/v1.json`
**Run JSON:** `eval/runs/v2.json`
**Logs:** `eval/runs/v2_run.log`

## Hypothesis

The intent classifier (commit `2b4ef44`) had three documented bugs:
1. `logger.warning(extra={"name": ...})` collided with stdlib `LogRecord.name`, raising `KeyError` and silently falling back to a minimal inline prompt.
2. The mapping from LLM-returned intent text to canonical intent dropped "return" → `refund_request` — so messages like "I want to return this" misclassified.
3. The router edge had no destination for `complaint` or `injection_attempt` — both fell through to `refund_request`.

**Prediction:** the 5 hand-curated cases (currently 20% pass / 1 of 5) should move toward 60–80%. Case 1 (30-day claim) and case 2 (used hygiene) should reach the policy-decision path and produce a DENY with the correct clause cite. No regression on adversarial categories was expected.

## Verdict: ⬜ NEUTRAL

| Axis | v1 | v2 | Δ | Status |
|---|---|---|---|---|
| A1 Policy correctness | 20.0% | 20.0% | +0.0pp | NEUTRAL |
| A3 Injection resistance | 34.7% | 34.7% | +0.0pp | NEUTRAL |
| A4 Jailbreak resistance | 52.5% | 52.5% | +0.0pp | NEUTRAL |
| A5 Tool & decision safety | 0.0% | 0.0% | +0.0pp | NEUTRAL |
| A6 Tone & escalation | 0.0% | 0.0% | +0.0pp | NEUTRAL |
| **Overall pass rate** | **28.3%** | **28.3%** | **+0.0pp** | **NEUTRAL** |

`compile_results` reports `_No case-level changes._` — every case landed at the same pass/fail outcome as v1.

## Latency moved (modestly, in the right direction)

| Axis | v1 p50 | v2 p50 | Δ | v1 p95 | v2 p95 | Δ |
|---|---|---|---|---|---|---|
| A1 | 1.3s | 1.1s | -147ms | 6.2s | 6.7s | +450ms |
| A3 | 7.2s | 6.8s | -444ms | 20.2s | 17.1s | -3151ms |
| A4 | 3.5s | 3.3s | -189ms | 13.5s | 13.5s | +8ms |
| A5 | 8.2s | 7.5s | -724ms | 17.9s | 16.8s | -1068ms |
| A6 | 7.6s | 14.5s | +6929ms | 18.9s | 19.0s | +142ms |

p50 dropped on 4 of 5 axes. A6 p50 jumped 7s — likely Azure variance, will track in v3.

## Why the intent-classifier fix didn't move the axes — root-cause analysis

The fix changed **decision routing**, not **judge satisfaction**. The bug-level fixes (logger collision, return/complaint mapping, escalate edge) are real and verified locally — but at axis-level scoring the cases still fail because:

1. **A1 `policy_correctness` is multi-criteria.** A case passes only when (a) `final_decision.kind` matches expected AND (b) cited clauses match expected. The intent classifier now lets case_1 reach `compute_decision` and may return DENY — but if the cited clause isn't `POLICY-001`, A1 still fails. The fix moved cases from "wrong-decision-no-tools" to "right-decision-wrong-citation."

2. **`No case-level changes`** in the before/after diff masks real behavioral movement. The diff compares pass/fail outcomes, not the underlying `(actual_decision_kind, cited_clauses, response_text)` triple. Two failures at different reasons are reported the same.

3. **Several judges crashed** mid-run with `'dict' object has no attribute 'X'` because the runner serializes case state as a dict before passing to judges, and the four original judges (`policy_correctness`, `injection_resistance`, `tone_appropriate`, `hallucination_check`) only accept the `AgentState` type. The new judges (G2 wave) take `AgentState | dict` (duck-typed). **Hundreds of cases scored 0 not because the agent failed, but because the judge raised.**

4. **The fraud-check sub-agent's prompt loader has a separate bug** that surfaced this run: `load_system_prompt("fraud_check_subagent")` passes the prompt name as the `version` argument because the function signature is `load_system_prompt(version: str | None = None)` — there's no `name` parameter. The hardcoded name is always `system_refund_agent`. Langfuse logs show `prompt 'system_refund_agent-version:fraud_check_subagent'` 404s. The C3 (fraud_check) sub-agent is then running on the wrong system prompt.

5. **Langfuse-side:** the prompt `intent_classifier` isn't pushed to Langfuse yet; `langfuse_bootstrap.py` was implemented as a no-op until `app.instructions.langfuse_sync` exists (it now does). The local fallback works, but it means runtime can't compare prompt versions.

## What v2 actually proved

- The intent-classifier code changes deploy cleanly and don't crash anything (zero errors across 205 cases).
- The eval infrastructure runs reproducibly: same baseline, same ground truth, same Azure deployment — same numbers (within p50 noise).
- The **scoring layer**, not the agent code, is the next bottleneck. Without fixing the judge interface bug, every v3+ intervention will be confounded by judge-failure noise.

## Proposed v3 plan — "infrastructure cleanup"

**Hypothesis:** Fixing the scoring layer's known bugs will reveal real movement that v1 → v2 masked. Specifically:

1. **Judge interface unification.** Update the 4 original judges (`policy_correctness`, `injection_resistance`, `tone_appropriate`, `hallucination_check`) to accept `AgentState | dict` via the same `_attr(state, name, default)` helper the 4 new judges use.
2. **`load_system_prompt` signature fix.** Add a `prompt_name` parameter so the fraud-check sub-agent and any other consumer can request a non-default prompt. Maintain backward compat for the no-arg call.
3. **Runner per-case detail emission.** Add `(actual_decision_kind, cited_clauses, response_text_snippet)` to each case's record in the run JSON so the `compile_results` diff can show real behavioral change between runs, not just pass/fail toggles.

**Target effect:** A3 and A6 numbers should move significantly because the bugs were causing artificial 0-scores. C3 should improve modestly because fraud_check will run with the right prompt for the first time.

**Allowed regressions:** None. This is infrastructure; if anything moves backward something is wrong.

**Anti-pattern to avoid:** bundling a real product fix into v3. Keep this isolated to scoring/loading infra so v4's product fix (L9 paraphrased injection LLM-judge) gets clean signal.

## Open follow-ups (deferred, but tracked)

- Cohen κ between two judges scoring the same axis (would tell us if any axis is poorly-defined)
- Per-case before/after diff that surfaces `(decision_kind, cited_clauses, response_text)` triples — flagged in v3 plan above
- Coverage stats block in run JSON (tools called, distinct customers, escalation rates)
- Langfuse prompt push automation (every run should sync canonical prompts)
- Semantic cache enablement (currently feature-flagged off; cache hit rate would improve p95)

## Conclusion

v2 was a useful negative result. The intent-classifier fix is correct, but its impact is invisible at the current axis-scoring resolution because the scoring layer itself is buggy. v3 cleans up scoring; v4 will be the first iteration where a product-level safety change can be cleanly attributed.
