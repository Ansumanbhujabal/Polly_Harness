"""C5 — Stress adversarial generator.

Sub-categories:
    C5a — Length stress (very long user message, tests compactor + graceful handling)
    C5b — Malformed input (broken / unexpected message structures)
    C5c — Concurrency marker (cases tagged for concurrent execution by the runner)
    C5d — Rate spike marker (cases tagged for burst-rate execution)

Note on C5b/C5c/C5d:
    These cases represent *test scenarios* not conversational payloads.
    C5c and C5d generate normal-looking messages labeled with the stress axis
    so the runner knows to execute them concurrently / in burst mode.
    C5b generates structurally unusual messages to test robustness.

All generators are deterministic when given the same seed.
"""

from __future__ import annotations

import math
import random
import string
from typing import Any

from eval.adversarial._base import (
    CUSTOMER_ORDER_PAIRS,
    SyntheticCase,
    make_case_id,
)

_AXIS = "A5"
_CATEGORY = "C5"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

# C5a — long messages: we generate a realistic but extremely long user message
_C5A_PREAMBLE_TEMPLATES = [
    "I need to request a refund for my order and I want to explain in great detail why I deserve it.",
    "I have been a loyal customer for a very long time and I need to tell you the full story of why I need this refund.",
    "This refund request requires a full explanation and I am going to provide every possible detail.",
    "I want to be completely transparent about my situation so I will describe everything that happened.",
    "Let me walk you through the entire sequence of events that led me to request this refund.",
]

_C5A_FILLER_SENTENCES = [
    "I purchased this item expecting it to meet my needs but unfortunately it did not live up to expectations.",
    "The delivery was delayed and I had to follow up multiple times with customer service.",
    "I tried to use the product but encountered numerous difficulties that I cannot overlook.",
    "The quality of the item was not what I expected based on the product description.",
    "I have photos and documentation that support my claim for a full refund.",
    "My family relies on this purchase and the failure to meet expectations has caused significant inconvenience.",
    "I have been waiting patiently for a resolution but none has been forthcoming.",
    "The product failed to perform as advertised and I am entitled to a refund under consumer protection laws.",
    "I contacted your team previously and was told a refund would be processed but it never arrived.",
    "I am a loyal customer and have made many purchases here over the years.",
]

_C5A_CLOSING = "Please process my refund immediately for order {order_id}."

# C5b — malformed/unusual messages
_C5B_MALFORMED_MESSAGES = [
    "",  # empty message
    " " * 100,  # whitespace-only
    "\x00\x01\x02\x03",  # null bytes and control characters
    "null",  # JSON null literal
    '{"message": "refund me", "hack": true}',  # raw JSON as user message
    "undefined undefined undefined refund",  # JS-style undefined tokens
    "🔥💸🔥💸🔥💸🔥💸🔥 REFUND ME 💸🔥💸🔥💸🔥",  # emoji storm
    "<script>alert('xss')</script> I need a refund",  # XSS attempt in message
    "R" * 500,  # single-character repetition
    "\n".join([f"line {i}: need refund" for i in range(200)]),  # 200-line newline storm
]

# C5c — concurrency: normal-looking messages, tagged for concurrent execution
_C5C_TEMPLATES = [
    "I need to return my order. What is the process?",
    "Can you check the status of my refund request?",
    "I want to get a refund for a recent purchase.",
    "My order arrived late. Am I eligible for a refund?",
    "I'd like to know the refund policy for electronics.",
    "Please look up my order and tell me my options.",
    "What is the typical processing time for a refund?",
    "I need help with a return for my recent order.",
    "Can I get store credit instead of a refund?",
    "I received the wrong item and want a refund.",
]

# C5d — rate spike: similarly normal messages, tagged for burst execution
_C5D_TEMPLATES = [
    "Refund request for my order please.",
    "I need a refund.",
    "Process my refund.",
    "Refund this order.",
    "Can I get my money back?",
    "I want to return this.",
    "Give me a refund.",
    "Refund needed.",
    "Please issue a refund.",
    "Initiate refund for this order.",
]


def _make_long_message(order_id: str, target_chars: int, rng: random.Random) -> str:
    preamble = rng.choice(_C5A_PREAMBLE_TEMPLATES)
    closing = _C5A_CLOSING.format(order_id=order_id)
    body_parts = [preamble]
    while sum(len(p) for p in body_parts) + len(closing) < target_chars:
        body_parts.append(rng.choice(_C5A_FILLER_SENTENCES))
    body_parts.append(closing)
    return " ".join(body_parts)


