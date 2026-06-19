"""LLM-as-judge evaluators for the refund agent eval suite.

Each judge module exports:
    score(state: AgentState | dict, expected: dict, *, llm=None) -> dict

The four original judges return float scores (0.0 or 1.0) for backward
compatibility with run_scenarios.py. The four new judges return a richer
dict: {"score": float, "passed": bool, "reason": str, "metadata": {...}}.

Mean scores across all evaluated cases are compared against eval/thresholds.yaml
in run_scenarios.py.

Original judges (v0.1):
  policy_correctness, injection_resistance, tone_appropriate, hallucination_check

New judges (G2):
  refusal_correctness  — axis A2 (LLM-based)
  jailbreak_resistance — axis A4 (LLM-based, heuristic + LLM for ambiguity)
  tool_safety          — axis A5 (deterministic)
  policy_grounding     — axis A1 refinement (deterministic)
"""

from eval.judges.hallucination_check import score as hallucination_check_score
from eval.judges.injection_resistance import score as injection_resistance_score
from eval.judges.jailbreak_resistance import score as jailbreak_resistance_score
from eval.judges.policy_correctness import score as policy_correctness_score
from eval.judges.policy_grounding import score as policy_grounding_score
from eval.judges.refusal_correctness import score as refusal_correctness_score
from eval.judges.tone_appropriate import score as tone_appropriate_score
from eval.judges.tool_safety import score as tool_safety_score

JUDGE_NAMES = [
    "policy_correctness",
    "injection_resistance",
    "tone_appropriate",
    "hallucination_check",
    # G2 additions
    "refusal_correctness",
    "jailbreak_resistance",
    "tool_safety",
    "policy_grounding",
]

JUDGE_FUNCTIONS = {
    "policy_correctness": policy_correctness_score,
    "injection_resistance": injection_resistance_score,
    "tone_appropriate": tone_appropriate_score,
    "hallucination_check": hallucination_check_score,
    # G2 additions
    "refusal_correctness": refusal_correctness_score,
    "jailbreak_resistance": jailbreak_resistance_score,
    "tool_safety": tool_safety_score,
    "policy_grounding": policy_grounding_score,
}

__all__ = [
    "JUDGE_FUNCTIONS",
    "JUDGE_NAMES",
    "hallucination_check_score",
    "injection_resistance_score",
    "jailbreak_resistance_score",
    "policy_correctness_score",
    "policy_grounding_score",
    "refusal_correctness_score",
    "tone_appropriate_score",
    "tool_safety_score",
]
