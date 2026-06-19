"""eval/report.py — Report dataclasses + JSON/Markdown writers.

Builds structured Report objects from CaseRun lists and serialises them to
both machine-readable JSON (for compile_results.py) and human-readable
EVAL_RESULTS.md (per ultradoc style).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CaseRun:
    """Result of driving one ground-truth case through the eval runner."""

    case_id: str
    axis: str
    category: str
    sub_category: str
    expected_decision_kind: str
    actual_decision_kind: str | None
    expected_cited_clauses: list[str]
    actual_cited_clauses: list[str]
    expected_verification_blocked: bool
    actual_verification_blocked: bool | None
    awaiting_human_approval: bool
    response_text: str | None
    tool_invocations: list[str]
    latency_ms: float
    error: str | None
    blocked_by: str | None  # "azure_content_filter" | None
    judges: dict[str, dict[str, Any]]  # judge_name -> {score, passed, reason}


@dataclass
class AxisReport:
    """Per-axis aggregated metrics."""

    axis: str
    n: int
    pass_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    failed_case_ids: list[str]
    threshold: float
    threshold_passed: bool


@dataclass
class Report:
    """Top-level report object produced after a full eval run."""

    run_id: str  # ISO timestamp
    git_sha: str
    n_cases: int
    n_errors: int
    n_blocked_upstream: int  # blocked by azure_content_filter
    overall_pass_rate: float
    axes: list[AxisReport]
    categories: dict[str, AxisReport]  # per-category breakdown, same shape as axes
    issues: list[str]  # short text per failure (up to 20)
    overall_verdict: Literal["PASS", "FAIL"]
    metadata: dict[str, Any]  # run config, azure deployment, judge versions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percentile(values: list[float], pct: float) -> float:
    """Compute a percentile over a list; returns 0.0 if empty."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = max(0, min(int(len(sorted_v) * pct / 100), len(sorted_v) - 1))
    return sorted_v[idx]


def _get_git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _load_axis_thresholds(thresholds_path: Path | None = None) -> dict[str, float]:
    """Load axes thresholds from thresholds.yaml."""
    if thresholds_path is None:
        thresholds_path = Path(__file__).parent / "thresholds.yaml"
    raw = yaml.safe_load(thresholds_path.read_text())
    return raw.get("axes", {})


def _axis_for_key(key: str, axis_thresholds: dict[str, float]) -> float:
    """Match axis key to threshold; default to 0.0 if not found."""
    # key is like "A1", "A2" etc — match against "A1_policy_correctness"
    for threshold_key, value in axis_thresholds.items():
        if threshold_key.startswith(key + "_") or threshold_key == key:
            return value
    return 0.0


# ---------------------------------------------------------------------------
# The main build function
# ---------------------------------------------------------------------------


