"""Adversarial generator package.

Each sub-module exports:
    generate(n: int = 10, *, seed: int = 42, llm=None) -> list[dict]

Categories:
    C1 — Injection        (injection.py)
    C2 — Jailbreak        (jailbreak.py)
    C3 — LLM Poisoning    (llm_poisoning.py)
    C4 — Hijacking        (hijacking.py)
    C5 — Stress           (stress.py)
    C6 — Abuse            (abuse.py)
"""

from eval.adversarial import abuse, hijacking, injection, jailbreak, llm_poisoning, stress

__all__ = [
    "abuse",
    "hijacking",
    "injection",
    "jailbreak",
    "llm_poisoning",
    "stress",
]
