"""LLM-as-judge evaluators for the refund agent eval suite.

Each judge module exports a single function:
    score(state: AgentState, expected: dict) -> float

Scores are binary (0.0 or 1.0) for all four judges. Mean scores across all
evaluated cases are compared against eval/thresholds.yaml in run_scenarios.py.
"""

from eval.judges.hallucination_check import score as hallucination_check_score
from eval.judges.injection_resistance import score as injection_resistance_score
from eval.judges.policy_correctness import score as policy_correctness_score
from eval.judges.tone_appropriate import score as tone_appropriate_score

JUDGE_NAMES = [
    "policy_correctness",
    "injection_resistance",
    "tone_appropriate",
    "hallucination_check",
]

JUDGE_FUNCTIONS = {
    "policy_correctness": policy_correctness_score,
    "injection_resistance": injection_resistance_score,
    "tone_appropriate": tone_appropriate_score,
    "hallucination_check": hallucination_check_score,
}

__all__ = [
    "JUDGE_FUNCTIONS",
    "JUDGE_NAMES",
    "hallucination_check_score",
    "injection_resistance_score",
    "policy_correctness_score",
    "tone_appropriate_score",
]
