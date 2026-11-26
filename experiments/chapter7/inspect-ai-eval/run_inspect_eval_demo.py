"""Experiment 7-16: Inspect AI-style Composable Task/Solver/Sandbox/Scorer Eval.

Supports two execution modes:
- ``--mock``: Deterministic offline demonstration of Inspect AI's core design:
  1. ``healthy_recovery``: Model hits an ``ExpectedToolError`` (missing file),
     receives the tool error in context, self-corrects, and passes.
  2. ``model_mistake``: Model enters wrong path / incomplete solution, fails
     scoring, and ``eval_log_to_trajectory_steps`` feeds ``locate_first_mistake``
     to pinpoint the exact deviating turn.
  3. ``sandbox_infra_error``: ``UnexpectedSandboxError`` aborts the sample as
     ``status="error"`` and ``SuiteOutcome(infra_required=True, score=None)``.
- ``--endpoint <URL>/v1 --model <ID>``: Live execution against any
  OpenAI-compatible ``/v1`` server.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.benchmarks.golden_set import openai_chat_completion
from evals.frameworks.inspect_ai import (
    EvalLog,
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
from evals.metrics.reliability import compute_reliability_summary
from evals.prefix_regression.locator import locate_first_mistake


def _build_sandbox_tools() -> list[ToolDef]:
    def _read_file(args: dict[str, Any], sb: LocalTempSandbox) -> str:
        path = str(args.get("path") or "")
        if not path:
            raise ExpectedToolError("'path' argument is required")
        return sb.read_file(path)

    def _run_python(args: dict[str, Any], sb: LocalTempSandbox) -> str:
        code = str(args.get("code") or "")
        if not code:
            raise ExpectedToolError("'code' argument is required")
        res = sb.exec([sys.executable, "-c", code])
        if not res.success:
            raise ExpectedToolError(f"Exit {res.returncode}: {res.stderr.strip()}")
        return res.stdout.strip() or "(no output)"

    return [
        ToolDef(
            name="read_file",
            description="Read a UTF-8 file inside the isolated sandbox.",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            handler=_read_file,
        ),
        ToolDef(
            name="run_python",
            description="Execute a short Python snippet inside the sandbox.",
            parameters={
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
            },
            handler=_run_python,
        ),
    ]


def _mock_generate_factory(scenario: str):
    """Deterministic multi-turn mock chat-completion function."""
    turn_counter = {"n": 0}

    def _generate(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        del tools
        turn_counter["n"] += 1
        step = turn_counter["n"]

        if scenario == "healthy_recovery":
            if step == 1:
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "read_file",
                                            "arguments": json.dumps({"path": "config/missing.txt"}),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            if step == 2:
                # Model observes ExpectedToolError and recovers by reading the real file
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_2",
                                        "type": "function",
                                        "function": {
                                            "name": "read_file",
                                            "arguments": json.dumps({"path": "secret_flag.txt"}),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            last_obs = str(messages[-1].get("content", ""))
            return {
                "choices": [
                    {"message": {"content": f"Verified flag inside sandbox: {last_obs.strip()}"}}
                ]
            }

        if scenario == "model_mistake":
            if step == 1:
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_err",
                                        "type": "function",
                                        "function": {
                                            "name": "read_file",
                                            "arguments": json.dumps({"path": "wrong_notes.txt"}),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            return {
                "choices": [
                    {"message": {"content": "Unable to locate flag; reporting placeholder FLAG-000."}}
                ]
            }

        return {"choices": [{"message": {"content": "unreachable"}}]}

    return _generate


def run_demo(
    *,
    model: str,
    endpoint: str | None = None,
    api_key: str | None = None,
    mock: bool = False,
    scenario: str = "healthy_recovery",
) -> dict[str, Any]:
    """Run Inspect-style Task -> Solver -> Sandbox -> Scorer + First-Mistake bridge."""
    dataset = [
        Sample(
            sample_id="ctf_flag_check",
            input="Inspect the sandbox workspace and report the exact flag stored in secret_flag.txt.",
            target="FLAG{inspect_sandbox_ok}",
            files={
                "secret_flag.txt": "FLAG{inspect_sandbox_ok}\n",
                "wrong_notes.txt": "decoy file\n",
            },
        )
    ]
    task = Task(
        name="sandbox_flag_probe",
        dataset=dataset,
        solver=react_solver(
            prompt="You are a sandbox security analyst. Use tools to verify files before answering.",
            tools=_build_sandbox_tools(),
            max_turns=6,
        ),
        scorer=includes_scorer(ignore_case=False),
        sandbox_type="local_temp",
        broken_sandbox=(mock and scenario == "sandbox_infra_error"),
    )

    if mock:
        generate_fn = _mock_generate_factory(scenario)
        non_canonical = ("offline_mock_mode",)
    else:
        if not endpoint:
            raise ValueError("endpoint is required when mock=False")

        def _live_generate(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
            return openai_chat_completion(
                endpoint=endpoint,
                model=model,
                messages=messages,
                tools=tools,
                api_key=api_key,
            )

        generate_fn = _live_generate
        non_canonical = ()

    eval_log: EvalLog = run_inspect_task(task, model=model, generate_fn=generate_fn)
    suite_outcome = eval_log_to_suite_outcome(eval_log, non_canonical_reasons=non_canonical)
    reliability = compute_reliability_summary([suite_outcome], horizon_k=5)

    first_mistake_report = None
    if eval_log.samples and eval_log.samples[0].status == "failed":
        def _classify(_idx: int, msg: dict[str, Any]) -> tuple[bool, str, str]:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                args_str = str(msg["tool_calls"][0].get("function", {}).get("arguments", ""))
                if "wrong_notes.txt" in args_str:
                    return False, "model_reasoning", "Agent inspected wrong_notes.txt instead of secret_flag.txt"
            return True, "", ""

        steps = eval_log_to_trajectory_steps(eval_log.samples[0], fault_classifier=_classify)
        report = locate_first_mistake(eval_log.samples[0].sample_id, steps)
        first_mistake_report = {
            "found_mistake": report.found_mistake,
            "first_mistake_index": report.first_mistake_index,
            "fault_layer": report.fault_layer,
            "reason": report.reason,
        }

    return {
        "scenario": scenario if mock else "live",
        "eval_log": eval_log.to_dict(),
        "suite_outcome": suite_outcome.to_dict(),
        "reliability": reliability,
        "first_mistake_attribution": first_mistake_report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Experiment 7-16: Inspect AI Task/Solver/Sandbox Demo")
    parser.add_argument("--mock", action="store_true", help="Run offline deterministic scenarios")
    parser.add_argument(
        "--scenario",
        default="all",
        choices=("all", "healthy_recovery", "model_mistake", "sandbox_infra_error"),
        help="Offline scenario to run",
    )
    parser.add_argument("--endpoint", default=None, help="OpenAI-compatible /v1 endpoint URL")
    parser.add_argument("--model", default="openai/gpt-4.1-mini", help="Model ID")
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path")
    args = parser.parse_args(argv)

    if not args.mock and not args.endpoint:
        parser.error("Provide --mock or --endpoint http://<host>:<port>/v1")

    if args.mock:
        scenarios = (
            ("healthy_recovery", "model_mistake", "sandbox_infra_error")
            if args.scenario == "all"
            else (args.scenario,)
        )
        payload: Any = {
            sc: run_demo(model=args.model, mock=True, scenario=sc)
            for sc in scenarios
        }
    else:
        payload = run_demo(
            model=args.model,
            endpoint=args.endpoint,
            api_key=args.api_key,
            mock=False,
        )

    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
