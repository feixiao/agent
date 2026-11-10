"""实验 9-9 演示入口：跑「纵向持续进化」任务流，对比三臂/真实 LLM 臂。

- 默认（--profile all）：evolving / append_only / static 三个确定性参考臂，
  完全离线，无需 API Key，用于直观展示学习曲线与臂差异。
- --profile llm --model <模型>：真实 LLM 跑单臂（每个任务一次模型调用）。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent import OpenAILongitudinalAgent, ReferenceAgent
from harness import LongitudinalEvaluator


ROOT = Path(__file__).parent


def load_tasks():
    return json.loads((ROOT / "dataset.json").read_text(encoding="utf-8"))["tasks"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Experiment 9-9: longitudinal continual-evolution evaluation")
    parser.add_argument("--profile", choices=("evolving", "append_only", "static", "llm", "all"), default="all")
    parser.add_argument("--model", help="model for --profile llm; defaults to LLM_MODEL or gpt-5.6")
    parser.add_argument("--output", help="optional JSON report path")
    args = parser.parse_args()

    profiles = ("evolving", "append_only", "static") if args.profile == "all" else (args.profile,)
    reports = []
    for profile in profiles:
        agent = OpenAILongitudinalAgent(args.model) if profile == "llm" else ReferenceAgent(profile)
        reports.append(LongitudinalEvaluator().run(agent, load_tasks()))

    print("Experiment 9-9: does the Agent keep evolving?\n")
    print(f"{'profile':<14} {'learn':>7} {'transfer':>9} {'change':>8} {'retain':>8} "
          f"{'safety':>8} {'neg-xfer':>9} {'tokens':>8} {'storage':>9}")
    for report in reports:
        phases = report["phase_accuracy"]
        print(
            f"{report['profile']:<14} {phases['learning']:>7.3f} {phases['transfer']:>9.3f} "
            f"{phases['change']:>8.3f} {report['retention_rate']:>8.3f} "
            f"{report['safety_rubric_pass_rate']:>8.3f} {report['negative_transfer_rate']:>9.3f} "
            f"{report['cost']['tokens']:>8} {report['cost']['storage_bytes']:>9}"
        )
    evolving = next((item for item in reports if item["profile"] == "evolving"), None)
    if evolving:
        print("\nEvolving-agent learning curve:")
        print(" -> ".join(
            f"{point['task_id']}:{point['cumulative_accuracy']:.2f}"
            for point in evolving["learning_curve"]
        ))
        print("tasks after change signal to recover:", evolving["adaptation"]["tasks_after_change_signal_to_recover"])

    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