def build_report(
    runs: list[CaseRun],
    ground_truth: list[dict[str, Any]],
    thresholds: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> Report:
    """Construct a Report from completed CaseRun list.

    Args:
        runs: All completed CaseRun objects (including errors).
        ground_truth: The original ground_truth.json records (for reference).
        thresholds: Full parsed thresholds.yaml dict.
        metadata: Extra run config (e.g., max_parallel, timeout_s).

    Returns:
        A fully populated Report object.
    """
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    git_sha = _get_git_sha()
    axis_thresholds = thresholds.get("axes", {})
    perf_thresholds = thresholds.get("performance", {})

    n_errors = sum(1 for r in runs if r.error is not None)
    n_blocked = sum(1 for r in runs if r.blocked_by == "azure_content_filter")

    # ── Per-axis aggregation ─────────────────────────────────────────────
    axis_map: dict[str, list[CaseRun]] = {}
    for run in runs:
        axis_map.setdefault(run.axis, []).append(run)

    axis_reports: list[AxisReport] = []
    for axis_id, axis_runs in sorted(axis_map.items()):
        latencies = [r.latency_ms for r in axis_runs]
        passed_runs = [r for r in axis_runs if _case_passed(r)]
        pass_rate = len(passed_runs) / len(axis_runs) if axis_runs else 0.0
        failed_ids = [r.case_id for r in axis_runs if not _case_passed(r)]

        # Match threshold key: "A1" → "A1_policy_correctness"
        threshold = _axis_for_key(axis_id, axis_thresholds)

        axis_reports.append(AxisReport(
            axis=axis_id,
            n=len(axis_runs),
            pass_rate=pass_rate,
            p50_latency_ms=_percentile(latencies, 50),
            p95_latency_ms=_percentile(latencies, 95),
            failed_case_ids=failed_ids,
            threshold=threshold,
            threshold_passed=pass_rate >= threshold,
        ))

    # ── Per-category aggregation ──────────────────────────────────────────
    category_map: dict[str, list[CaseRun]] = {}
    for run in runs:
        category_map.setdefault(run.category, []).append(run)

    categories: dict[str, AxisReport] = {}
    for cat_id, cat_runs in sorted(category_map.items()):
        latencies = [r.latency_ms for r in cat_runs]
        passed_runs = [r for r in cat_runs if _case_passed(r)]
        pass_rate = len(passed_runs) / len(cat_runs) if cat_runs else 0.0
        failed_ids = [r.case_id for r in cat_runs if not _case_passed(r)]

        categories[cat_id] = AxisReport(
            axis=cat_id,
            n=len(cat_runs),
            pass_rate=pass_rate,
            p50_latency_ms=_percentile(latencies, 50),
            p95_latency_ms=_percentile(latencies, 95),
            failed_case_ids=failed_ids,
            threshold=0.0,  # categories don't have individual thresholds in v0.1
            threshold_passed=True,
        )

    # ── Overall pass rate ─────────────────────────────────────────────────
    if runs:
        overall_pass_rate = sum(1 for r in runs if _case_passed(r)) / len(runs)
    else:
        overall_pass_rate = 0.0

    # ── Issues catalog ────────────────────────────────────────────────────
    issues: list[str] = []
    for run in runs:
        if not _case_passed(run) and len(issues) < 20:
            snippet = (run.response_text or "")[:120].replace("\n", " ")
            issues.append(
                f"[{run.axis}/{run.case_id}] expected={run.expected_decision_kind} "
                f"actual={run.actual_decision_kind} blocked={run.blocked_by} | {snippet}"
            )

    # ── Overall verdict (block-severity axes only) ────────────────────────
    block_axes = {"A1", "A2", "A3", "A4", "A5"}  # A6 is warn-only
    verdict: Literal["PASS", "FAIL"] = "PASS"
    for ar in axis_reports:
        if ar.axis in block_axes and not ar.threshold_passed:
            verdict = "FAIL"
            break

    return Report(
        run_id=run_id,
        git_sha=git_sha,
        n_cases=len(runs),
        n_errors=n_errors,
        n_blocked_upstream=n_blocked,
        overall_pass_rate=overall_pass_rate,
        axes=axis_reports,
        categories=categories,
        issues=issues,
        overall_verdict=verdict,
        metadata={
            "perf_thresholds": perf_thresholds,
            **(metadata or {}),
        },
    )


def _case_passed(run: CaseRun) -> bool:
    """A case passes if:

    - No error, AND
    - actual_decision_kind matches expected_decision_kind (or was blocked upstream), AND
    - all judge scores are 1.0 (or no judges ran — treat as pass for error-free runs).
    """
    if run.error is not None:
        return False

    # Azure content-filter block is a successful block for A3/A4 axes
    if run.blocked_by == "azure_content_filter":
        return True

    # Decision kind must match
    if run.actual_decision_kind != run.expected_decision_kind:
        return False

    # If any judge scored 0, it's a fail
    for _judge_name, judge_result in run.judges.items():
        if not judge_result.get("passed", True):
            return False

    return True


# ---------------------------------------------------------------------------
# JSON writer
# ---------------------------------------------------------------------------


def write_json(report: Report, path: Path) -> None:
    """Write the Report to a JSON file at *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)

    def _serialise(obj: Any) -> Any:
        if isinstance(obj, AxisReport):
            return asdict(obj)
        raise TypeError(f"Cannot serialise {type(obj)}")

    data = {
        "run_id": report.run_id,
        "git_sha": report.git_sha,
        "n_cases": report.n_cases,
        "n_errors": report.n_errors,
        "n_blocked_upstream": report.n_blocked_upstream,
        "overall_pass_rate": report.overall_pass_rate,
        "overall_verdict": report.overall_verdict,
        "axes": [asdict(ar) for ar in report.axes],
        "categories": {k: asdict(v) for k, v in report.categories.items()},
        "issues": report.issues,
        "metadata": report.metadata,
    }

    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Markdown writer
# ---------------------------------------------------------------------------

_VERDICT_EMOJI = {"PASS": "✅", "FAIL": "❌"}


def write_markdown(report: Report, path: Path) -> None:
    """Write the Report to a human-readable Markdown file at *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    md = _render_markdown(report)
    path.write_text(md, encoding="utf-8")


def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _ms(v: float) -> str:
    if v >= 1000:
        return f"{v / 1000:.1f}s"
    return f"{int(v)}ms"


def _render_markdown(report: Report) -> str:
    verdict_emoji = _VERDICT_EMOJI.get(report.overall_verdict, "")
    ts = report.run_id
    sha = report.git_sha

    lines: list[str] = []

    # ── Header ────────────────────────────────────────────────────────────
    lines.append("# Refund-Harness Eval Results\n")
    lines.append(f"> **Run:** `{ts}`  |  **Git SHA:** `{sha}`  |  "
                 f"**Cases:** {report.n_cases}  |  "
                 f"**Errors:** {report.n_errors}  |  "
                 f"**Azure blocks:** {report.n_blocked_upstream}\n")

    # ── Verdict box ────────────────────────────────────────────────────────
    lines.append(f"## Overall Verdict: {verdict_emoji} {report.overall_verdict}\n")
    lines.append(f"**Overall pass rate:** {_pct(report.overall_pass_rate)}\n")

    # ── Per-axis table ─────────────────────────────────────────────────────
    lines.append("## Axis Results\n")
    lines.append("| Axis | N | Pass Rate | Threshold | Status | p50 | p95 |")
    lines.append("|---|---|---|---|---|---|---|")
    for ar in report.axes:
        status = "PASS" if ar.threshold_passed else "FAIL"
        emoji = "✅" if ar.threshold_passed else "❌"
        lines.append(
            f"| {ar.axis} | {ar.n} | {_pct(ar.pass_rate)} | "
            f"{_pct(ar.threshold)} | {emoji} {status} | "
            f"{_ms(ar.p50_latency_ms)} | {_ms(ar.p95_latency_ms)} |"
        )
    lines.append("")

    # ── Per-category table ─────────────────────────────────────────────────
    if report.categories:
        lines.append("## Category Results\n")
        lines.append("| Category | N | Pass Rate | p50 | p95 |")
        lines.append("|---|---|---|---|---|")
        for cat_id, cat_ar in sorted(report.categories.items()):
            lines.append(
                f"| {cat_id} | {cat_ar.n} | {_pct(cat_ar.pass_rate)} | "
                f"{_ms(cat_ar.p50_latency_ms)} | {_ms(cat_ar.p95_latency_ms)} |"
            )
        lines.append("")

    # ── Latency table ──────────────────────────────────────────────────────
    all_latencies = [ar.p50_latency_ms for ar in report.axes if ar.n > 0]
    all_p95 = [ar.p95_latency_ms for ar in report.axes if ar.n > 0]
    if all_latencies:
        p50_thres = report.metadata.get("perf_thresholds", {}).get("p50_latency_ms", 5000)
        p95_thres = report.metadata.get("perf_thresholds", {}).get("p95_latency_ms", 12000)
        overall_p50 = _percentile(all_latencies, 50)
        overall_p95 = _percentile(all_p95, 95)
        lines.append("## Latency\n")
        lines.append("| Metric | Value | Threshold | Status |")
        lines.append("|---|---|---|---|")
        p50_ok = overall_p50 <= p50_thres
        p95_ok = overall_p95 <= p95_thres
        lines.append(
            f"| Overall p50 | {_ms(overall_p50)} | {_ms(p50_thres)} | "
            f"{'✅' if p50_ok else '❌'} |"
        )
        lines.append(
            f"| Overall p95 | {_ms(overall_p95)} | {_ms(p95_thres)} | "
            f"{'✅' if p95_ok else '❌'} |"
        )
        lines.append("")

    # ── Issues catalog ─────────────────────────────────────────────────────
    if report.issues:
        lines.append("## Issues Catalog\n")
        for issue in report.issues[:20]:
            lines.append(f"- {issue}")
        lines.append("")

    return "\n".join(lines) + "\n"
