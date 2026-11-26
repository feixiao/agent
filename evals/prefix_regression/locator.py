"""Prefix regression & First Mistake attribution for multi-step Agent trajectories.

Implements AGENT.md Criterion 6 ("First Mistake Identification"):
Never attribute a multi-step failure solely to the terminal exception (e.g.
timeout on step 14). Instead, bisect or scan trajectory prefixes to locate the
earliest step where the trajectory deviated from the valid specification and
freeze that prefix as a deterministic regression case.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TrajectoryStep:
    """Single step in an Agent trajectory."""

    step_index: int
    role: str  # "user" | "assistant" | "tool"
    action: str = ""
    observation: str = ""
    is_valid: bool | None = None
    fault_layer: str = ""  # "harness_template" | "tool_contract" | "model_reasoning" | "env_infra"
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FirstMistakeReport:
    """Result of locating the first deviating step in a trajectory."""

    task_id: str
    found_mistake: bool
    first_mistake_index: int | None
    fault_layer: str
    reason: str
    prefix_length: int
    checks_performed: int


@dataclass(frozen=True)
class PrefixRegressionCase:
    """Frozen regression fixture generated from a failing trajectory prefix."""

    case_id: str
    source_task_id: str
    prefix_steps: tuple[TrajectoryStep, ...]
    forbidden_action: str
    expected_fault_layer: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "source_task_id": self.source_task_id,
            "prefix_length": len(self.prefix_steps),
            "prefix_steps": [
                {
                    "step_index": s.step_index,
                    "role": s.role,
                    "action": s.action,
                    "observation": s.observation,
                }
                for s in self.prefix_steps
            ],
            "forbidden_action": self.forbidden_action,
            "expected_fault_layer": self.expected_fault_layer,
            "notes": self.notes,
        }


def locate_first_mistake(
    task_id: str,
    steps: Sequence[TrajectoryStep],
    *,
    prefix_predicate: Callable[[Sequence[TrajectoryStep]], bool] | None = None,
) -> FirstMistakeReport:
    """Locate the earliest invalid step in ``steps``.

    If ``prefix_predicate`` is provided, it must return ``True`` when a prefix
    ``steps[:k]`` is still valid and ``False`` once the mistake has occurred
    (monotonicity assumption), allowing $O(\\log N)$ binary search. Otherwise
    scans ``step.is_valid`` in chronological order.
    """
    if not steps:
        return FirstMistakeReport(
            task_id=task_id,
            found_mistake=False,
            first_mistake_index=None,
            fault_layer="none",
            reason="Empty trajectory",
            prefix_length=0,
            checks_performed=0,
        )

    if prefix_predicate is not None:
        lo, hi = 1, len(steps)
        first_bad_k: int | None = None
        checks = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            checks += 1
            if prefix_predicate(steps[:mid]):
                lo = mid + 1
            else:
                first_bad_k = mid
                hi = mid - 1
        if first_bad_k is None:
            return FirstMistakeReport(
                task_id=task_id,
                found_mistake=False,
                first_mistake_index=None,
                fault_layer="none",
                reason="All prefixes passed predicate",
                prefix_length=len(steps),
                checks_performed=checks,
            )
        bad_step = steps[first_bad_k - 1]
        return FirstMistakeReport(
            task_id=task_id,
            found_mistake=True,
            first_mistake_index=bad_step.step_index,
            fault_layer=bad_step.fault_layer or "model_reasoning",
            reason=bad_step.reason or f"Prefix failed at step {bad_step.step_index}",
            prefix_length=first_bad_k - 1,
            checks_performed=checks,
        )

    for idx, step in enumerate(steps):
        if step.is_valid is False:
            return FirstMistakeReport(
                task_id=task_id,
                found_mistake=True,
                first_mistake_index=step.step_index,
                fault_layer=step.fault_layer or "model_reasoning",
                reason=step.reason or f"Step {step.step_index} marked invalid",
                prefix_length=idx,
                checks_performed=idx + 1,
            )

    return FirstMistakeReport(
        task_id=task_id,
        found_mistake=False,
        first_mistake_index=None,
        fault_layer="none",
        reason="No invalid step found",
        prefix_length=len(steps),
        checks_performed=len(steps),
    )


def build_prefix_regression_case(
    case_id: str,
    task_id: str,
    steps: Sequence[TrajectoryStep],
    report: FirstMistakeReport,
) -> PrefixRegressionCase:
    """Freeze the clean prefix right before the First Mistake into a regression fixture."""
    if not report.found_mistake or report.first_mistake_index is None:
        raise ValueError("Cannot build prefix regression case when no mistake was found")
    prefix = tuple(steps[: report.prefix_length])
    bad_step = steps[report.prefix_length]
    return PrefixRegressionCase(
        case_id=case_id,
        source_task_id=task_id,
        prefix_steps=prefix,
        forbidden_action=bad_step.action,
        expected_fault_layer=report.fault_layer,
        notes=report.reason,
    )
