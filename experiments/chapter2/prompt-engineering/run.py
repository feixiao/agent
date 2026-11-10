# Copyright Sierra

"""
【本文件是干什么的】
提示工程实验（书中实验 2-4）的原始入口（Tau-Bench 官方 run 脚本）：
按命令行参数构造 RunConfig，调用 tau_bench.run.run 批量执行任务
（Agent 模型 + 用户模拟模型各走 litellm，可用 --model-provider openai
配合 OPENAI_API_BASE 指向本地 OpenAI 兼容服务，如 LM Studio）。

本地最小规模示例（单任务、限制 3 个 Agent 步）：
    OPENAI_API_KEY=not-needed OPENAI_API_BASE=http://localhost:1234/v1 \\
      python run_ablation.py --model qwen3.8-27b-splash --model-provider openai \\
        --user-model qwen3.8-27b-splash --user-model-provider openai \\
        --env retail --end-index 1 --num-trials 1 --max-agent-steps 3
（消融维度 --tone-style/--randomize-wiki/--remove-tool-descriptions 在 run_ablation.py 中。）
"""

import argparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from tau_bench.types import RunConfig
from tau_bench.run import run
from litellm import provider_list
from tau_bench.envs.user import UserStrategy


def parse_args() -> RunConfig:
    """解析命令行参数 → RunConfig（任务范围、模型、温度、种子、日志目录等）。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-trials", type=int, default=1)
    parser.add_argument(
        "--env", type=str, choices=["retail", "airline"], default="retail"
    )
    parser.add_argument(
        "--model",
        type=str,
        help="The model to use for the agent",
    )
    parser.add_argument(
        "--model-provider",
        type=str,
        choices=provider_list,
        help="The model provider for the agent",
    )
    parser.add_argument(
        "--user-model",
        type=str,
        default="gpt-4o",
        help="The model to use for the user simulator",
    )
    parser.add_argument(
        "--user-model-provider",
        type=str,
        choices=provider_list,
        help="The model provider for the user simulator",
    )
    parser.add_argument(
        "--agent-strategy",
        type=str,
        default="tool-calling",
        choices=["tool-calling", "act", "react", "few-shot"],
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="The sampling temperature for the action model",
    )
    parser.add_argument(
        "--task-split",
        type=str,
        default="test",
        choices=["train", "test", "dev"],
        help="The split of tasks to run (only applies to the retail domain for now",
    )
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--end-index", type=int, default=-1, help="Run all tasks if -1")
    parser.add_argument("--task-ids", type=int, nargs="+", help="(Optional) run only the tasks with the given IDs")
    parser.add_argument("--log-dir", type=str, default="results")
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=1,
        help="Number of tasks to run in parallel",
    )
    parser.add_argument("--seed", type=int, default=10)
    parser.add_argument("--shuffle", type=int, default=0)
    parser.add_argument("--user-strategy", type=str, default="llm", choices=[item.value for item in UserStrategy])
    parser.add_argument("--few-shot-displays-path", type=str, help="Path to a jsonlines file containing few shot displays")
    args = parser.parse_args()
    print(args)
    return RunConfig(
        model_provider=args.model_provider,
        user_model_provider=args.user_model_provider,
        model=args.model,
        user_model=args.user_model,
        num_trials=args.num_trials,
        env=args.env,
        agent_strategy=args.agent_strategy,
        temperature=args.temperature,
        task_split=args.task_split,
        start_index=args.start_index,
        end_index=args.end_index,
        task_ids=args.task_ids,
        log_dir=args.log_dir,
        max_concurrency=args.max_concurrency,
        seed=args.seed,
        shuffle=args.shuffle,
        user_strategy=args.user_strategy,
        few_shot_displays_path=args.few_shot_displays_path,
    )


def main():
    """入口：解析参数后交给 tau_bench.run.run 执行并把结果写入 --log-dir。"""
    config = parse_args()
    run(config)


if __name__ == "__main__":
    main()
