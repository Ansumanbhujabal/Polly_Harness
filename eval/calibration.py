"""Calibration helpers for the refund-harness eval system.

Used by report.py to compute meta-statistics from §9 of ARCHITECTURE.md:
  - inter_judge_kappa: Cohen's kappa between two judges on the same axis
  - drift_score: two-proportion z-test for regression detection between runs
  - confidence_calibration_ece: Expected Calibration Error for judges that emit
    a continuous confidence score

These are pure statistical functions with no I/O side effects; they do not
call Azure OpenAI, Langfuse, or any external service.
"""

from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)


# ── inter_judge_kappa ─────────────────────────────────────────────────────────


def inter_judge_kappa(scores_a: list[float], scores_b: list[float]) -> float:
    """Compute Cohen's kappa between two judges on binary pass/fail at threshold 0.5.

    Used to track agreement between two judges that score the same axis (e.g.,
    policy_correctness and policy_grounding both scoring A1 cases).  A kappa
    of ≥ 0.7 indicates substantial agreement (ARCHITECTURE.md §9 target).

    Args:
        scores_a: List of float scores from judge A (0.0–1.0).
        scores_b: List of float scores from judge B (0.0–1.0).

    Returns:
        Cohen's kappa in [-1, 1]. Returns 0.0 on degenerate inputs (e.g., both
        judges always agree in the same direction or n=0).

    Raises:
        ValueError: if the lists have different lengths or are empty.
    """
    if len(scores_a) != len(scores_b):
        raise ValueError(
            f"inter_judge_kappa: score lists must have equal length "
            f"(got {len(scores_a)} vs {len(scores_b)})"
        )
    n = len(scores_a)
    if n == 0:
        raise ValueError("inter_judge_kappa: score lists must not be empty")

    # Binarise at 0.5 threshold
    labels_a = [1 if s >= 0.5 else 0 for s in scores_a]
    labels_b = [1 if s >= 0.5 else 0 for s in scores_b]

    # Confusion matrix counts
    tp = sum(1 for a, b in zip(labels_a, labels_b) if a == 1 and b == 1)
    tn = sum(1 for a, b in zip(labels_a, labels_b) if a == 0 and b == 0)
    fp = sum(1 for a, b in zip(labels_a, labels_b) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(labels_a, labels_b) if a == 1 and b == 0)

    # Observed agreement
    p_o = (tp + tn) / n

    # Expected agreement under independence
    p_a1 = (tp + fn) / n  # fraction of A that is positive
    p_b1 = (tp + fp) / n  # fraction of B that is positive
    p_e = p_a1 * p_b1 + (1 - p_a1) * (1 - p_b1)

    # Degenerate: all predictions identical across both judges
    if math.isclose(p_e, 1.0, rel_tol=1e-9):
        logger.debug("inter_judge_kappa: degenerate case (p_e=1.0) — returning 0.0")
        return 0.0

    kappa = (p_o - p_e) / (1.0 - p_e)
    logger.debug(
        "inter_judge_kappa: n=%d p_o=%.4f p_e=%.4f kappa=%.4f", n, p_o, p_e, kappa
    )
    return round(kappa, 6)


# ── drift_score ───────────────────────────────────────────────────────────────


