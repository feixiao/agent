"""实验 9-6 完整流程演示：诊断 → 候选 → 验证 → 发布决定。

默认 --generator deterministic（纯离线，候选由确定性生成器产出）；
--generator llm 则调用真实 API 的 Coding Agent 生成候选。
验证（--generator llm 路径需 Docker 沙箱；确定性路径同样走沙箱检查，
无 Docker 时相关检查按不通过处理）。候选与发布清单只写 output/，
绝不改动 stable/ 下的稳定代码。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evolution import diagnose, generate_candidate, release_manifest, validate_candidate, write_candidate


ROOT = Path(__file__).parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Experiment 9-6 self-modification pipeline")
    parser.add_argument("--generator", choices=("deterministic", "llm"), default="deterministic")
    parser.add_argument("--model", help="real LLM model; defaults to LLM_MODEL or gpt-5.6")
    args = parser.parse_args()
    trajectories = json.loads((ROOT / "failure_trajectories.json").read_text(encoding="utf-8"))
    stable_path = ROOT / "stable" / "retry_policy.py"
    stable_source = stable_path.read_text(encoding="utf-8")

    diagnosis = diagnose(trajectories)
    if args.generator == "llm":
        from llm_generator import generate_with_openai
        candidate = generate_with_openai(stable_source, diagnosis, args.model)
    else:
        candidate = generate_candidate(stable_source, diagnosis)
    checks = validate_candidate(candidate["source"], trajectories, stable_source)
    manifest = release_manifest(stable_source, candidate, diagnosis, checks)

    write_candidate(candidate["source"], ROOT / "output" / "candidate" / "retry_policy.py")
    (ROOT / "output" / "release_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Experiment 9-6: trajectory-triggered self-modification (generator={args.generator})\n")
    print("diagnosed target:", diagnosis["target"])
    print("source cases:", ", ".join(diagnosis["source_case_ids"]))
    print("\nCandidate diff:\n")
    print(candidate["diff"])
    print("checks:", checks)
    print("decision:", manifest["decision"])
    print("stable file unchanged:", stable_path.read_text(encoding="utf-8") == stable_source)
    print("rollback version:", manifest["rollback_version"])


if __name__ == "__main__":
    main()
