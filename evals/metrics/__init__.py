"""Agent reliability, cost, honest reporting, and statistical validity metrics."""

from .reliability import (
    SuiteOutcome,
    compute_reliability_summary,
    pass_at_k,
    pass_pow_k,
)
from .statistics import (
    block_bootstrap_percentile_ci,
    bootstrap_percentile_ci,
    compute_statistics,
    tail_validity,
)

__all__ = [
    "SuiteOutcome",
    "block_bootstrap_percentile_ci",
    "bootstrap_percentile_ci",
    "compute_reliability_summary",
    "compute_statistics",
    "pass_at_k",
    "pass_pow_k",
    "tail_validity",
]
