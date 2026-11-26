"""Experiment 7-17: Harbor Task Bundle Lint, ErrorPolicy & ATIF-v1.8 Demo.

Demonstrates Harbor's core container-first evaluation contracts without
requiring Docker or cloud sandbox credentials:
1. Parses and lints ``sample_task/`` (``instruction.md``, ``task.toml``,
   ``environment/Dockerfile``, ``solution/solve.sh``, ``tests/test.sh``).
2. Simulates four Harbor trials across distinct error classifications:
   - Success (``reward=1.0``, ``reward_valid=True``)
   - ``AgentTimeoutError`` (``reward=0.0``, ``reward_valid=True`` -> counts as 0)
   - ``ApiRateLimitError`` (``reward=0.0``, ``reward_valid=False`` -> excluded)
   - ``EnvironmentStartTimeoutError`` (``verifier_ran=False``, ``should_retry=True``,
     ``reward_valid=False`` -> excluded)
3. Builds and validates an ``ATIF-v1.8`` trajectory (``trajectory.json``) and
   maps a failing trajectory into ``evals.prefix_regression.locate_first_mistake``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.frameworks.harbor import (
    ATIFStep,
    HarborTrialResult,
    aggregate_harbor_trials,
    atif_to_trajectory_steps,
    build_atif_trajectory,
    classify_trial_error,
    lint_harbor_task,
    parse_harbor_task,
    validate_atif_trajectory,
)
from evals.prefix_regression.locator import locate_first_mistake

DEFAULT_TASK_DIR = Path(__file__).resolve().parent / "sample_task"


def run_demo(task_dir: Path = DEFAULT_TASK_DIR) -> dict[str, Any]:
    """Run Harbor task validation, error-policy aggregation, and ATIF audit."""
    spec = parse_harbor_task(task_dir)
    lint_issues = lint_harbor_task(task_dir)

    trials = [
        HarborTrialResult(
            trial_id="trial-01-pass",
            task_name=spec.task_name,
            agent_name="claude-code",
            reward=1.0,
            exception_type=None,
            verifier_ran=True,
        ),
        HarborTrialResult(
            trial_id="trial-02-agent-timeout",
            task_name=spec.task_name,
            agent_name="claude-code",
            reward=0.0,
            exception_type="AgentTimeoutError",
            policy=classify_trial_error("AgentTimeoutError"),
            verifier_ran=True,
        ),
        HarborTrialResult(
            trial_id="trial-03-rate-limit",
            task_name=spec.task_name,
            agent_name="claude-code",
            reward=0.0,
            exception_type="ApiRateLimitError",
            policy=classify_trial_error("ApiRateLimitError"),
            verifier_ran=True,
        ),
        HarborTrialResult(
            trial_id="trial-04-env-start-timeout",
            task_name=spec.task_name,
            agent_name="claude-code",
            reward=None,
            exception_type="EnvironmentStartTimeoutError",
            policy=classify_trial_error("EnvironmentStartTimeoutError"),
            verifier_ran=False,
        ),
    ]
    aggregation = aggregate_harbor_trials(trials)

    atif_doc = build_atif_trajectory(
        agent_name="claude-code",
        agent_version="2.1.0",
        model_name="anthropic/claude-sonnet-5-5",
        session_id="harbor-demo-session-01",
        steps=[
            ATIFStep(
                step_id=1,
                source="user",
                message="Update /app/service_config.json port to 8080 and healthcheck_path to /healthz.",
            ),
            ATIFStep(
                step_id=2,
                source="agent",
                message="Inspecting /app/service_config.json first.",
                tool_calls=[
                    {
                        "tool_call_id": "call_read_1",
                        "function_name": "bash",
                        "arguments": {"command": "cat /app/service_config.json"},
                    }
                ],
                observation_results=[
                    {
                        "source_call_id": "call_read_1",
                        "content": '{"port": 3000, "healthcheck_path": "/ping"}',
                    }
                ],
            ),
            ATIFStep(
                step_id=3,
                source="agent",
                message="Writing updated port 8080 but forgetting healthcheck_path.",
                tool_calls=[
                    {
                        "tool_call_id": "call_edit_2",
                        "function_name": "write_file",
                        "arguments": {
                            "path": "/app/service_config.json",
                            "content": '{"port": 8080, "healthcheck_path": "/ping"}',
                        },
                    }
                ],
                observation_results=[
                    {
                        "source_call_id": "call_edit_2",
                        "content": "Updated /app/service_config.json",
                    }
                ],
            ),
        ],
        final_metrics={"total_steps": 3, "reward": 0.0},
    )
    atif_errors = validate_atif_trajectory(atif_doc)

    def _atif_fault(raw_step: dict[str, Any]) -> tuple[bool, str, str]:
        for tc in raw_step.get("tool_calls") or []:
            if tc.get("function_name") == "write_file":
                content = str((tc.get("arguments") or {}).get("content", ""))
                if "/healthz" not in content:
                    return False, "model_reasoning", "Overwrote service_config.json without updating healthcheck_path to /healthz"
        return True, "", ""

    prefix_steps = atif_to_trajectory_steps(atif_doc, step_validator=_atif_fault)
    first_mistake = locate_first_mistake("harbor-demo-session-01", prefix_steps)

    return {
        "task_spec": {
            "task_name": spec.task_name,
            "schema_version": spec.schema_version,
            "verifier_environment_mode": spec.verifier_environment_mode,
            "network_mode": spec.network_mode,
            "lint_issues": lint_issues,
        },
        "trials": [t.to_dict() for t in trials],
        "aggregation": aggregation,
        "atif_validation": {
            "schema_version": atif_doc["schema_version"],
            "valid": len(atif_errors) == 0,
            "errors": atif_errors,
        },
        "first_mistake_from_atif": {
            "found_mistake": first_mistake.found_mistake,
            "first_mistake_index": first_mistake.first_mistake_index,
            "fault_layer": first_mistake.fault_layer,
            "reason": first_mistake.reason,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Experiment 7-17: Harbor Task, ErrorPolicy & ATIF Demo")
    parser.add_argument("--mock", action="store_true", help="Run offline Harbor contract validation demo")
    parser.add_argument("--task-dir", type=Path, default=DEFAULT_TASK_DIR, help="Path to Harbor task directory")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path")
    args = parser.parse_args(argv)

    if not args.mock and not args.task_dir.exists():
        parser.error(f"Task directory not found: {args.task_dir}")

    payload = run_demo(task_dir=args.task_dir)
    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
