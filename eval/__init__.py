"""Evaluation layer — public API.

Entry points:
    python -m eval.run_scenarios
    python -m eval.generate_adversarial_cases

Judges are in eval/judges/. Seed cases and thresholds are YAML files in eval/.
"""

from pathlib import Path

EVAL_DIR = Path(__file__).parent
SEED_CASES_PATH = EVAL_DIR / "seed_cases.yaml"
THRESHOLDS_PATH = EVAL_DIR / "thresholds.yaml"
GENERATED_DIR = EVAL_DIR / "generated"

__all__ = [
    "EVAL_DIR",
    "GENERATED_DIR",
    "SEED_CASES_PATH",
    "THRESHOLDS_PATH",
]
