"""Unit tests for evals.frameworks (Inspect AI & Harbor) and Chapter 7 demos."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

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
from evals.frameworks.inspect_ai import (
    ExpectedToolError,
    LocalTempSandbox,
    Sample,
    Task,
    ToolDef,
    eval_log_to_suite_outcome,
    eval_log_to_trajectory_steps,
    includes_scorer,
    react_solver,
    run_inspect_task,
)
from evals.prefix_regression.locator import locate_first_mistake


def _load_module(rel_path: str, module_name: str):
    script_path = Path(__file__).resolve().parents[2] / rel_path
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class TestInspectAIFramework(unittest.TestCase):
    def test_expected_tool_error_allows_recovery(self) -> None:
        def _read(args: dict, sb: LocalTempSandbox) -> str:
            return sb.read_file(str(args["path"]))

        tool = ToolDef(
            name="read_file",
            description="Read file",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}},
            handler=_read,
        )
        turns = {"n": 0}

        def _gen(messages, _tools):
            turns["n"] += 1
            if turns["n"] == 1:
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "c1",
                                        "type": "function",
                                        "function": {
                                            "name": "read_file",
                                            "arguments": json.dumps({"path": "missing.txt"}),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            if turns["n"] == 2:
                self.assertIn("ToolError:", messages[-1]["content"])
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "c2",
                                        "type": "function",
                                        "function": {
                                            "name": "read_file",
                                            "arguments": json.dumps({"path": "flag.txt"}),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            return {"choices": [{"message": {"content": messages[-1]["content"]}}]}

        task = Task(
            name="unit_inspect",
            dataset=[Sample(sample_id="s1", input="Find flag", target="FLAG_OK", files={"flag.txt": "FLAG_OK"})],
            solver=react_solver(prompt="Find the flag.", tools=[tool], max_turns=4),
            scorer=includes_scorer(),
        )
        log = run_inspect_task(task, model="mock-model", generate_fn=_gen)
        self.assertEqual(log.passed, 1)
        self.assertEqual(log.errors, 0)
        self.assertTrue(log.samples[0].tool_events[0]["expected_error"])
        self.assertFalse(log.samples[0].tool_events[1]["expected_error"])

    def test_unexpected_sandbox_error_triggers_infra_required(self) -> None:
        task = Task(
            name="broken_inspect",
            dataset=[Sample(sample_id="s1", input="Check", target="OK")],
            solver=react_solver(prompt="", tools=[], max_turns=2),
            scorer=includes_scorer(),
            broken_sandbox=True,
        )
        log = run_inspect_task(task, model="mock-model", generate_fn=lambda _m, _t: {"choices": []})
        self.assertEqual(log.errors, 1)
        self.assertIsNone(log.accuracy)
        outcome = eval_log_to_suite_outcome(log)
        self.assertTrue(outcome.infra_required)
        self.assertIsNone(outcome.score)

    def test_sandbox_path_escape_raises_expected_tool_error(self) -> None:
        with LocalTempSandbox({"a.txt": "ok"}) as sb, self.assertRaises(ExpectedToolError):
            sb.read_file("../outside.txt")

    def test_eval_log_to_trajectory_steps(self) -> None:
        task = Task(
            name="trace_inspect",
            dataset=[Sample(sample_id="s1", input="Answer", target="42")],
            solver=react_solver(prompt="Be concise.", tools=[], max_turns=2),
            scorer=includes_scorer(),
        )
        log = run_inspect_task(
            task,
            model="mock-model",
            generate_fn=lambda _m, _t: {"choices": [{"message": {"content": "99"}}]},
        )
        steps = eval_log_to_trajectory_steps(
            log.samples[0],
            fault_classifier=lambda _idx, m: (
                (False, "model_reasoning", "Wrong numeric answer")
                if m.get("role") == "assistant"
                else (True, "", "")
            ),
        )
        report = locate_first_mistake("s1", steps)
        self.assertTrue(report.found_mistake)
        self.assertEqual(report.fault_layer, "model_reasoning")


class TestHarborFramework(unittest.TestCase):
    def test_error_policy_classification_and_override(self) -> None:
        agent_to = classify_trial_error("AgentTimeoutError")
        self.assertFalse(agent_to.should_retry)
        self.assertTrue(agent_to.should_grade)
        self.assertTrue(agent_to.has_valid_reward)

        rate_lim = classify_trial_error("ApiRateLimitError")
        self.assertTrue(rate_lim.should_retry)
        self.assertTrue(rate_lim.should_grade)
        self.assertFalse(rate_lim.has_valid_reward)

        overridden = classify_trial_error(
            "NonZeroAgentExitCodeError",
            overrides={"NonZeroAgentExitCodeError": {"should_retry": True}},
        )
        self.assertTrue(overridden.should_retry)
        self.assertTrue(overridden.has_valid_reward)

    def test_aggregate_excludes_invalid_rewards(self) -> None:
        trials = [
            HarborTrialResult("t1", "org/task", "claude-code", reward=1.0),
            HarborTrialResult(
                "t2",
                "org/task",
                "claude-code",
                reward=0.0,
                exception_type="AgentTimeoutError",
                policy=classify_trial_error("AgentTimeoutError"),
            ),
            HarborTrialResult(
                "t3",
                "org/task",
                "claude-code",
                reward=1.0,
                exception_type="ApiRateLimitError",
                policy=classify_trial_error("ApiRateLimitError"),
            ),
            HarborTrialResult(
                "t4",
                "org/task",
                "claude-code",
                reward=None,
                exception_type="EnvironmentStartTimeoutError",
                policy=classify_trial_error("EnvironmentStartTimeoutError"),
                verifier_ran=False,
            ),
        ]
        summary = aggregate_harbor_trials(trials)
        self.assertEqual(summary["valid_trials"], 2)
        self.assertEqual(summary["invalid_trials"], 2)
        self.assertEqual(summary["mean_reward"], 0.5)
        self.assertEqual(summary["retryable_trial_ids"], ["t3", "t4"])

    def test_sample_task_bundle_parse_and_lint(self) -> None:
        task_dir = (
            Path(__file__).resolve().parents[2]
            / "experiments"
            / "chapter7"
            / "harbor-eval"
            / "sample_task"
        )
        spec = parse_harbor_task(task_dir)
        self.assertEqual(spec.task_name, "agent-in-depth/fix-service-port")
        self.assertEqual(spec.verifier_environment_mode, "separate")
        self.assertEqual(spec.network_mode, "no-network")
        self.assertEqual(lint_harbor_task(task_dir), [])

    def test_atif_validation_and_prefix_bridge(self) -> None:
        doc = build_atif_trajectory(
            agent_name="codex",
            agent_version="1.0",
            model_name="openai/gpt-5.6-sol",
            steps=[
                ATIFStep(step_id=1, source="user", message="Check config"),
                ATIFStep(
                    step_id=2,
                    source="agent",
                    message="Running command",
                    tool_calls=[{"tool_call_id": "tc1", "function_name": "bash", "arguments": {"cmd": "ls"}}],
                    observation_results=[{"source_call_id": "tc1", "content": "ok"}],
                ),
            ],
        )
        self.assertEqual(validate_atif_trajectory(doc), [])
        steps = atif_to_trajectory_steps(doc)
        self.assertEqual(len(steps), 2)

        bad_doc = dict(doc)
        bad_doc["steps"] = [
            {
                "step_id": 1,
                "source": "agent",
                "message": "bad ref",
                "tool_calls": [{"tool_call_id": "tc1", "function_name": "bash", "arguments": {}}],
                "observation": {"results": [{"source_call_id": "missing_tc", "content": "err"}]},
            }
        ]
        self.assertTrue(len(validate_atif_trajectory(bad_doc)) >= 1)


class TestChapter7InspectAndHarborDemos(unittest.TestCase):
    def test_inspect_demo_mock_scenarios(self) -> None:
        mod = _load_module(
            "experiments/chapter7/inspect-ai-eval/run_inspect_eval_demo.py",
            "run_inspect_eval_demo",
        )
        healthy = mod.run_demo(model="mock-gpt", mock=True, scenario="healthy_recovery")
        self.assertEqual(healthy["eval_log"]["summary"]["passed"], 1)

        mistake = mod.run_demo(model="mock-gpt", mock=True, scenario="model_mistake")
        self.assertEqual(mistake["eval_log"]["summary"]["failed"], 1)
        self.assertTrue(mistake["first_mistake_attribution"]["found_mistake"])

        infra = mod.run_demo(model="mock-gpt", mock=True, scenario="sandbox_infra_error")
        self.assertTrue(infra["suite_outcome"]["infra_required"])
        self.assertIsNone(infra["suite_outcome"]["score"])

    def test_harbor_demo_mock(self) -> None:
        mod = _load_module(
            "experiments/chapter7/harbor-eval/run_harbor_eval_demo.py",
            "run_harbor_eval_demo",
        )
        report = mod.run_demo()
        self.assertEqual(report["task_spec"]["lint_issues"], [])
        self.assertEqual(report["aggregation"]["mean_reward"], 0.5)
        self.assertTrue(report["atif_validation"]["valid"])
        self.assertTrue(report["first_mistake_from_atif"]["found_mistake"])


if __name__ == "__main__":
    unittest.main()
