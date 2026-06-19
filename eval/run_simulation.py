"""eval/run_simulation.py — Production eval runner.

CLI:
    uv run python eval/run_simulation.py \\
        --ground-truth eval/ground_truth.json \\
        --output eval/runs/$(date -u +%Y%m%dT%H%M%S).json \\
        [--baseline eval/runs/baseline.json] \\
        [--max-parallel 4] \\
        [--timeout-s 60] \\
        [--limit N] \\
        [--no-llm-judges] \\
        [--axes A1,A3,A5] \\
        [--append]

Behaviour:
1. Loads ground_truth.json
2. Optionally filters by --axes (comma-separated)
3. Spawns up to --max-parallel async drivers via asyncio.gather + semaphore
4. Each driver:
   - Pre-populates state.customer + state.order from lookup_customer + get_order tools
     (same pattern as scripts/burn_5_cases.py)
   - Calls RefundGraph.ainvoke with a per-case thread_id
   - Wraps in try/except; Azure content_filter exceptions captured as successful blocks
   - Measures latency, captures tool_invocations
   - Returns a CaseRun record
5. After all cases complete, runs all judges (lazy-import missing ones)
6. Calls report.build_report() and writes JSON + EVAL_RESULTS.md
7. If --baseline, runs compile_results.compare() and appends Before/After section
8. Exits non-zero if any block-severity axis pass-rate < threshold OR regressions > 0
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Axes whose failures trigger a non-zero exit
_BLOCK_AXES = {"A1", "A2", "A3", "A4", "A5"}

# Map ground-truth axis IDs (A1–A6) to the judge names that score them
_AXIS_JUDGE_MAP: dict[str, list[str]] = {
    "A1": ["policy_correctness", "policy_grounding"],
    "A2": ["refusal_correctness"],
    "A3": ["injection_resistance"],
    "A4": ["jailbreak_resistance"],
    "A5": ["tool_safety", "hallucination_check"],
    "A6": ["tone_appropriate", "refusal_correctness"],
}

# All judge modules — existing ones + new ones (lazy-imported; skip if missing)
_ALL_JUDGE_MODULES: dict[str, str] = {
    "policy_correctness": "eval.judges.policy_correctness",
    "injection_resistance": "eval.judges.injection_resistance",
    "tone_appropriate": "eval.judges.tone_appropriate",
    "hallucination_check": "eval.judges.hallucination_check",
    # New judges (built by parallel sub-agent; skip if not yet present)
    "refusal_correctness": "eval.judges.refusal_correctness",
    "jailbreak_resistance": "eval.judges.jailbreak_resistance",
    "tool_safety": "eval.judges.tool_safety",
    "policy_grounding": "eval.judges.policy_grounding",
}


# ---------------------------------------------------------------------------
# CRM helpers (mirrors scripts/burn_5_cases.py pattern)
# ---------------------------------------------------------------------------


async def _lookup_customer(customer_id: str) -> Any:
    """Load customer via the lookup_customer tool."""
    try:
        from app.tools import get_tool_by_name  # type: ignore[import]

        tool = get_tool_by_name("lookup_customer")
        if tool is None:
            return None
        result = await tool.run(tool.Input(customer_id=customer_id))
        return getattr(result, "customer", result)
    except Exception as exc:  # noqa: BLE001
        logger.debug("lookup_customer failed for %s: %s", customer_id, exc)
        return None


async def _lookup_order(order_id: str, customer_id: str) -> Any:
    """Load order via the get_order tool."""
    try:
        from app.tools import get_tool_by_name  # type: ignore[import]

        tool = get_tool_by_name("get_order")
        if tool is None:
            return None
        result = await tool.run(tool.Input(order_id=order_id, customer_id=customer_id))
        return getattr(result, "order", result)
    except Exception as exc:  # noqa: BLE001
        logger.debug("get_order failed for %s/%s: %s", order_id, customer_id, exc)
        return None


# ---------------------------------------------------------------------------
# State accessors (handle both dict and AgentState)
# ---------------------------------------------------------------------------


def _get(state: Any, attr: str) -> Any:
    if isinstance(state, dict):
        return state.get(attr)
    return getattr(state, attr, None)


def _final_kind(state: Any) -> str | None:
    fd = _get(state, "final_decision")
    if fd is None:
        return None
    return fd.get("kind") if isinstance(fd, dict) else getattr(fd, "kind", None)


def _final_clauses(state: Any) -> list[str]:
    fd = _get(state, "final_decision")
    if fd is None:
        return []
    if isinstance(fd, dict):
        return fd.get("cited_clause_ids", [])
    return list(getattr(fd, "cited_clause_ids", []))


def _verification_blocked(state: Any) -> bool | None:
    ver = _get(state, "verification")
    if ver is None:
        return None
    if isinstance(ver, dict):
        checks = ver.get("checks", [])
        return any(
            (c.get("severity") == "block" and not c.get("passed", True)) for c in checks
        )
    return getattr(ver, "blocked", None)


def _tool_invocations(state: Any) -> list[str]:
    invs = _get(state, "tool_invocations") or []
    result = []
    for inv in invs:
        if isinstance(inv, dict):
            result.append(inv.get("tool_name", "?"))
        else:
            result.append(getattr(inv, "tool_name", "?"))
    return result


# ---------------------------------------------------------------------------
# Judge loading (lazy, skip missing)
# ---------------------------------------------------------------------------


def _load_judge_functions(no_llm: bool = False) -> dict[str, Any]:
    """Import judge score functions; skip any module that fails to import."""
    loaded: dict[str, Any] = {}
    for judge_name, module_path in _ALL_JUDGE_MODULES.items():
        try:
            import importlib
            mod = importlib.import_module(module_path)
            loaded[judge_name] = mod.score
        except ImportError:
            logger.warning("Judge %s not found at %s — skipping", judge_name, module_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Judge %s failed to load: %s — skipping", judge_name, exc)
    return loaded


def _run_judges(
    state: Any,
    case: dict[str, Any],
    judge_functions: dict[str, Any],
    axis: str,
    no_llm: bool = False,
) -> dict[str, dict[str, Any]]:
    """Run all relevant judges for this axis; return {judge_name: {score, passed, reason}}."""
    relevant_judges = _AXIS_JUDGE_MAP.get(axis, list(judge_functions.keys()))
    results: dict[str, dict[str, Any]] = {}

    for judge_name in relevant_judges:
        fn = judge_functions.get(judge_name)
        if fn is None:
            continue
        try:
            score = fn(state, case)
            results[judge_name] = {
                "score": float(score),
                "passed": float(score) >= 1.0,
                "reason": "",
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Judge %s raised for case %s: %s", judge_name, case.get("case_id"), exc)
            results[judge_name] = {"score": 0.0, "passed": False, "reason": str(exc)}

    return results


# ---------------------------------------------------------------------------
# Single-case driver
# ---------------------------------------------------------------------------


async def _drive_case(
    case: dict[str, Any],
    semaphore: asyncio.Semaphore,
    graph: Any,  # RefundGraph
    judge_functions: dict[str, Any],
    timeout_s: float,
    no_llm: bool,
) -> "CaseRun":  # noqa: F821 — forward ref; import at top of function
    from eval.report import CaseRun

    case_id = case.get("case_id", case.get("id", "unknown"))
    axis = case.get("axis", "A1")
    category = case.get("category", "C1")
    sub_category = case.get("sub_category", "")

    async with semaphore:
        conversation_id = f"eval-{case_id}-{uuid.uuid4().hex[:8]}"
        customer_id = case.get("customer_id", "")
        order_id = case.get("order_id", "")
        user_message = case.get("user_message", "")

        # Pre-populate customer + order (same pattern as burn_5_cases.py)
        customer = await _lookup_customer(customer_id) if customer_id else None
        order = (
            await _lookup_order(order_id, customer_id)
            if order_id and customer_id
            else None
        )

        from app.domain.models import AgentState

        initial_state = AgentState(
            conversation_id=conversation_id,
            messages=[{"role": "user", "content": user_message}],
            stated_email=getattr(customer, "email", None) if customer else None,
            customer=customer,
            order=order,
        )
        config = {"configurable": {"thread_id": conversation_id}}

        start_ts = time.perf_counter()
        final_state: Any = None
        error: str | None = None
        blocked_by: str | None = None

        try:
            final_state = await asyncio.wait_for(
                graph.ainvoke(initial_state, config),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            error = f"TimeoutError: case timed out after {timeout_s}s"
            logger.warning("Case %s timed out", case_id)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            # Azure content_filter exception → treat as successful injection block
            if any(kw in msg for kw in ("content_filter", "ResponsibleAIPolicy", "jailbreak")):
                blocked_by = "azure_content_filter"
                logger.info("Case %s blocked by Azure content filter", case_id)
            else:
                error = f"{type(exc).__name__}: {msg}"
                logger.error("Case %s failed: %s", case_id, error)

        latency_ms = round((time.perf_counter() - start_ts) * 1000, 1)

        # Extract outputs from final state
        if blocked_by == "azure_content_filter":
            actual_kind = "escalate"
            actual_clauses: list[str] = []
            actual_blocked: bool | None = True
            awaiting_approval = False
            response_text: str | None = None
            tool_invs: list[str] = []
        elif final_state is not None:
            actual_kind = _final_kind(final_state)
            # Normalise enum to string
            if hasattr(actual_kind, "value"):
                actual_kind = actual_kind.value
            actual_clauses = _final_clauses(final_state)
            actual_blocked = _verification_blocked(final_state)
            awaiting_approval = bool(_get(final_state, "awaiting_human_approval"))
            response_text = _get(final_state, "response_text")
            tool_invs = _tool_invocations(final_state)
        else:
            actual_kind = None
            actual_clauses = []
            actual_blocked = None
            awaiting_approval = False
            response_text = None
            tool_invs = []

        # Run judges
        state_for_judges = final_state if final_state is not None else initial_state
        judges: dict[str, dict[str, Any]] = {}
        if not error:
            judges = _run_judges(state_for_judges, case, judge_functions, axis, no_llm)

        return CaseRun(
            case_id=case_id,
            axis=axis,
            category=category,
            sub_category=sub_category,
            expected_decision_kind=case.get("expected_decision_kind", ""),
            actual_decision_kind=actual_kind,
            expected_cited_clauses=case.get("expected_cited_clauses", []),
            actual_cited_clauses=actual_clauses,
            expected_verification_blocked=case.get("expected_verification_outcome") == "blocks",
            actual_verification_blocked=actual_blocked,
            awaiting_human_approval=awaiting_approval,
            response_text=response_text,
            tool_invocations=tool_invs,
            latency_ms=latency_ms,
            error=error,
            blocked_by=blocked_by,
            judges=judges,
        )


# ---------------------------------------------------------------------------
# Build report helper (exposed for import in tests / smoke check)
# ---------------------------------------------------------------------------


def _build_report_from_runs(
    runs: list[Any],  # list[CaseRun]
    ground_truth: list[dict[str, Any]],
    thresholds: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> Any:  # Report
    from eval.report import build_report

    return build_report(runs, ground_truth, thresholds, metadata)


# ---------------------------------------------------------------------------
# Main async entrypoint
# ---------------------------------------------------------------------------


async def _run(args: argparse.Namespace) -> int:
    """Run the full evaluation; return exit code."""
    ground_truth_path = Path(args.ground_truth)
    output_path = Path(args.output)
    eval_dir = Path(__file__).parent

    # Load ground truth
    if not ground_truth_path.exists():
        logger.error("Ground truth not found: %s", ground_truth_path)
        return 1

    import json

    raw = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    # Support both {"cases": [...]} wrapper and a bare list
    if isinstance(raw, dict) and "cases" in raw:
        ground_truth: list[dict[str, Any]] = raw["cases"]
    elif isinstance(raw, list):
        ground_truth = raw
    else:
        logger.error("Unexpected ground truth shape: %s", type(raw))
        return 1
    logger.info("Loaded %d ground truth cases from %s", len(ground_truth), ground_truth_path)

    # Filter by axes
    cases = ground_truth
    if args.axes:
        requested = {a.strip() for a in args.axes.split(",")}
        cases = [c for c in cases if c.get("axis", "") in requested]
        logger.info("Filtered to %d cases for axes: %s", len(cases), requested)

    # Limit
    if args.limit and args.limit > 0:
        cases = cases[: args.limit]
        logger.info("Limited to %d cases", len(cases))

    if not cases:
        logger.warning("No cases to run.")
        return 0

    # Load thresholds
    thresholds_path = eval_dir / "thresholds.yaml"
    thresholds = yaml.safe_load(thresholds_path.read_text())

    # Build graph
    logger.info("Building RefundGraph...")
    from app.graph import build_graph

    graph = await build_graph()

    # Load judges
    judge_functions = _load_judge_functions(no_llm=args.no_llm_judges)
    logger.info("Loaded %d judges: %s", len(judge_functions), sorted(judge_functions))

    # Run cases concurrently
    semaphore = asyncio.Semaphore(args.max_parallel)
    tasks = [
        _drive_case(
            case=case,
            semaphore=semaphore,
            graph=graph,
            judge_functions=judge_functions,
            timeout_s=args.timeout_s,
            no_llm=args.no_llm_judges,
        )
        for case in cases
    ]

    logger.info(
        "Running %d cases with max_parallel=%d timeout=%ss",
        len(tasks),
        args.max_parallel,
        args.timeout_s,
    )

    runs = await asyncio.gather(*tasks, return_exceptions=False)

    logger.info("All cases complete. Building report...")

    # Build report
    metadata = {
        "max_parallel": args.max_parallel,
        "timeout_s": args.timeout_s,
        "no_llm_judges": args.no_llm_judges,
        "judges_loaded": sorted(judge_functions.keys()),
        "ground_truth_path": str(ground_truth_path),
    }
    report = _build_report_from_runs(list(runs), ground_truth, thresholds, metadata)

    # Write JSON
    from eval.report import write_json, write_markdown

    write_json(report, output_path)
    logger.info("Run JSON written to: %s", output_path)

    # Write / update EVAL_RESULTS.md
    eval_results_path = eval_dir / "EVAL_RESULTS.md"
    write_markdown(report, eval_results_path)
    logger.info("EVAL_RESULTS.md written to: %s", eval_results_path)

    # Before/After comparison
    exit_code = 0
    if args.baseline:
        baseline_path = Path(args.baseline)
        if baseline_path.exists():
            from eval.compile_results import append_before_after_section, compare, load_run

            baseline_data = load_run(baseline_path)
            import json as _json

            current_data = _json.loads(output_path.read_text(encoding="utf-8"))
            comparison = compare(baseline_data, current_data)
            append_before_after_section(eval_results_path, comparison)
            logger.info("Before/After section appended. Verdict: %s", comparison["verdict"])

            regression_threshold = (
                thresholds.get("regression", {}).get("max_newly_failing", 0)
            )
            if len(comparison["newly_failing"]) > regression_threshold:
                logger.error(
                    "Regression detected: %d newly failing cases (max allowed: %d)",
                    len(comparison["newly_failing"]),
                    regression_threshold,
                )
                exit_code = 1
        else:
            logger.warning("Baseline not found at %s — skipping comparison", baseline_path)

    # Check block-severity axis thresholds
    axis_thresholds = thresholds.get("axes", {})
    for ar in report.axes:
        if ar.axis in _BLOCK_AXES and not ar.threshold_passed:
            logger.error(
                "Block-severity axis %s failed threshold: %.1f%% < %.1f%%",
                ar.axis,
                ar.pass_rate * 100,
                ar.threshold * 100,
            )
            exit_code = 1

    # Print summary
    verdict_str = f"{'✅' if report.overall_verdict == 'PASS' else '❌'} {report.overall_verdict}"
    print(f"\n{'=' * 60}")
    print(f"  EVAL RUN {report.run_id}")
    print(f"  Verdict: {verdict_str}  |  Pass rate: {report.overall_pass_rate:.1%}")
    print(f"  Cases: {report.n_cases}  |  Errors: {report.n_errors}  |  Azure blocks: {report.n_blocked_upstream}")
    print(f"{'=' * 60}")
    for ar in report.axes:
        status = "PASS" if ar.threshold_passed else "FAIL"
        print(f"  {ar.axis:4s}  {ar.pass_rate:.1%}  (threshold {ar.threshold:.1%})  {status}")
    print(f"{'=' * 60}")
    print(f"\nJSON:     {output_path}")
    print(f"Markdown: {eval_results_path}\n")

    return exit_code


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Production eval runner for the refund-harness agent."
    )
    parser.add_argument(
        "--ground-truth",
        default="eval/ground_truth.json",
        help="Path to ground_truth.json",
    )
    parser.add_argument(
        "--output",
        default=f"eval/runs/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json",
        help="Output path for the run JSON",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="Baseline run JSON for before/after comparison",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=4,
        help="Max concurrent graph invocations",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=60.0,
        help="Per-case timeout in seconds",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N cases",
    )
    parser.add_argument(
        "--no-llm-judges",
        action="store_true",
        help="Skip LLM-as-judge calls (offline mode)",
    )
    parser.add_argument(
        "--axes",
        default=None,
        help="Comma-separated axis filter, e.g. A1,A3,A5",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to EVAL_RESULTS.md rather than overwriting",
    )
    return parser


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = _build_parser()
    args = parser.parse_args()
    exit_code = asyncio.run(_run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
