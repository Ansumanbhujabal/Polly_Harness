"""Shared foundation for all adversarial generators.

Exports:
    SyntheticCase  — dataclass matching the ground-truth JSON schema (ARCHITECTURE §4)
    CRM            — singleton accessor for customers + orders
    _paraphrase    — LLM-based paraphrase helper (cached to disk)
    CUSTOMERS      — list of all customer_id strings
    ORDERS         — list of all order_id strings
    CUSTOMER_ORDER_PAIRS — list of (customer_id, order_id) tuples (real CRM rows only)
"""

from __future__ import annotations

import dataclasses
import json
import random
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Repo paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CRM_CUSTOMERS = _REPO_ROOT / "data" / "crm" / "customers.json"
_CRM_ORDERS = _REPO_ROOT / "data" / "crm" / "orders.json"
_SYNTHETIC_DIR = _REPO_ROOT / "eval" / "synthetic_data"
_SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# CRM data (loaded once at import time)
# ---------------------------------------------------------------------------


def _load_crm() -> tuple[list[dict], list[dict]]:
    customers = json.loads(_CRM_CUSTOMERS.read_text())["customers"]
    orders = json.loads(_CRM_ORDERS.read_text())["orders"]
    return customers, orders


_CUSTOMERS_RAW, _ORDERS_RAW = _load_crm()

CUSTOMERS: list[str] = [c["customer_id"] for c in _CUSTOMERS_RAW]
ORDERS: list[str] = [o["order_id"] for o in _ORDERS_RAW]

# Pairs guaranteed to be in the CRM (customer_id, order_id)
CUSTOMER_ORDER_PAIRS: list[tuple[str, str]] = [
    (o["customer_id"], o["order_id"]) for o in _ORDERS_RAW
]

# ---------------------------------------------------------------------------
# Ground-truth schema dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SyntheticCase:
    """One adversarial ground-truth record — matches ARCHITECTURE.md §4."""

    case_id: str
    axis: str
    category: str
    sub_category: str
    customer_id: str
    order_id: str
    user_message: str
    expected_decision_kind: str          # "escalate" | "deny" | "approve"
    expected_reason_code: str
    expected_cited_clauses: list[str]
    expected_verification_blocked: bool
    expected_block_check: str
    expected_response_traits: list[str]
    must_not_traits: list[str]
    severity: str                         # "block" | "warn"
    source: str = "synthetic"

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# case_id helpers
# ---------------------------------------------------------------------------


def make_case_id(sub_category: str, index: int) -> str:
    """Return deterministic case_id like 'C1a-001'."""
    return f"{sub_category}-{index:03d}"


# ---------------------------------------------------------------------------
# LLM paraphrase helper (cached per sub_category+seed)
# ---------------------------------------------------------------------------


def _cache_path(sub_category: str, seed: int) -> Path:
    return _SYNTHETIC_DIR / f".cache_{sub_category}_{seed}.jsonl"


def _paraphrase(
    text: str,
    n_variants: int,
    llm: Any,  # langchain_openai.AzureChatOpenAI | None
    *,
    sub_category: str,
    seed: int,
) -> list[str]:
    """Return n_variants paraphrases of *text*.

    Results are cached to eval/synthetic_data/.cache_<sub_cat>_<seed>.jsonl
    so repeated runs do not hit the API.

    When llm is None (--no-llm mode) returns deterministic template variants
    instead.
    """
    cache = _cache_path(sub_category, seed)

    # -- Try cache first -------------------------------------------------------
    if cache.exists():
        stored: list[str] = []
        for line in cache.read_text().splitlines():
            if line.strip():
                stored.append(json.loads(line)["variant"])
        if len(stored) >= n_variants:
            return stored[:n_variants]

    # -- No LLM available — return deterministic variants ----------------------
    if llm is None:
        rng = random.Random(seed)
        variants: list[str] = []
        suffixes = [
            "Please process immediately.",
            "This is urgent.",
            "I need this resolved now.",
            "Thank you in advance.",
            "I've been waiting too long.",
        ]
        for i in range(n_variants):
            suffix = suffixes[i % len(suffixes)]
            variants.append(f"{text} {suffix}")
        # Cache these so structure is consistent
        _write_cache(cache, variants)
        return variants

    # -- Call LLM --------------------------------------------------------------
    from langchain_core.messages import HumanMessage, SystemMessage

    system = (
        "You are a test-data generator. "
        "Rewrite the user message in natural language while preserving its semantic intent. "
        "Return ONLY the rewritten message on a single line. Do not explain."
    )
    results: list[str] = []
    rng = random.Random(seed)

    for _ in range(n_variants):
        temp = round(rng.uniform(0.6, 0.9), 2)
        try:
            resp = llm.invoke(
                [SystemMessage(content=system), HumanMessage(content=text)],
                temperature=temp,
            )
            results.append(resp.content.strip())
        except Exception:  # noqa: BLE001
            results.append(text)  # fallback: original text

    _write_cache(cache, results)
    return results


def _write_cache(path: Path, variants: list[str]) -> None:
    lines = "\n".join(json.dumps({"variant": v}) for v in variants)
    path.write_text(lines + "\n")
