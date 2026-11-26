"""Experiment 7-15: gBench-style Golden Set, Two-Axis Scaffold Versioning & Tail Validity.

Supports two execution modes:
- ``--mock``: Deterministic offline simulation across four diagnostic scenarios
  (``healthy``, ``broken_template``, ``weak_model``, ``infra_error``), ideal for
  understanding how gBench isolates template/harness defects from model weakness.
- ``--endpoint <URL>/v1 --model <ID>``: Live smoke evaluation against any
  OpenAI-compatible ``/v1`` server (Ollama, vLLM, OpenRouter, etc.).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
from pathlib import Path
from typing import Any

# Allow running directly via `python experiments/chapter7/gbench-eval/run_gbench_local_smoke.py`
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.benchmarks.golden_set import (
    DEFAULT_GOLDEN_CASES,
    SCORING_VERSION,
    GoldenCase,
    GoldenRunner,
)
from evals.metrics.reliability import (
    SuiteOutcome,
    compute_reliability_summary,
)
from evals.metrics.statistics import (
    block_bootstrap_percentile_ci,
    compute_statistics,
    tail_validity,
)
from evals.scaffold import (
    RunCondition,
    ScaffoldSpec,
    SubjectSpec,
    compare_conditions,
)


def _mock_completion_factory(scenario: str):
    """Build deterministic OpenAI-shaped responses for offline smoke scenarios."""

    def _complete(case: GoldenCase) -> dict[str, Any]:
        if scenario == "infra_error":
            raise urllib.error.URLError("Connection refused on http://127.0.0.1:8000/v1")

        if case.case_id == "code_canonical":
            return {
                "choices": [
                    {
                        "message": {
                            "content": "```python\ndef is_palindrome(s: str) -> bool:\n    return s == s[::-1]\n```"
                        }
                    }
                ]
            }

        if case.case_id == "structured_json":
            return {
                "choices": [
                    {"message": {"content": '{"status": "ok", "count": 3}'}}
                ]
            }

        if case.case_id == "function_call_single":
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
                                        "name": "get_weather",
                                        "arguments": '{"city": "Tokyo"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            }

        if case.case_id == "safety_boundary":
            return {
                "choices": [
                    {
                        "message": {
                            "content": "I cannot provide instructions for synthesizing hazardous chemicals."
                        }
                    }
                ]
            }

        if case.case_id == "template_tool_response":
            if scenario == "broken_template":
                # Simulates a chat template dropping the tool turn or leaking template tags
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "<start_of_turn>model I need to look up ORD-4417 first."
                            }
                        }
                    ]
                }
            if scenario == "weak_model":
                return {
                    "choices": [
                        {"message": {"content": "The order status is unknown."}}
                    ]
                }
            return {
                "choices": [
                    {"message": {"content": "Order ORD-4417 is delayed; tracking code is QX7R2M."}}
                ]
            }

        if case.case_id == "template_tool_response_twin":
            if scenario == "weak_model":
                return {
                    "choices": [
                        {"message": {"content": "Sorry, I could not find the tracking code."}}
                    ]
                }
            return {
                "choices": [
                    {"message": {"content": "Tracking code QX7R2M, status: delayed."}}
                ]
            }

        if case.case_id == "template_multi_turn":
            if scenario == "broken_template":
                return {
                    "choices": [
                        {"message": {"content": "I only see the last turn; codes missing."}}
                    ]
                }
            if scenario == "weak_model":
                return {
                    "choices": [
                        {"message": {"content": "I forgot the codes."}}
                    ]
                }
            return {
                "choices": [
                    {"message": {"content": "Project code is K9P4 and region code is Z3W8."}}
                ]
            }

        if case.case_id == "template_multi_turn_twin":
            if scenario == "weak_model":
                return {
                    "choices": [
                        {"message": {"content": "I cannot recall them."}}
                    ]
                }
            return {
                "choices": [
                    {"message": {"content": "K9P4 and Z3W8."}}
                ]
            }

        return {"choices": [{"message": {"content": "ok"}}]}

    return _complete


def run_smoke(
    *,
    model: str,
    endpoint: str | None = None,
    api_key: str | None = None,
    mock: bool = False,
    scenario: str = "healthy",
) -> dict[str, Any]:
    """Execute Golden Set + Scaffold contract + Statistical/Reliability audit."""
    if mock:
        runner = GoldenRunner(
            model=model,
            completion_fn=_mock_completion_factory(scenario),
        )
    else:
        runner = GoldenRunner(
            model=model,
            endpoint=endpoint,
            api_key=api_key,
        )

    golden_report = runner.run(DEFAULT_GOLDEN_CASES)

    # Two-axis Subject vs. Scaffold versioning (gbench/core/scaffold.py pattern)
    base_scaffold = ScaffoldSpec(
        prompt_version="golden-v1",
        schema_version="openai-chat-v1",
        scoring_version=SCORING_VERSION,
        tool_permissions=("get_weather", "lookup_order"),
        attempts=1,
        decode={"temperature": 0.0, "max_tokens": 512},
        dataset_snapshot="golden_set_core_8",
        serving_environment={"backend": "mock" if mock else "openai_v1"},
        load_shape={"batch_sizes": [1]},
    )
    baseline_cond = RunCondition(
        pillar="golden",
        subject=SubjectSpec(model_checkpoint=model, quantization="bf16"),
        scaffold=base_scaffold,
    )
    quant_cond = RunCondition(
        pillar="golden",
        subject=SubjectSpec(model_checkpoint=model, quantization="fp8"),
        scaffold=base_scaffold,
    )
    moved_scaffold_cond = RunCondition(
        pillar="golden",
        subject=SubjectSpec(model_checkpoint=model, quantization="fp8"),
        scaffold=ScaffoldSpec(
            prompt_version="golden-v2",
            schema_version="openai-chat-v1",
            scoring_version=SCORING_VERSION,
            attempts=1,
            decode={"temperature": 0.2, "max_tokens": 512},
        ),
    )

    infra_blocked = golden_report.applicable_total > 0 and golden_report.errors == golden_report.applicable_total
    outcome = SuiteOutcome(
        suite_id="golden_set",
        passed=golden_report.passed,
        failed=golden_report.failed,
        errors=golden_report.errors,
        infra_required=infra_blocked,
        infra_reason="All applicable Golden Set cases failed due to endpoint/infra error" if infra_blocked else "",
        non_canonical_reasons=("offline_mock_mode",) if mock else (),
        prompt_tokens=1600,
        cached_tokens=1024,
        completion_tokens=420,
        cost_usd=0.0 if mock else 0.0012,
    )
    reliability = compute_reliability_summary([outcome], horizon_k=5)

    # Statistical tail-validity demonstration (mirroring gbench/analysis/statistics.py)
    sample_itl_blocks = [
        [18.2, 19.0, 21.4, 20.1],
        [19.5, 22.0, 24.1, 21.8],
        [17.9, 18.4, 19.1, 20.5],
        [25.0, 27.3, 28.1, 26.4],
    ]
    flattened_itl = [x for blk in sample_itl_blocks for x in blk]
    p95_valid, p95_req = tail_validity(len(flattened_itl), 95.0)
    p99_valid, p99_req = tail_validity(len(flattened_itl), 99.0)

    return {
        "scenario": scenario if mock else "live",
        "condition": baseline_cond.to_dict(),
        "condition_comparisons": {
            "quant_sweep_same_scaffold": compare_conditions(baseline_cond, quant_cond),
            "moved_scaffold_and_subject": compare_conditions(baseline_cond, moved_scaffold_cond),
        },
        "golden_report": golden_report.to_dict(),
        "reliability": reliability,
        "suite_outcome": outcome.to_dict(),
        "latency_stats_demo": {
            "summary": compute_statistics(flattened_itl),
            "block_bootstrap_p95": block_bootstrap_percentile_ci(sample_itl_blocks, 95.0, n_boot=200),
            "tail_validity": {
                "n": len(flattened_itl),
                "p95": {"is_valid": p95_valid, "required_n": p95_req},
                "p99": {"is_valid": p99_valid, "required_n": p99_req},
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Experiment 7-15: gBench-style Golden Set & Scaffold Smoke")
    parser.add_argument("--mock", action="store_true", help="Run deterministic offline simulation")
    parser.add_argument(
        "--scenario",
        default="all",
        choices=("all", "healthy", "broken_template", "weak_model", "infra_error"),
        help="Offline mock scenario to run",
    )
    parser.add_argument("--endpoint", default=None, help="OpenAI-compatible /v1 endpoint URL")
    parser.add_argument("--model", default="google/gemma-4-E4B-it", help="Model ID served by endpoint")
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY") or os.getenv("VLLM_API_KEY"))
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path")
    args = parser.parse_args(argv)

    if not args.mock and not args.endpoint:
        parser.error("Provide --mock or --endpoint http://<host>:<port>/v1")

    if args.mock:
        scenarios = (
            ("healthy", "broken_template", "weak_model", "infra_error")
            if args.scenario == "all"
            else (args.scenario,)
        )
        result: Any = {
            sc: run_smoke(model=args.model, mock=True, scenario=sc)
            for sc in scenarios
        }
    else:
        result = run_smoke(
            model=args.model,
            endpoint=args.endpoint,
            api_key=args.api_key,
            mock=False,
        )

    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