def drift_score(
    baseline_pass_rate: float,
    current_pass_rate: float,
    *,
    n: int,
) -> dict:
    """Two-proportion z-test for axis-level regression detection.

    Compares a baseline pass rate against the current run's pass rate for the
    same judge / axis.  Flags a regression when the drop is both practically
    significant (delta < -0.02) and statistically significant (p < 0.05).

    Args:
        baseline_pass_rate: Pass rate from the baseline run (0.0–1.0).
        current_pass_rate:  Pass rate from the current run (0.0–1.0).
        n:                  Number of cases in the current run (used for SE).

    Returns:
        {
          "delta": float,       # current - baseline (negative = drop)
          "p_value": float,     # two-tailed p-value from z-test
          "regression": bool,   # True if delta < -0.02 AND p < 0.05
        }

    Raises:
        ValueError: if n <= 0 or rates are outside [0, 1].
    """
    if n <= 0:
        raise ValueError(f"drift_score: n must be > 0, got {n}")
    if not (0.0 <= baseline_pass_rate <= 1.0 and 0.0 <= current_pass_rate <= 1.0):
        raise ValueError(
            f"drift_score: pass rates must be in [0, 1] "
            f"(got baseline={baseline_pass_rate}, current={current_pass_rate})"
        )

    delta = current_pass_rate - baseline_pass_rate

    # Pooled proportion for standard error (two-proportion z-test)
    # We assume n cases in each run (same test set size).
    p_pooled = (baseline_pass_rate + current_pass_rate) / 2.0
    se_denom = p_pooled * (1 - p_pooled) * (2 / n)

    if se_denom <= 0 or math.isclose(se_denom, 0.0, abs_tol=1e-12):
        # Edge case: pooled proportion is 0 or 1 (all same outcome)
        logger.debug("drift_score: degenerate SE (p_pooled=%.4f, n=%d) — p_value=1.0", p_pooled, n)
        p_value = 1.0
    else:
        z = delta / math.sqrt(se_denom)
        # Two-tailed p-value via complementary error function approximation
        p_value = 2.0 * (1.0 - _norm_cdf(abs(z)))

    regression = (delta < -0.02) and (p_value < 0.05)

    logger.debug(
        "drift_score: baseline=%.4f current=%.4f delta=%.4f p=%.4f regression=%s",
        baseline_pass_rate,
        current_pass_rate,
        delta,
        p_value,
        regression,
    )

    return {
        "delta": round(delta, 6),
        "p_value": round(p_value, 6),
        "regression": regression,
    }


def _norm_cdf(x: float) -> float:
    """Standard normal CDF via math.erfc (avoids scipy dependency)."""
    return 0.5 * math.erfc(-x / math.sqrt(2))


# ── confidence_calibration_ece ────────────────────────────────────────────────


def confidence_calibration_ece(
    predictions: list[tuple[float, bool]],
    bins: int = 10,
) -> float:
    """Expected Calibration Error (ECE) for a judge that emits confidence scores.

    Bins the predictions by confidence and computes the weighted average of
    |mean_confidence - accuracy| per bin.  A perfectly calibrated judge has
    ECE = 0.0; a judge that is always 90% confident but only right 50% of the
    time would have ECE ≈ 0.4.

    Used to assess per-axis calibration quality (ARCHITECTURE.md §12 roadmap).

    Args:
        predictions: List of (confidence: float 0–1, correct: bool) tuples.
        bins: Number of equal-width bins in [0, 1] (default 10).

    Returns:
        ECE as a float in [0, 1]. Returns 0.0 when predictions is empty.

    Raises:
        ValueError: if bins <= 0 or any confidence value is outside [0, 1].
    """
    if bins <= 0:
        raise ValueError(f"confidence_calibration_ece: bins must be > 0, got {bins}")
    if not predictions:
        logger.debug("confidence_calibration_ece: empty predictions list — returning 0.0")
        return 0.0

    for conf, _ in predictions:
        if not (0.0 <= conf <= 1.0):
            raise ValueError(
                f"confidence_calibration_ece: confidence values must be in [0, 1], got {conf}"
            )

    n = len(predictions)
    bin_width = 1.0 / bins

    ece = 0.0
    for b in range(bins):
        lo = b * bin_width
        hi = lo + bin_width
        # Include the right boundary in the last bin to capture confidence == 1.0
        if b == bins - 1:
            in_bin = [(conf, correct) for conf, correct in predictions if lo <= conf <= hi]
        else:
            in_bin = [(conf, correct) for conf, correct in predictions if lo <= conf < hi]

        if not in_bin:
            continue

        bin_n = len(in_bin)
        mean_conf = sum(c for c, _ in in_bin) / bin_n
        accuracy = sum(1 for _, ok in in_bin if ok) / bin_n
        ece += (bin_n / n) * abs(mean_conf - accuracy)

    logger.debug(
        "confidence_calibration_ece: n=%d bins=%d ECE=%.6f", n, bins, ece
    )
    return round(ece, 6)
