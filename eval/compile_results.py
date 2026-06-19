"""eval/compile_results.py — before/after diff + regression flag.

Compares a baseline run JSON against a current run JSON and produces:
- Per-axis pass-rate delta
- Per-category pass-rate delta
- Newly-failing case IDs (regressions)
- Newly-passing case IDs (improvements)
- Latency delta (p50, p95)
- Summary verdict: IMPROVED | NEUTRAL | REGRESSED

Append a 'Before / After' section to EVAL_RESULTS.md when called from
the runner or directly via CLI.

CLI:
    uv run python eval/compile_results.py \\
        --baseline eval/runs/baseline.json \\
        --current eval/runs/latest.json \\
        --md eval/EVAL_RESULTS.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Literal


# ---------------------------------------------------------------------------
# Core comparison function
# ---------------------------------------------------------------------------


def compare(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Diff baseline and current run reports.

    Args:
        baseline: Parsed JSON dict from a previous write_json() call.
        current:  Parsed JSON dict from the current write_json() call.

    Returns:
        {
          'per_axis_delta': {axis_id: {'pass_rate_delta': float, 'regressed': bool, ...}},
          'per_category_delta': {...},
          'newly_failing': list[str],     # case IDs passed in baseline, fail now
          'newly_passing': list[str],     # case IDs failed in baseline, pass now
          'latency_delta': {axis_id: {'p50_delta': float, 'p95_delta': float}},
          'verdict': 'IMPROVED' | 'NEUTRAL' | 'REGRESSED',
          'baseline_run_id': str,
          'current_run_id': str,
        }
    """
    base_axes = {ar["axis"]: ar for ar in baseline.get("axes", [])}
    cur_axes = {ar["axis"]: ar for ar in current.get("axes", [])}

    base_cats = baseline.get("categories", {})
    cur_cats = current.get("categories", {})

    # ── Per-axis delta ─────────────────────────────────────────────────────
    per_axis_delta: dict[str, dict[str, Any]] = {}
    all_axes = sorted(set(base_axes) | set(cur_axes))
    for axis in all_axes:
        b = base_axes.get(axis, {})
        c = cur_axes.get(axis, {})
        b_rate = b.get("pass_rate", 0.0)
        c_rate = c.get("pass_rate", 0.0)
        delta = c_rate - b_rate
        per_axis_delta[axis] = {
            "baseline_pass_rate": b_rate,
            "current_pass_rate": c_rate,
            "pass_rate_delta": round(delta, 4),
            "regressed": delta < 0,
            "improved": delta > 0,
        }

    # ── Per-category delta ─────────────────────────────────────────────────
    per_category_delta: dict[str, dict[str, Any]] = {}
    all_cats = sorted(set(base_cats) | set(cur_cats))
    for cat in all_cats:
        b = base_cats.get(cat, {})
        c = cur_cats.get(cat, {})
        b_rate = b.get("pass_rate", 0.0)
        c_rate = c.get("pass_rate", 0.0)
        delta = c_rate - b_rate
        per_category_delta[cat] = {
            "baseline_pass_rate": b_rate,
            "current_pass_rate": c_rate,
            "pass_rate_delta": round(delta, 4),
            "regressed": delta < 0,
            "improved": delta > 0,
        }

    # ── Latency delta ──────────────────────────────────────────────────────
    latency_delta: dict[str, dict[str, Any]] = {}
    for axis in all_axes:
        b = base_axes.get(axis, {})
        c = cur_axes.get(axis, {})
        latency_delta[axis] = {
            "p50_delta": round(c.get("p50_latency_ms", 0.0) - b.get("p50_latency_ms", 0.0), 1),
            "p95_delta": round(c.get("p95_latency_ms", 0.0) - b.get("p95_latency_ms", 0.0), 1),
        }

    # ── Newly failing / passing ────────────────────────────────────────────
    # Build per-case pass/fail sets from the axes' failed_case_ids lists
    base_failed = set()
    for ar in baseline.get("axes", []):
        base_failed.update(ar.get("failed_case_ids", []))

    cur_failed = set()
    for ar in current.get("axes", []):
        cur_failed.update(ar.get("failed_case_ids", []))

    # Collect all known case IDs across both runs
    all_case_ids: set[str] = set()
    for ar in baseline.get("axes", []) + current.get("axes", []):
        all_case_ids.update(ar.get("failed_case_ids", []))

    newly_failing = sorted(cur_failed - base_failed)  # were passing, now failing
    newly_passing = sorted(base_failed - cur_failed)  # were failing, now passing

    # ── Summary verdict ────────────────────────────────────────────────────
    has_regressions = bool(newly_failing)
    has_axis_regression = any(v["regressed"] for v in per_axis_delta.values())

    verdict: Literal["IMPROVED", "NEUTRAL", "REGRESSED"]
    if has_regressions or has_axis_regression:
        verdict = "REGRESSED"
    elif newly_passing or any(v["improved"] for v in per_axis_delta.values()):
        verdict = "IMPROVED"
    else:
        verdict = "NEUTRAL"

    return {
        "per_axis_delta": per_axis_delta,
        "per_category_delta": per_category_delta,
        "newly_failing": newly_failing,
        "newly_passing": newly_passing,
        "latency_delta": latency_delta,
        "verdict": verdict,
        "baseline_run_id": baseline.get("run_id", "unknown"),
        "current_run_id": current.get("run_id", "unknown"),
    }


