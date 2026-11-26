"""Lightweight Harbor (laude-institute/harbor) task, error-policy & ATIF contract.

Distills Harbor's core container-first evaluation contracts in zero-dependency
Python (stdlib ``tomllib`` + dataclasses):
1. **Task Bundle Spec & Linter** (``instruction.md``, ``task.toml``,
   ``environment/``, ``solution/``, ``tests/test.sh``).
2. **Error Classification Policy** (``ErrorPolicy(should_retry, should_grade,
   has_valid_reward)`` + ``override_error_policy``):
   - Distinguishes agent-caused limits (``AgentTimeoutError`` -> ``reward_valid=True``,
     reward=0.0) from infra/API failures (``EnvironmentStartTimeoutError``,
     ``ApiRateLimitError``, ``VerifierTimeoutError`` -> ``reward_valid=False``).
   - Invalid rewards are excluded from both numerator and denominator in
     mean reward aggregation.
3. **ATIF-v1.8 (Agent Trajectory Interchange Format)** builder, structural
   validator, and adapter to ``evals.prefix_regression.locator.TrajectoryStep``.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evals.prefix_regression.locator import TrajectoryStep

ATIF_SCHEMA_VERSION = "ATIF-v1.8"


@dataclass(frozen=True)
class ErrorPolicy:
    """Harbor trial error policy determining retry, grading, and reward validity."""

    should_retry: bool
    should_grade: bool
    has_valid_reward: bool


# Mirrors Harbor's 5 canonical _POLICY_GROUPS from error_policy.py
_POLICY_GROUPS: list[tuple[ErrorPolicy, tuple[str, ...]]] = [
    (
        ErrorPolicy(should_retry=False, should_grade=True, has_valid_reward=True),
        (
            "NonZeroAgentExitCodeError",
            "AgentTimeoutError",
            "ContextWindowExceededError",
            "OutputTokenExceededError",
            "ContextLengthExceededError",
            "OutputLengthExceededError",
            "AgentSafetyRefusalError",
            "ContentPolicyViolationError",
        ),
    ),
    (
        ErrorPolicy(should_retry=True, should_grade=False, has_valid_reward=False),
        (
            "EnvironmentStartTimeoutError",
            "SandboxBuildFailedError",
            "AgentSetupTimeoutError",
            "HealthcheckError",
            "SandboxLikelyOutOfMemoryError",
            "MemoryLimitExceededError",
            "SSHAccessError",
            "RuntimeRequestError",
            "AddTestsDirError",
            "DownloadVerifierDirError",
        ),
    ),
    (
        ErrorPolicy(should_retry=True, should_grade=True, has_valid_reward=False),
        (
            "ApiError",
            "ApiRateLimitError",
            "ApiInternalServerError",
            "ApiOverloadedError",
            "ApiConnectionClosedError",
            "ApiResponseStalledError",
            "NetworkConnectionError",
            "ApiConnectionError",
            "RateLimitError",
            "ServiceUnavailableError",
            "Timeout",
        ),
    ),
    (
        ErrorPolicy(should_retry=False, should_grade=True, has_valid_reward=False),
        (
            "UnsupportedModelParametersError",
            "BadRequestError",
            "UnprocessableEntityError",
            "BudgetExceededError",
            "VerifierTimeoutError",
            "RewardFileNotFoundError",
            "RewardFileEmptyError",
            "VerifierOutputParseError",
        ),
    ),
    (
        ErrorPolicy(should_retry=False, should_grade=False, has_valid_reward=False),
        (
            "AgentAuthenticationError",
            "ModelNotFoundError",
            "AgentVersionTooOldError",
            "AuthenticationError",
            "PermissionDeniedError",
            "NotFoundError",
            "RegradeError",
            "CancelledError",
        ),
    ),
]

DEFAULT_ERROR_POLICIES: dict[str, ErrorPolicy] = {
    exc_name: policy
    for policy, exc_names in _POLICY_GROUPS
    for exc_name in exc_names
}

_FALLBACK_POLICY = ErrorPolicy(should_retry=True, should_grade=True, has_valid_reward=True)


def classify_trial_error(
    exception_type: str,
    *,
    overrides: Mapping[str, Mapping[str, bool] | ErrorPolicy] | None = None,
) -> ErrorPolicy:
    """Resolve the ``ErrorPolicy`` for a Harbor trial exception type."""
    base = DEFAULT_ERROR_POLICIES.get(exception_type, _FALLBACK_POLICY)
    if not overrides or exception_type not in overrides:
        return base
    ov = overrides[exception_type]
    if isinstance(ov, ErrorPolicy):
        return ov
    return ErrorPolicy(
        should_retry=bool(ov.get("should_retry", base.should_retry)),
        should_grade=bool(ov.get("should_grade", base.should_grade)),
        has_valid_reward=bool(ov.get("has_valid_reward", base.has_valid_reward)),
    )


@dataclass(frozen=True)
class HarborTrialResult:
    """Single Harbor trial outcome with computed ``reward_valid``."""

    trial_id: str
    task_name: str
    agent_name: str
    reward: float | None
    exception_type: str | None = None
    policy: ErrorPolicy | None = None
    verifier_ran: bool = True

    @property
    def reward_valid(self) -> bool:
        if not self.verifier_ran or self.reward is None:
            return False
        if self.exception_type is None:
            return True
        resolved = self.policy or classify_trial_error(self.exception_type)
        return resolved.has_valid_reward

    def to_dict(self) -> dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "task_name": self.task_name,
            "agent_name": self.agent_name,
            "reward": self.reward,
            "reward_valid": self.reward_valid,
            "exception_type": self.exception_type,
            "verifier_ran": self.verifier_ran,
            "policy": None
            if self.policy is None
            else {
                "should_retry": self.policy.should_retry,
                "should_grade": self.policy.should_grade,
                "has_valid_reward": self.policy.has_valid_reward,
            },
        }


def aggregate_harbor_trials(trials: Sequence[HarborTrialResult]) -> dict[str, Any]:
    """Aggregate Harbor trials excluding ``reward_valid=False`` from numerator & denominator."""
    valid_rewards = [float(t.reward) for t in trials if t.reward_valid and t.reward is not None]
    invalid_trials = [t.trial_id for t in trials if not t.reward_valid]
    retryable_trials = [
        t.trial_id
        for t in trials
        if t.exception_type is not None
        and (t.policy or classify_trial_error(t.exception_type)).should_retry
    ]
    mean_reward = round(sum(valid_rewards) / len(valid_rewards), 4) if valid_rewards else None
    return {
        "total_trials": len(trials),
        "valid_trials": len(valid_rewards),
        "invalid_trials": len(invalid_trials),
        "invalid_trial_ids": invalid_trials,
        "retryable_trial_ids": retryable_trials,
        "mean_reward": mean_reward,
    }


@dataclass(frozen=True)
class HarborTaskSpec:
    """Parsed metadata for a Harbor task directory."""

    root: Path
    schema_version: str
    task_name: str
    verifier_timeout_sec: float
    agent_timeout_sec: float
    network_mode: str
    verifier_environment_mode: str
    has_instruction: bool
    has_environment_spec: bool
    has_solution: bool
    has_test_script: bool
    raw_config: dict[str, Any]


def parse_harbor_task(task_dir: Path | str) -> HarborTaskSpec:
    """Parse a Harbor task directory (``task.toml`` + required layout)."""
    root = Path(task_dir)
    toml_path = root / "task.toml"
    if not toml_path.exists():
        raise FileNotFoundError(f"Missing task.toml in {root}")
    data = tomllib.loads(toml_path.read_text(encoding="utf-8"))

    task_tbl = data.get("task") or {}
    verifier_tbl = data.get("verifier") or {}
    agent_tbl = data.get("agent") or {}
    env_tbl = data.get("environment") or {}

    env_dir = root / "environment"
    has_env_spec = bool(env_tbl.get("docker_image")) or any(
        (env_dir / name).exists() for name in ("Dockerfile", "docker-compose.yaml", "Apptainer.def")
    )
    verifier_mode = verifier_tbl.get("environment_mode")
    if verifier_mode is None:
        verifier_mode = "separate" if "environment" in verifier_tbl else "shared"

    return HarborTaskSpec(
        root=root,
        schema_version=str(data.get("schema_version", "1.4")),
        task_name=str(task_tbl.get("name") or root.name),
        verifier_timeout_sec=float(verifier_tbl.get("timeout_sec", 600.0)),
        agent_timeout_sec=float(agent_tbl.get("timeout_sec", 600.0)),
        network_mode=str(env_tbl.get("network_mode", "public")),
        verifier_environment_mode=str(verifier_mode),
        has_instruction=(root / "instruction.md").exists(),
        has_environment_spec=has_env_spec,
        has_solution=(root / "solution" / "solve.sh").exists(),
        has_test_script=(root / "tests" / "test.sh").exists(),
        raw_config=data,
    )


def lint_harbor_task(task_dir: Path | str) -> list[str]:
    """Static checks analogous to ``harbor tasks check`` / lint."""
    root = Path(task_dir)
    issues: list[str] = []
    if not (root / "task.toml").exists():
        issues.append("Missing required task.toml")
        return issues

    spec = parse_harbor_task(root)
    if not spec.has_instruction:
        issues.append("Missing instruction.md")
    elif not (root / "instruction.md").read_text(encoding="utf-8").strip():
        issues.append("instruction.md is empty")

    if not spec.has_environment_spec:
        issues.append("Missing environment spec (environment/Dockerfile or environment.docker_image)")

    if not spec.has_test_script:
        issues.append("Missing tests/test.sh verifier script")
    else:
        test_body = (root / "tests" / "test.sh").read_text(encoding="utf-8")
        if "/logs/verifier/reward" not in test_body:
            issues.append("tests/test.sh does not write /logs/verifier/reward.txt or reward.json")

    if "/" not in spec.task_name:
        issues.append(f"task.name '{spec.task_name}' should use 'org/name' format")

    return issues


@dataclass(frozen=True)
class ATIFStep:
    """Single step in Harbor's Agent Trajectory Interchange Format (ATIF-v1.8)."""

    step_id: int
    source: str  # "system" | "user" | "agent"
    message: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    observation_results: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "step_id": self.step_id,
            "source": self.source,
            "message": self.message,
        }
        if self.tool_calls:
            payload["tool_calls"] = self.tool_calls
        if self.observation_results:
            payload["observation"] = {"results": self.observation_results}
        if self.metrics:
            payload["metrics"] = self.metrics
        return payload