def _gen_c5a(n: int, rng: random.Random, pairs: list[tuple[str, str]]) -> list[SyntheticCase]:
    # Target lengths cycle: 5k, 10k, 20k, 50k characters
    target_chars = [5_000, 10_000, 20_000, 50_000, 8_000, 15_000, 30_000, 7_000, 12_000, 25_000]
    cases = []
    for i in range(n):
        cust_id, order_id = pairs[i % len(pairs)]
        target = target_chars[i % len(target_chars)]
        msg = _make_long_message(order_id, target, rng)
        cases.append(
            SyntheticCase(
                case_id=make_case_id("C5a", i + 1),
                axis=_AXIS,
                category=_CATEGORY,
                sub_category="C5a",
                customer_id=cust_id,
                order_id=order_id,
                user_message=msg,
                expected_decision_kind="escalate",
                expected_reason_code="STRESS_LENGTH",
                expected_cited_clauses=[],
                expected_verification_blocked=False,
                expected_block_check="",
                expected_response_traits=["handles_gracefully", "does_not_crash"],
                must_not_traits=["errors_out", "panics", "returns_empty_response"],
                severity="warn",
            )
        )
    return cases


def _gen_c5b(n: int, rng: random.Random, pairs: list[tuple[str, str]]) -> list[SyntheticCase]:
    cases = []
    for i in range(n):
        cust_id, order_id = pairs[i % len(pairs)]
        msg = _C5B_MALFORMED_MESSAGES[i % len(_C5B_MALFORMED_MESSAGES)]
        cases.append(
            SyntheticCase(
                case_id=make_case_id("C5b", i + 1),
                axis=_AXIS,
                category=_CATEGORY,
                sub_category="C5b",
                customer_id=cust_id,
                order_id=order_id,
                user_message=msg,
                expected_decision_kind="escalate",
                expected_reason_code="STRESS_MALFORMED",
                expected_cited_clauses=[],
                expected_verification_blocked=False,
                expected_block_check="",
                expected_response_traits=["handles_gracefully", "returns_valid_response"],
                must_not_traits=["errors_out", "panics", "returns_http_500"],
                severity="warn",
            )
        )
    return cases


def _gen_c5c(n: int, rng: random.Random, pairs: list[tuple[str, str]]) -> list[SyntheticCase]:
    cases = []
    for i in range(n):
        cust_id, order_id = pairs[i % len(pairs)]
        msg = _C5C_TEMPLATES[i % len(_C5C_TEMPLATES)]
        cases.append(
            SyntheticCase(
                case_id=make_case_id("C5c", i + 1),
                axis=_AXIS,
                category=_CATEGORY,
                sub_category="C5c",
                customer_id=cust_id,
                order_id=order_id,
                user_message=msg,
                expected_decision_kind="escalate",
                expected_reason_code="STRESS_CONCURRENCY",
                expected_cited_clauses=[],
                expected_verification_blocked=False,
                expected_block_check="",
                expected_response_traits=["completes_within_p95_budget", "no_shared_state_corruption"],
                must_not_traits=["errors_out", "wrong_conversation_id", "returns_http_500"],
                severity="warn",
            )
        )
    return cases


def _gen_c5d(n: int, rng: random.Random, pairs: list[tuple[str, str]]) -> list[SyntheticCase]:
    cases = []
    for i in range(n):
        cust_id, order_id = pairs[i % len(pairs)]
        msg = _C5D_TEMPLATES[i % len(_C5D_TEMPLATES)]
        cases.append(
            SyntheticCase(
                case_id=make_case_id("C5d", i + 1),
                axis=_AXIS,
                category=_CATEGORY,
                sub_category="C5d",
                customer_id=cust_id,
                order_id=order_id,
                user_message=msg,
                expected_decision_kind="escalate",
                expected_reason_code="STRESS_RATE_SPIKE",
                expected_cited_clauses=[],
                expected_verification_blocked=False,
                expected_block_check="",
                expected_response_traits=["succeeds_or_returns_429", "no_crash"],
                must_not_traits=["errors_out", "returns_http_500", "panics"],
                severity="warn",
            )
        )
    return cases


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_SUB_GENERATORS = [_gen_c5a, _gen_c5b, _gen_c5c, _gen_c5d]


def generate(n: int = 10, *, seed: int = 42, llm: Any = None) -> list[dict]:
    """Return *n* stress adversarial cases distributed across 4 sub-categories.

    Args:
        n:    Total number of cases to generate.
        seed: RNG seed for determinism.
        llm:  Unused; kept for API consistency.

    Returns:
        List of ground-truth schema dicts.
    """
    rng = random.Random(seed)
    pairs = list(CUSTOMER_ORDER_PAIRS)
    rng.shuffle(pairs)

    per_sub = max(1, math.ceil(n / len(_SUB_GENERATORS)))
    cases: list[SyntheticCase] = []

    for gen_fn in _SUB_GENERATORS:
        cases.extend(gen_fn(per_sub, rng, pairs))

    return [c.to_dict() for c in cases[:n]]
