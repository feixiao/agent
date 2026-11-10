"""实验 9-1 演示入口：无需 API Key 即可跑三层轨迹验证器。

读取 sample_trajectories.json（4 条样例轨迹），逐条出七维报告，
并打印标量基线 vs 多维诊断效用、以及与专家标注的校准报告。
--judge heuristic（默认，离线）/ --judge llm（需真实 LLM，注意其
EvidenceChatClient 端点固定为各付费 provider，不能指向本地服务）。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from calibration import calibration_report
from verifier import TrajectoryVerifier, diagnostic_utility, scalar_baseline


ROOT = Path(__file__).parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Experiment 9-1 trajectory verifier")
    parser.add_argument("--judge", choices=("heuristic", "llm"), default="heuristic")
    parser.add_argument("--model", help="real LLM model; defaults to LLM_MODEL or gpt-5.6")
    args = parser.parse_args()
    trajectories = json.loads((ROOT / "sample_trajectories.json").read_text(encoding="utf-8"))
    if args.judge == "llm":
        from llm_judge import OpenAIQualityJudge
        verifier = TrajectoryVerifier(quality_judge=OpenAIQualityJudge(args.model))
    else:
        verifier = TrajectoryVerifier()
    reports = [verifier.evaluate(item) for item in trajectories]

    print(f"Experiment 9-1: three-layer customer-service trajectory verifier (judge={args.judge})\n")
    for report in reports:
        failed = [
            item["dimension"] for item in report["dimensions"] if item["verdict"] == "fail"
        ]
        print(f"{report['trajectory_id']:<24} score={report['overall_score']:.3f} "
              f"decision={report['release_recommendation']:<16} failures={failed or ['none']}")

    scalar = scalar_baseline(reports[1])
    print("\nScalar baseline:", scalar)
    print("Multidimensional diagnostic utility:", diagnostic_utility(reports[1]))
    print("\nCalibration:")
    print(json.dumps(calibration_report(trajectories, reports), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
