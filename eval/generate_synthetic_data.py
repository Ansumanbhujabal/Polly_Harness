"""CLI orchestrator — generates adversarial synthetic data and merges with hand-curated cases.

Usage:
    uv run python eval/generate_synthetic_data.py \\
        --count 200 \\
        --output eval/ground_truth.json \\
        --hand-curated eval/seed_cases.yaml

Flags:
    --count N           Total synthetic cases (default 200); distributed across 24 sub-categories.
    --output PATH       Where to write the merged ground_truth.json.
    --hand-curated PATH YAML with seed/demo cases; appended with source="hand_curated".
    --seed N            RNG seed (default 42).
    --no-llm            Skip LLM-paraphrase sub-categories (cheap mode for tests).

Output structure:
    {"version": "1.0", "generated_at": <ISO>, "cases": [...]}
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("generate_synthetic_data")

# ---------------------------------------------------------------------------
# Generator registry
# The 6 modules cover 24 sub-categories total (5+4+4+3+4+4).
# We distribute *count* cases proportionally.
# ---------------------------------------------------------------------------

_GENERATOR_SPECS: list[tuple[str, str, int]] = [
    # (module_path, category_label, n_sub_categories)
    ("eval.adversarial.injection", "C1", 5),
    ("eval.adversarial.jailbreak", "C2", 4),
    ("eval.adversarial.llm_poisoning", "C3", 4),
    ("eval.adversarial.hijacking", "C4", 3),
    ("eval.adversarial.stress", "C5", 4),
    ("eval.adversarial.abuse", "C6", 4),
]

_TOTAL_SUB_CATEGORIES = sum(s for _, _, s in _GENERATOR_SPECS)  # 24


def _distribute(total: int) -> dict[str, int]:
    """Distribute *total* cases proportionally across generator modules.

    Each module gets cases proportional to its number of sub-categories.
    Remainder cases are added one-by-one to the largest-remainder modules.
    """
    base: dict[str, int] = {}
    remainders: list[tuple[float, str]] = []

    for mod_path, label, n_sub in _GENERATOR_SPECS:
        exact = total * n_sub / _TOTAL_SUB_CATEGORIES
        base[mod_path] = int(exact)
        remainders.append((exact - int(exact), mod_path))

    # Distribute remainder cases to top-remainder modules
    allocated = sum(base.values())
    remainder_count = total - allocated
    remainders.sort(key=lambda x: -x[0])
    for i in range(remainder_count):
        base[remainders[i % len(remainders)][1]] += 1

    return base


def _load_llm(deployment: str) -> Any:
    """Lazy-load AzureChatOpenAI; returns None on import failure."""
    try:
        from langchain_openai import AzureChatOpenAI

        from app.config import settings

        return AzureChatOpenAI(
            azure_deployment=deployment,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not load AzureChatOpenAI: %s — running in no-llm mode.", exc)
        return None


def _load_hand_curated(path: Path) -> list[dict]:
    """Load seed_cases.yaml and normalise to ground-truth schema records."""
    raw = yaml.safe_load(path.read_text())
    if not raw:
        return []

    records: list[dict] = []
    for item in raw:
        # Normalise from the seed_cases YAML shape to the ground-truth schema
        records.append(
            {
                "case_id": item.get("id", "hand_curated"),
                "axis": "A1",  # hand-curated cases are policy-correctness demos
                "category": "hand_curated",
                "sub_category": "hand_curated",
                "customer_id": item.get("customer_id", ""),
                "order_id": item.get("order_id", ""),
                "user_message": item.get("user_message", ""),
                "expected_decision_kind": item.get("expected_decision_kind", ""),
                "expected_reason_code": item.get("expected_reason_code", ""),
                "expected_cited_clauses": item.get("expected_cited_clauses", []),
                "expected_verification_blocked": item.get("expected_verification_outcome", "")
                == "blocks",
                "expected_block_check": "",
                "expected_response_traits": item.get("expected_response_traits", []),
                "must_not_traits": item.get("must_not_traits", []),
                "severity": item.get("severity", "block"),
                "source": "hand_curated",
            }
        )
    return records


def _validate_case(case: dict, idx: int) -> list[str]:
    """Return a list of validation error strings (empty = valid)."""
    import re

    errors: list[str] = []
    required_fields = [
        "case_id",
        "axis",
        "category",
        "sub_category",
        "customer_id",
        "order_id",
        "user_message",
        "expected_decision_kind",
        "expected_reason_code",
        "expected_cited_clauses",
        "expected_verification_blocked",
        "expected_block_check",
        "expected_response_traits",
        "must_not_traits",
        "severity",
        "source",
    ]
    for field in required_fields:
        if field not in case:
            errors.append(f"[{idx}] missing field: {field}")

    # Validate case_id format for synthetic cases
    if case.get("source") == "synthetic":
        cid = case.get("case_id", "")
        if not re.match(r"^C[1-6][a-e]-\d{3}$", cid):
            errors.append(f"[{idx}] invalid case_id format: {cid!r}")

    if case.get("severity") not in ("block", "warn"):
        errors.append(f"[{idx}] invalid severity: {case.get('severity')!r}")

    return errors


def generate_all(
    count: int,
    seed: int,
    no_llm: bool,
    hand_curated_path: Path | None,
) -> dict:
    """Run all generators and merge with hand-curated cases.

    Returns the full ground_truth dict (not yet written to disk).
    """
    import importlib

    allocation = _distribute(count)
    llm = None if no_llm else _load_llm("gpt-4o")

    all_cases: list[dict] = []
    sub_cat_counts: dict[str, int] = {}

    for mod_path, label, _ in _GENERATOR_SPECS:
        n = allocation[mod_path]
        if n == 0:
            log.warning("Skipping %s (allocated 0 cases)", mod_path)
            continue

        log.info("Generating %d cases from %s …", n, mod_path)
        try:
            mod = importlib.import_module(mod_path)
            cases = mod.generate(n, seed=seed, llm=llm)
        except Exception as exc:  # noqa: BLE001
            log.error("Generator %s failed: %s", mod_path, exc)
            raise

        # Mark source and count per sub_category
        for c in cases:
            c["source"] = "synthetic"
            sub_cat_counts[c["sub_category"]] = sub_cat_counts.get(c["sub_category"], 0) + 1

        all_cases.extend(cases)
        log.info("  → %d cases produced", len(cases))

    # Append hand-curated
    if hand_curated_path and hand_curated_path.exists():
        hc = _load_hand_curated(hand_curated_path)
        log.info("Loaded %d hand-curated cases from %s", len(hc), hand_curated_path)
        all_cases.extend(hc)
    elif hand_curated_path:
        log.warning("Hand-curated path not found: %s", hand_curated_path)

    # Validate all cases
    all_errors: list[str] = []
    for i, case in enumerate(all_cases):
        errs = _validate_case(case, i)
        all_errors.extend(errs)

    if all_errors:
        log.warning("%d validation issues found:", len(all_errors))
        for err in all_errors[:20]:
            log.warning("  %s", err)
        if len(all_errors) > 20:
            log.warning("  … and %d more", len(all_errors) - 20)

    total_synthetic = sum(1 for c in all_cases if c.get("source") == "synthetic")
    total_hc = sum(1 for c in all_cases if c.get("source") == "hand_curated")
    log.info(
        "Total cases: %d synthetic + %d hand_curated = %d",
        total_synthetic,
        total_hc,
        len(all_cases),
    )
    log.info("Sub-category distribution: %s", json.dumps(sub_cat_counts, sort_keys=True))

    return {
        "version": "1.0",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "total_cases": len(all_cases),
        "synthetic_count": total_synthetic,
        "hand_curated_count": total_hc,
        "sub_category_counts": sub_cat_counts,
        "cases": all_cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate adversarial synthetic data for the refund-harness eval."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=200,
        help="Total synthetic cases to generate (default 200).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("eval/ground_truth.json"),
        help="Output path for the merged ground_truth.json.",
    )
    parser.add_argument(
        "--hand-curated",
        type=Path,
        default=None,
        help="Path to seed_cases.yaml to include as hand_curated cases.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for deterministic output (default 42).",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM-paraphrase sub-categories (cheap mode; safe for CI).",
    )

    args = parser.parse_args()

    log.info(
        "Starting generation: count=%d seed=%d no-llm=%s",
        args.count,
        args.seed,
        args.no_llm,
    )

    ground_truth = generate_all(
        count=args.count,
        seed=args.seed,
        no_llm=args.no_llm,
        hand_curated_path=args.hand_curated,
    )

    # Write output
    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(ground_truth, indent=2, ensure_ascii=False))
    log.info("Written to %s (%d cases)", output_path, ground_truth["total_cases"])


if __name__ == "__main__":
    main()
