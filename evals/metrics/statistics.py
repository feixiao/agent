"""Statistical rigor utilities adapted from google-deepmind/gbench.

Pure-Python (stdlib-only) implementation of key checks from
``gbench/analysis/statistics.py``:
- ``compute_statistics``: single-value ``std`` is ``None`` (never fake ``0``).
- ``tail_validity``: checks whether sample size ``n`` supports a stable ``p``-th
  percentile (e.g. P95 needs >= 200, P99 needs >= 1000 for ``min_tail=10``).
- ``bootstrap_percentile_ci``: iid percentile + bootstrap CI.
- ``block_bootstrap_percentile_ci``: block-level bootstrap preserving
  within-request / within-trajectory autocorrelation.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from typing import Any


def _linear_percentile(sorted_vals: Sequence[float], p: float) -> float:
    """Linear-interpolation percentile matching ``numpy.percentile`` default."""
    n = len(sorted_vals)
    if n == 0:
        raise ValueError("Cannot compute percentile of empty sequence")
    if n == 1:
        return float(sorted_vals[0])
    rank = (p / 100.0) * (n - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    frac = rank - lo
    return float(sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac)


def compute_statistics(values: Sequence[float]) -> dict[str, float | int | None]:
    """Compute descriptive statistics without fabricating dispersion for n < 2."""
    clean = [float(v) for v in values if math.isfinite(float(v))]
    n = len(clean)
    if n == 0:
        return {}

    ordered = sorted(clean)
    mean_val = sum(ordered) / n
    median_val = _linear_percentile(ordered, 50.0)

    if n > 1:
        var = sum((x - mean_val) ** 2 for x in ordered) / (n - 1)
        std_val: float | None = math.sqrt(var)
    else:
        std_val = None

    cv_percent = (std_val / mean_val) * 100.0 if (std_val is not None and mean_val > 0) else None
    return {
        "mean": mean_val,
        "median": median_val,
        "std": std_val,
        "min": ordered[0],
        "max": ordered[-1],
        "count": n,
        "cv_percent": cv_percent,
    }


def tail_validity(n: int, p: float, min_tail: int = 10) -> tuple[bool, int]:
    """Check whether sample size ``n`` has >= ``min_tail`` points in the tail."""
    if not 0.0 < p < 100.0:
        return False, 0
    frac = (1.0 - p / 100.0) if p >= 50.0 else (p / 100.0)
    if frac <= 0.0:
        return False, 0
    required = math.ceil(round(min_tail / frac, 6))
    return n >= required, required


def bootstrap_percentile_ci(
    samples: Sequence[float],
    p: float,
    *,
    n_boot: int = 1000,
    ci: float = 0.95,
    seed: int = 83,
) -> dict[str, Any]:
    """Point estimate + bootstrap CI for the p-th percentile of iid samples."""
    clean = [float(x) for x in samples if math.isfinite(float(x))]
    n = len(clean)
    if n == 0:
        return {"value": None, "ci_low": None, "ci_high": None, "n": 0}

    ordered = sorted(clean)
    point = _linear_percentile(ordered, p)
    if n < 2:
        return {"value": point, "ci_low": point, "ci_high": point, "n": n}

    rng = random.Random(seed)
    boot_vals: list[float] = []
    for _ in range(n_boot):
        resample = sorted(clean[rng.randrange(n)] for _ in range(n))
        boot_vals.append(_linear_percentile(resample, p))
    boot_vals.sort()

    lo_p = (1.0 - ci) / 2.0 * 100.0
    hi_p = (1.0 + ci) / 2.0 * 100.0
    return {
        "value": point,
        "ci_low": _linear_percentile(boot_vals, lo_p),
        "ci_high": _linear_percentile(boot_vals, hi_p),
        "n": n,
    }


def block_bootstrap_percentile_ci(
    blocks: Sequence[Sequence[float]],
    p: float,
    *,
    n_boot: int = 500,
    ci: float = 0.95,
    seed: int = 83,
) -> dict[str, Any]:
    """Block-bootstrap percentile CI preserving within-block autocorrelation.

    Resamples whole requests/trajectories (blocks) rather than individual
    tokens or steps so serially correlated decode/step latencies do not produce
    artificially narrow confidence intervals.
    """
    clean_blocks = [
        [float(x) for x in block if math.isfinite(float(x))]
        for block in blocks
    ]
    clean_blocks = [b for b in clean_blocks if b]
    if not clean_blocks:
        return {"value": None, "ci_low": None, "ci_high": None, "n_blocks": 0, "n_samples": 0}

    pooled = sorted(x for b in clean_blocks for x in b)
    point = _linear_percentile(pooled, p)
    n_blocks = len(clean_blocks)
    if n_blocks < 2:
        return {
            "value": point,
            "ci_low": point,
            "ci_high": point,
            "n_blocks": n_blocks,
            "n_samples": len(pooled),
        }

    rng = random.Random(seed)
    boot_vals: list[float] = []
    for _ in range(n_boot):
        chosen = [clean_blocks[rng.randrange(n_blocks)] for _ in range(n_blocks)]
        merged = sorted(x for b in chosen for x in b)
        boot_vals.append(_linear_percentile(merged, p))
    boot_vals.sort()

    lo_p = (1.0 - ci) / 2.0 * 100.0
    hi_p = (1.0 + ci) / 2.0 * 100.0
    return {
        "value": point,
        "ci_low": _linear_percentile(boot_vals, lo_p),
        "ci_high": _linear_percentile(boot_vals, hi_p),
        "n_blocks": n_blocks,
        "n_samples": len(pooled),
    }
