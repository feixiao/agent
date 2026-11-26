"""Agent evaluation subsystem for agent-in-depth.

Distills core evaluation engineering patterns from google-deepmind/gbench
and Chapter 7 into lightweight, zero-dependency Python modules:
- Two-axis Subject vs. Scaffold versioning (``evals.scaffold``)
- Deterministic Golden Set smoke tests & chat-template twin isolation (``evals.benchmarks``)
- Pass^k / Pass@k reliability, honest reporting, and statistical tail validity (``evals.metrics``)
- Trajectory prefix regression & First Mistake attribution (``evals.prefix_regression``)
- Inspect AI & Harbor contracts (``evals.frameworks``)
"""

from .scaffold import (
    CONTRACT_VERSION,
    ContractField,
    RunCondition,
    ScaffoldSpec,
    SubjectSpec,
    compare_conditions,
)

__all__ = [
    "CONTRACT_VERSION",
    "ContractField",
    "RunCondition",
    "ScaffoldSpec",
    "SubjectSpec",
    "compare_conditions",
]
