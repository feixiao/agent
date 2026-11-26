"""Unit tests for evals/ subsystem and Chapter 7 gbench-eval smoke runner."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from evals.benchmarks.golden_set import (
    DEFAULT_GOLDEN_CASES,
    GoldenCase,
    GoldenRunner,
)
from evals.metrics.reliability import (
    SuiteOutcome,
    compute_reliability_summary,
    pass_at_k,
    pass_pow_k,
)
from evals.metrics.statistics import (
    block_bootstrap_percentile_ci,
    bootstrap_percentile_ci,
    compute_statistics,
    tail_validity,
)
from evals.prefix_regression.locator import (
    TrajectoryStep,
    build_prefix_regression_case,
    locate_first_mistake,
)
from evals.scaffold import (
    RunCondition,
    ScaffoldSpec,
    SubjectSpec,
    compare_conditions,
)


def _load_smoke_module():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "experiments"
        / "chapter7"
        / "gbench-eval"
        / "run_gbench_local_smoke.py"
    )
    spec = importlib.util.spec_from_file_location("run_gbench_local_smoke", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_gbench_local_smoke"] = module
    spec.loader.exec_module(module)
    return module


class TestEvalsScaffold(unittest.TestCase):
    def test_two_axis_comparability_rules(self) -> None:
        scaffold_a = ScaffoldSpec(
            prompt_version="v1",
            schema_version="v1",
            scoring_version=1,
            decode={"temperature": 0.0},
            load_shape={"batch_sizes": [1, 8]},
        )
        scaffold_b = ScaffoldSpec(
            prompt_version="v2",
            schema_version="v1",
            scoring_version=1,
            decode={"temperature": 0.0},
            load_shape={"batch_sizes": [1, 8]},
        )
        cond_base = RunCondition(
            pillar="golden",
            subject=SubjectSpec(model_checkpoint="gemma-4-12b", quantization="bf16"),
            scaffold=scaffold_a,
        )
        cond_quant = RunCondition(
            pillar="golden",
            subject=SubjectSpec(model_checkpoint="gemma-4-12b", quantization="fp8"),
            scaffold=scaffold_a,
        )
        cond_new_prompt = RunCondition(
            pillar="golden",
            subject=SubjectSpec(model_checkpoint="gemma-4-12b", quantization="bf16"),
            scaffold=scaffold_b,
        )
        cond_both = RunCondition(
            pillar="golden",
            subject=SubjectSpec(model_checkpoint="gemma-4-12b", quantization="fp8"),
            scaffold=scaffold_b,
        )

        self.assertEqual(compare_conditions(cond_base, cond_base)["verdict"], "identical")
        quant_cmp = compare_conditions(cond_base, cond_quant)
        self.assertTrue(quant_cmp["comparable"])
        self.assertEqual(quant_cmp["verdict"], "valid_subject_delta")

        prompt_cmp = compare_conditions(cond_base, cond_new_prompt)
        self.assertFalse(prompt_cmp["comparable"])
        self.assertEqual(prompt_cmp["verdict"], "scaffold_changed_break_series")

        both_cmp = compare_conditions(cond_base, cond_both)
        self.assertFalse(both_cmp["comparable"])
        self.assertEqual(both_cmp["verdict"], "both_changed_uninterpretable")

    def test_honest_unpinned_coverage(self) -> None:
        empty_cond = RunCondition(
            pillar="evals",
            subject=SubjectSpec(model_checkpoint="qwen2.5-7b"),
            scaffold=ScaffoldSpec(),
        )
        data = empty_cond.to_dict()
        self.assertIsNone(data["scaffold_id"])
        self.assertEqual(data["scaffold"]["covers"], [])
        self.assertIn("decode", data["scaffold"]["unpinned"])
        self.assertEqual(data["subject"]["unpinned"], ["quantization"])


class TestGoldenSetAndPairs(unittest.TestCase):
    def test_broken_template_vs_healthy_and_weak_model(self) -> None:
        run_smoke = _load_smoke_module().run_smoke

        healthy = run_smoke(model="test-model", mock=True, scenario="healthy")
        self.assertEqual(healthy["golden_report"]["passed"], len(DEFAULT_GOLDEN_CASES))
        self.assertEqual(healthy["golden_report"]["pass_rate"], 100.0)
        self.assertTrue(
            all(p["diagnosis"] == "healthy" for p in healthy["golden_report"]["pair_diagnostics"])
        )

        broken = run_smoke(model="test-model", mock=True, scenario="broken_template")
        pair_diags = {
            p["pair_id"]: p["diagnosis"]
            for p in broken["golden_report"]["pair_diagnostics"]
        }
        self.assertEqual(pair_diags["tool_response_serialization"], "template_broken")
        self.assertEqual(pair_diags["multi_turn_history"], "template_broken")

        weak = run_smoke(model="test-model", mock=True, scenario="weak_model")
        weak_diags = {
            p["pair_id"]: p["diagnosis"]
            for p in weak["golden_report"]["pair_diagnostics"]
        }
        self.assertEqual(weak_diags["tool_response_serialization"], "model_weak")
        self.assertEqual(weak_diags["multi_turn_history"], "model_weak")

        infra = run_smoke(model="test-model", mock=True, scenario="infra_error")
        self.assertIsNone(infra["golden_report"]["pass_rate"])
        self.assertTrue(infra["suite_outcome"]["infra_required"])
        self.assertIsNone(infra["suite_outcome"]["score"])

    def test_modality_exclusion_and_leaked_token_detection(self) -> None:
        cases = [
            GoldenCase(
                case_id="vision_case",
                category="multimodal_vision",
                match_type="contains_all",
                messages=[{"role": "user", "content": "Describe image"}],
                expected_outputs=("star",),
                required_modality="image",
            ),
            GoldenCase(
                case_id="leak_case",
                category="chat_template",
                match_type="contains_all",
                messages=[{"role": "user", "content": "Say hi"}],
                expected_outputs=("hi",),
                forbid_chat_template_tokens=True,
            ),
        ]

        runner = GoldenRunner(
            model="text-only",
            supported_modalities=frozenset({"text"}),
            completion_fn=lambda _c: {"choices": [{"message": {"content": "hi <|im_end|>"}}]},
        )
        report = runner.run(cases)
        self.assertEqual(report.not_applicable, 1)
        self.assertEqual(report.applicable_total, 1)
        self.assertEqual(report.failed, 1)
        self.assertEqual(report.pass_rate, 0.0)


class TestMetricsStatisticsAndPrefixRegression(unittest.TestCase):
    def test_reliability_math_and_honest_reporting(self) -> None:
        self.assertAlmostEqual(pass_pow_k(0.6, 5), 0.07776, places=5)
        self.assertAlmostEqual(pass_at_k(0.6, 5), 0.98976, places=5)

        blocked = SuiteOutcome(
            suite_id="quality",
            passed=0,
            failed=0,
            errors=1,
            infra_required=True,
            infra_reason="context_window <= 8192",
        )
        self.assertIsNone(blocked.score)
        self.assertFalse(blocked.leaderboard_comparable)

        ok = SuiteOutcome(
            suite_id="golden_set",
            passed=8,
            failed=2,
            errors=0,
            prompt_tokens=1000,
            cached_tokens=800,
        )
        self.assertEqual(ok.score, 0.8)
        self.assertEqual(ok.cache_hit_rate, 0.8)
        summary = compute_reliability_summary([blocked, ok], horizon_k=5)
        self.assertEqual(summary["suites_infra_blocked"], 1)
        self.assertEqual(summary["suites_scored"], 1)
        self.assertAlmostEqual(summary["mean_score"], 0.8, places=4)

    def test_statistics_tail_validity_and_bootstrap(self) -> None:
        single = compute_statistics([42.0])
        self.assertIsNone(single["std"])
        self.assertIsNone(single["cv_percent"])

        self.assertEqual(tail_validity(199, 95.0), (False, 200))
        self.assertEqual(tail_validity(200, 95.0), (True, 200))
        self.assertEqual(tail_validity(999, 99.0), (False, 1000))
        self.assertEqual(tail_validity(1000, 99.0), (True, 1000))

        iid_ci = bootstrap_percentile_ci([10.0, 12.0, 14.0, 16.0, 20.0], 95.0, n_boot=100)
        self.assertLessEqual(iid_ci["ci_low"], iid_ci["value"])
        self.assertLessEqual(iid_ci["value"], iid_ci["ci_high"])

        blk_ci = block_bootstrap_percentile_ci([[10.0, 11.0], [15.0, 16.0], [20.0, 25.0]], 95.0, n_boot=100)
        self.assertEqual(blk_ci["n_blocks"], 3)
        self.assertEqual(blk_ci["n_samples"], 6)

    def test_prefix_regression_bisection(self) -> None:
        steps = [
            TrajectoryStep(step_index=0, role="user", action="ask_refund", is_valid=True),
            TrajectoryStep(step_index=1, role="assistant", action="lookup_order", is_valid=True),
            TrajectoryStep(
                step_index=2,
                role="assistant",
                action="refund_wrong_line",
                is_valid=False,
                fault_layer="model_reasoning",
                reason="Picked inactive line_id instead of verifying active subscription",
            ),
            TrajectoryStep(step_index=3, role="tool", action="timeout", is_valid=False, fault_layer="env_infra"),
        ]
        report = locate_first_mistake(
            "telecom_case_1",
            steps,
            prefix_predicate=lambda prefix: all(s.is_valid is not False for s in prefix),
        )
        self.assertTrue(report.found_mistake)
        self.assertEqual(report.first_mistake_index, 2)
        self.assertEqual(report.prefix_length, 2)
        self.assertEqual(report.fault_layer, "model_reasoning")

        fixture = build_prefix_regression_case("reg_01", "telecom_case_1", steps, report)
        self.assertEqual(fixture.forbidden_action, "refund_wrong_line")
        self.assertEqual(len(fixture.prefix_steps), 2)


if __name__ == "__main__":
    unittest.main()
