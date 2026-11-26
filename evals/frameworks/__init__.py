"""Lightweight reference implementations for Inspect AI and Harbor contracts.

Zero-dependency Python (stdlib-only) models and runners capturing the core
engineering abstractions from:
- ``UKGovernmentBEIS/inspect_ai`` (``Task``, ``Solver``, ``Scorer``,
  ``Sandbox`` expected-vs-unexpected error isolation, and ``EvalLog`` bridge)
- ``laude-institute/harbor`` (``task.toml`` bundle lint/parsing,
  ``ErrorPolicy`` & ``reward_valid`` aggregation, and ``ATIF-v1.8`` trajectory
  validation & ``prefix_regression`` bridge)
"""

from .harbor import (
    ATIF_SCHEMA_VERSION,
    DEFAULT_ERROR_POLICIES,
    ATIFStep,
    ATIFTrajectory,
    ErrorPolicy,
    HarborTaskSpec,
    HarborTrialResult,
    aggregate_harbor_trials,
    atif_to_trajectory_steps,
    build_atif_trajectory,
    classify_trial_error,
    lint_harbor_task,
    parse_harbor_task,
    validate_atif_trajectory,
)
from .inspect_ai import (
    EvalLog,
    ExpectedToolError,
    LocalTempSandbox,
    Sample,
    SampleLog,
    SandboxExecResult,
    Score,
    Task,
    TaskState,
    ToolDef,
    UnexpectedSandboxError,
    eval_log_to_suite_outcome,
    eval_log_to_trajectory_steps,
    exact_scorer,
    includes_scorer,
    react_solver,
    run_inspect_task,
)

__all__ = [
    "ATIF_SCHEMA_VERSION",
    "DEFAULT_ERROR_POLICIES",
    "ATIFStep",
    "ATIFTrajectory",
    "ErrorPolicy",
    "EvalLog",
    "ExpectedToolError",
    "HarborTaskSpec",
    "HarborTrialResult",
    "LocalTempSandbox",
    "Sample",
    "SampleLog",
    "SandboxExecResult",
    "Score",
    "Task",
    "TaskState",
    "ToolDef",
    "UnexpectedSandboxError",
    "aggregate_harbor_trials",
    "atif_to_trajectory_steps",
    "build_atif_trajectory",
    "classify_trial_error",
    "eval_log_to_suite_outcome",
    "eval_log_to_trajectory_steps",
    "exact_scorer",
    "includes_scorer",
    "lint_harbor_task",
    "parse_harbor_task",
    "react_solver",
    "run_inspect_task",
    "validate_atif_trajectory",
]