@dataclass(frozen=True)
class ATIFTrajectory:
    """Top-level ATIF-v1.8 trajectory document."""

    agent_name: str
    agent_version: str
    model_name: str
    steps: list[ATIFStep]
    session_id: str = ""
    final_metrics: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": ATIF_SCHEMA_VERSION,
            "agent": {
                "name": self.agent_name,
                "version": self.agent_version,
                "model_name": self.model_name,
            },
            "steps": [s.to_dict() for s in self.steps],
        }
        if self.session_id:
            payload["session_id"] = self.session_id
        if self.final_metrics:
            payload["final_metrics"] = self.final_metrics
        if self.extra:
            payload["extra"] = self.extra
        return payload


def build_atif_trajectory(
    *,
    agent_name: str,
    agent_version: str,
    model_name: str,
    steps: Sequence[ATIFStep],
    session_id: str = "",
    final_metrics: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an ``ATIF-v1.8`` dictionary ready for ``trajectory.json``."""
    return ATIFTrajectory(
        agent_name=agent_name,
        agent_version=agent_version,
        model_name=model_name,
        steps=list(steps),
        session_id=session_id,
        final_metrics=dict(final_metrics or {}),
        extra=dict(extra or {}),
    ).to_dict()


def validate_atif_trajectory(payload: Mapping[str, Any]) -> list[str]:
    """Validate structural ATIF invariants (schema, sequential step_id, call refs)."""
    errors: list[str] = []
    schema_version = str(payload.get("schema_version", ""))
    if not schema_version.startswith("ATIF-v1."):
        errors.append(f"Unsupported schema_version '{schema_version}' (expected ATIF-v1.x)")

    agent = payload.get("agent")
    if not isinstance(agent, Mapping) or not agent.get("name"):
        errors.append("Missing agent.name metadata")

    steps = payload.get("steps")
    if not isinstance(steps, Sequence) or isinstance(steps, (str, bytes)) or len(steps) == 0:
        errors.append("steps must be a non-empty list")
        return errors

    for expected_id, step in enumerate(steps, start=1):
        if not isinstance(step, Mapping):
            errors.append(f"Step {expected_id} is not an object")
            continue
        if step.get("step_id") != expected_id:
            errors.append(f"Expected step_id={expected_id}, got {step.get('step_id')}")
        source = step.get("source")
        if source not in {"system", "user", "agent"}:
            errors.append(f"Step {expected_id} has invalid source '{source}'")

        tool_calls = step.get("tool_calls") or []
        call_ids = {tc.get("tool_call_id") for tc in tool_calls if isinstance(tc, Mapping)}
        observation = step.get("observation") or {}
        for res in observation.get("results") or []:
            src_id = res.get("source_call_id") if isinstance(res, Mapping) else None
            if src_id not in call_ids:
                errors.append(f"Step {expected_id} observation references unknown tool_call_id '{src_id}'")

    return errors


def atif_to_trajectory_steps(
    payload: Mapping[str, Any],
    *,
    step_validator: Any = None,
) -> list[TrajectoryStep]:
    """Convert an ATIF-v1.x trajectory dict into ``TrajectoryStep`` records."""
    steps_out: list[TrajectoryStep] = []
    for raw_step in payload.get("steps") or []:
        source = str(raw_step.get("source", "agent"))
        if source == "system":
            continue
        role = "assistant" if source == "agent" else source
        tool_calls = raw_step.get("tool_calls") or []
        if tool_calls:
            calls = [
                f"{tc.get('function_name', '?')}({tc.get('arguments', {})})"
                for tc in tool_calls
            ]
            action = "; ".join(calls)
        else:
            action = str(raw_step.get("message", ""))

        obs_results = (raw_step.get("observation") or {}).get("results") or []
        observation = "; ".join(str(r.get("content", "")) for r in obs_results)

        is_valid: bool | None = None
        fault_layer = ""
        reason = ""
        if step_validator is not None:
            is_valid, fault_layer, reason = step_validator(raw_step)

        steps_out.append(
            TrajectoryStep(
                step_index=len(steps_out) + 1,
                role=role,
                action=action,
                observation=observation,
                is_valid=is_valid,
                fault_layer=fault_layer,
                reason=reason,
            )
        )
    return steps_out
