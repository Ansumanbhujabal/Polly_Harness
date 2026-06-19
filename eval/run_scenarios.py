"""Eval scenario runner — `python -m eval.run_scenarios`.

1. Loads eval/seed_cases.yaml + any files in eval/generated/*.yaml.
2. For each case: invokes RefundGraph (stub-ready; real LLM in CI).
3. Scores with 4 judges.
4. Posts the run to a Langfuse dataset.
5. Prints a pass-rate table.
6. Exits non-zero if ANY judge's mean score is below its threshold in eval/thresholds.yaml.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

from eval import GENERATED_DIR, SEED_CASES_PATH, THRESHOLDS_PATH
from eval.judges import JUDGE_FUNCTIONS, JUDGE_NAMES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Case loading
# ---------------------------------------------------------------------------


def load_cases() -> list[dict[str, Any]]:
    """Load seed cases + all generated variant files."""
    cases: list[dict[str, Any]] = yaml.safe_load(SEED_CASES_PATH.read_text())
    logger.info("Loaded %d seed cases", len(cases))

    if GENERATED_DIR.exists():
        for generated_file in sorted(GENERATED_DIR.glob("*.yaml")):
            extra = yaml.safe_load(generated_file.read_text())
            if extra:
                cases.extend(extra)
                logger.info("Loaded %d variants from %s", len(extra), generated_file)

    logger.info("Total cases to evaluate: %d", len(cases))
    return cases


# ---------------------------------------------------------------------------
# Graph invocation (stub-safe)
# ---------------------------------------------------------------------------


async def _invoke_graph(case: dict[str, Any]) -> Any:  # returns AgentState
    """Run a single eval case through RefundGraph.

    In real runs, this hits the actual LangGraph + LLM.
    In test / offline runs, callers replace this function via monkeypatching.
    """
    from app.graph import AgentState, build_graph

    conversation_id = f"eval_{case['id']}"
    user_message = case["user_message"]

    # Build initial state
    initial_state = AgentState(
        conversation_id=conversation_id,
        messages=[{"role": "user", "content": user_message}],
    )

    graph = build_graph()
    result = await graph.ainvoke(initial_state)
    return result


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_case(state: Any, case: dict[str, Any]) -> dict[str, float]:
    """Run all 4 judges against a completed state. Returns {judge_name: score}."""
    scores: dict[str, float] = {}
    for judge_name in JUDGE_NAMES:
        judge_fn = JUDGE_FUNCTIONS[judge_name]
        try:
            s = judge_fn(state, case)
        except Exception as exc:  # noqa: BLE001
            logger.error("Judge %s failed for case %s: %s", judge_name, case.get("id"), exc)
            s = 0.0
        scores[judge_name] = s
    return scores


# ---------------------------------------------------------------------------
# Langfuse dataset posting
# ---------------------------------------------------------------------------


def _post_to_langfuse_dataset(
    run_results: list[dict[str, Any]],
    dataset_name: str = "refund-agent-eval",
) -> None:
    """Post all case results to a Langfuse dataset run (best-effort)."""
    try:
        from app.observability import get_langfuse_client

        client = get_langfuse_client()
        if client is None:
            logger.info("Langfuse client not configured — skipping dataset post")
            return

        for result in run_results:
            client.create_dataset_item(
                dataset_name=dataset_name,
                input={"user_message": result["case"]["user_message"]},
                expected_output={
                    "decision_kind": result["case"]["expected_decision_kind"],
                },
                metadata={
                    "case_id": result["case"]["id"],
                    "scores": result["scores"],
                },
            )
        client.flush()
        logger.info("Posted %d results to Langfuse dataset '%s'", len(run_results), dataset_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Langfuse dataset post failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# Threshold gate + reporting
# ---------------------------------------------------------------------------


def load_thresholds() -> dict[str, float]:
    """Load thresholds from eval/thresholds.yaml (never hardcoded)."""
    return yaml.safe_load(THRESHOLDS_PATH.read_text())


def compute_pass_rates(
    all_scores: list[dict[str, float]],
) -> dict[str, float]:
    """Compute mean score per judge across all cases."""
    if not all_scores:
        return {name: 0.0 for name in JUDGE_NAMES}
    mean_scores: dict[str, float] = {}
    for judge_name in JUDGE_NAMES:
        values = [s.get(judge_name, 0.0) for s in all_scores]
        mean_scores[judge_name] = sum(values) / len(values)
    return mean_scores


def print_report(
    pass_rates: dict[str, float],
    thresholds: dict[str, float],
    total_cases: int,
) -> list[str]:
    """Print the pass-rate table. Returns list of failing judge names."""
    col_w = max(len(name) for name in JUDGE_NAMES) + 2

    print(f"\n{'=' * 60}")
    print(f"  EVAL RESULTS  ({total_cases} cases)")
    print(f"{'=' * 60}")
    print(f"{'Judge':<{col_w}} {'Pass Rate':>12} {'Threshold':>12} {'Status':>10}")
    print(f"{'-' * col_w} {'-' * 12} {'-' * 12} {'-' * 10}")

    failing: list[str] = []
    for judge_name in JUDGE_NAMES:
        rate = pass_rates.get(judge_name, 0.0)
        threshold = thresholds.get(judge_name, 1.0)
        passed = rate >= threshold
        status = "PASS" if passed else "FAIL"
        if not passed:
            failing.append(judge_name)
        print(f"{judge_name:<{col_w}} {rate:>11.1%} {threshold:>11.1%} {status:>10}")

    print(f"{'=' * 60}")
    if failing:
        print(f"\nFAILING JUDGES: {', '.join(failing)}")
    else:
        print("\nAll judges passed.")
    print()
    return failing


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_eval(
    cases: list[dict[str, Any]] | None = None,
    invoke_fn: Any = None,
) -> tuple[dict[str, float], list[str]]:
    """Run the full eval suite.

    Args:
        cases: Override the loaded cases (for testing).
        invoke_fn: Override the graph invocation function (for testing).

    Returns:
        (pass_rates, failing_judges)
    """
    if cases is None:
        cases = load_cases()

    if invoke_fn is None:
        invoke_fn = _invoke_graph

    thresholds = load_thresholds()
    all_scores: list[dict[str, float]] = []
    run_results: list[dict[str, Any]] = []

    for case in cases:
        case_id = case.get("id", "unknown")
        logger.info("Running case: %s", case_id)
        try:
            state = await invoke_fn(case)
            scores = score_case(state, case)
        except Exception as exc:
            logger.error("Case %s failed during graph invocation: %s", case_id, exc)
            # Score all judges 0.0 for a crashed case
            scores = {name: 0.0 for name in JUDGE_NAMES}
            state = None
        all_scores.append(scores)
        run_results.append({"case": case, "scores": scores, "state": state})
        logger.debug("Case %s scores: %s", case_id, scores)

    pass_rates = compute_pass_rates(all_scores)
    failing = print_report(pass_rates, thresholds, total_cases=len(cases))
    _post_to_langfuse_dataset(run_results)

    return pass_rates, failing


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    _pass_rates, failing = asyncio.run(run_eval())
    if failing:
        sys.exit(1)


if __name__ == "__main__":
    main()