# ---------------------------------------------------------------------------
# Markdown before/after section
# ---------------------------------------------------------------------------


def append_before_after_section(
    eval_results_md_path: Path,
    comparison: dict[str, Any],
) -> None:
    """Append a '### Before / After (base_ts → cur_ts)' section to EVAL_RESULTS.md."""
    base_ts = comparison.get("baseline_run_id", "baseline")
    cur_ts = comparison.get("current_run_id", "current")
    verdict = comparison.get("verdict", "NEUTRAL")
    verdict_emoji = {"IMPROVED": "✅", "NEUTRAL": "⬜", "REGRESSED": "❌"}.get(verdict, "⬜")

    lines: list[str] = []
    lines.append(f"\n---\n\n### Before / After ({base_ts} → {cur_ts})\n")
    lines.append(f"**Verdict:** {verdict_emoji} {verdict}\n")

    # ── Per-axis table ─────────────────────────────────────────────────────
    lines.append("\n#### Per-Axis Pass-Rate Delta\n")
    lines.append("| Axis | Baseline | Current | Delta | Status |")
    lines.append("|---|---|---|---|---|")
    for axis, d in sorted(comparison.get("per_axis_delta", {}).items()):
        delta_str = f"{d['pass_rate_delta']:+.1%}"
        if d["regressed"]:
            status = "❌ REGRESSED"
        elif d["improved"]:
            status = "✅ IMPROVED"
        else:
            status = "— NEUTRAL"
        lines.append(
            f"| {axis} | {d['baseline_pass_rate']:.1%} | "
            f"{d['current_pass_rate']:.1%} | {delta_str} | {status} |"
        )
    lines.append("")

    # ── Latency delta ──────────────────────────────────────────────────────
    lines.append("\n#### Latency Delta\n")
    lines.append("| Axis | p50 Δ | p95 Δ |")
    lines.append("|---|---|---|")
    for axis, d in sorted(comparison.get("latency_delta", {}).items()):
        p50 = d.get("p50_delta", 0.0)
        p95 = d.get("p95_delta", 0.0)
        lines.append(f"| {axis} | {p50:+.0f}ms | {p95:+.0f}ms |")
    lines.append("")

    # ── Newly failing ──────────────────────────────────────────────────────
    newly_failing = comparison.get("newly_failing", [])
    newly_passing = comparison.get("newly_passing", [])

    if newly_failing:
        lines.append("\n#### Regressions (newly failing)\n")
        for case_id in newly_failing:
            lines.append(f"- `{case_id}`")
        lines.append("")

    if newly_passing:
        lines.append("\n#### Improvements (newly passing)\n")
        for case_id in newly_passing:
            lines.append(f"- `{case_id}`")
        lines.append("")

    if not newly_failing and not newly_passing:
        lines.append("\n_No case-level changes._\n")

    section_text = "\n".join(lines) + "\n"

    if eval_results_md_path.exists():
        existing = eval_results_md_path.read_text(encoding="utf-8")
        eval_results_md_path.write_text(existing + section_text, encoding="utf-8")
    else:
        eval_results_md_path.write_text(section_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_run(path: Path) -> dict[str, Any]:
    """Load a run JSON file and return it as a dict."""
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare two eval run JSON files and append a Before/After section."
    )
    parser.add_argument("--baseline", type=Path, required=True, help="Baseline run JSON path")
    parser.add_argument("--current", type=Path, required=True, help="Current run JSON path")
    parser.add_argument("--md", type=Path, default=Path("eval/EVAL_RESULTS.md"),
                        help="EVAL_RESULTS.md path to append Before/After section")
    args = parser.parse_args()

    if not args.baseline.exists():
        print(f"ERROR: baseline not found: {args.baseline}", file=sys.stderr)
        sys.exit(1)
    if not args.current.exists():
        print(f"ERROR: current not found: {args.current}", file=sys.stderr)
        sys.exit(1)

    baseline = load_run(args.baseline)
    current = load_run(args.current)

    comparison = compare(baseline, current)

    verdict = comparison["verdict"]
    print(f"\nVerdict: {verdict}")
    print(f"Newly failing: {comparison['newly_failing']}")
    print(f"Newly passing: {comparison['newly_passing']}")

    append_before_after_section(args.md, comparison)
    print(f"\nBefore/After section appended to: {args.md}")

    # Exit non-zero on regressions
    if verdict == "REGRESSED":
        sys.exit(1)


if __name__ == "__main__":
    main()
