"""Reliability metrics (Pass^k, Pass@k, token/cache cost) and honest reporting.

Combines ``agent-in-depth``'s core reliability math (``Pass^k = p^k`` vs
``Pass@k = 1 - (1 - p)^k``) with ``google-deepmind/gbench``'s honest-reporting
contract:
- Infrastructure failures (``infra_required`` / all-error runs) withhold
  ``score`` (``None``) rather than emitting a misleading ``0.0``.
- Any deviation from canonical benchmark conditions marks
  ``leaderboard_comparable = False`` with explicit reasons.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def pass_at_k(single_step_success: float, k: int) -> float:
    """Probability of at least one success in ``k`` independent attempts."""
    if not 0.0 <= single_step_success <= 1.0:
        raise ValueError("single_step_success must be in [0.0, 1.0]")
    if k < 1:
        raise ValueError("k must be >= 1")
    return 1.0 - (1.0 - single_step_success) ** k


def pass_pow_k(single_step_success: float, k: int) -> float:
    """Probability that all ``k`` consecutive steps/trials succeed (Pass^k)."""
    if not 0.0 <= single_step_success <= 1.0:
        raise ValueError("single_step_success must be in [0.0, 1.0]")
    if k < 1:
        raise ValueError("k must be >= 1")
    return single_step_success**k


@dataclass(frozen=True)
class SuiteOutcome:
    """Honest outcome record for an evaluation suite run."""

    suite_id: str
    passed: int
    failed: int
    errors: int
    infra_required: bool = False
    infra_reason: str = ""
    non_canonical_reasons: tuple[str, ...] = ()
    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def scored_total(self) -> int:
        return self.passed + self.failed

    @property
    def score(self) -> float | None:
        if self.infra_required or self.scored_total == 0:
            return None
        return round(self.passed / self.scored_total, 4)

    @property
    def leaderboard_comparable(self) -> bool:
        return not self.infra_required and len(self.non_canonical_reasons) == 0

    @property
    def cache_hit_rate(self) -> float | None:
        if self.prompt_tokens <= 0:
            return None
        return round(self.cached_tokens / self.prompt_tokens, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "status": "infra_required" if self.infra_required else (
                "completed_with_errors" if self.errors > 0 else "success"
            ),
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "score": self.score,
            "infra_required": self.infra_required,
            "infra_reason": self.infra_reason,
            "leaderboard_comparable": self.leaderboard_comparable,
            "non_canonical_reasons": list(self.non_canonical_reasons),
            "prompt_tokens": self.prompt_tokens,
            "cached_tokens": self.cached_tokens,
            "completion_tokens": self.completion_tokens,
            "cache_hit_rate": self.cache_hit_rate,
            "cost_usd": round(self.cost_usd, 6),
        }


def compute_reliability_summary(
    outcomes: list[SuiteOutcome],
    *,
    horizon_k: int = 5,
) -> dict[str, Any]:
    """Aggregate scored suites while preserving honest ``None`` on infra blocks."""
    comparable_scores = [o.score for o in outcomes if o.score is not None]
    mean_single = (
        sum(comparable_scores) / len(comparable_scores) if comparable_scores else None
    )
    total_prompt = sum(o.prompt_tokens for o in outcomes)
    total_cached = sum(o.cached_tokens for o in outcomes)
    return {
        "suites_total": len(outcomes),
        "suites_scored": len(comparable_scores),
        "suites_infra_blocked": sum(1 for o in outcomes if o.infra_required),
        "mean_score": round(mean_single, 4) if mean_single is not None else None,
        "horizon_k": horizon_k,
        "projected_pass_at_k": (
            round(pass_at_k(mean_single, horizon_k), 4) if mean_single is not None else None
        ),
        "projected_pass_pow_k": (
            round(pass_pow_k(mean_single, horizon_k), 4) if mean_single is not None else None
        ),
        "total_cost_usd": round(sum(o.cost_usd for o in outcomes), 6),
        "aggregate_cache_hit_rate": (
            round(total_cached / total_prompt, 4) if total_prompt > 0 else None
        ),
    }
