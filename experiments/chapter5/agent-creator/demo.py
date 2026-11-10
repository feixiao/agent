"""实验 5-13 命令行入口：比较「从零生成 Agent」与「改造成熟参考 Agent」两条路线。

两种策略（见 creator.py）：
  - scratch  : 让模型从零写出整个 Agent（agent.py/工具/测试/README 全套文件）；
  - template : 模型只产出一份紧凑的「领域特化」domain_spec.json，
               Agent 主循环/工具协议/CLI/测试沿用经过验证的 reference_agent 代码。

本脚本加载冻结的实验协议（experiment_protocol.json），跑两臂并输出对照结果 JSON；
--no-live 跳过真实 API 执行，--resume 复用已生成的臂并补跑/重验。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from creator import DEFAULT_PROTOCOL, load_protocol, run_experiment


DEFAULT_REQUIREMENTS = load_protocol()[0]["requirements"]


def main() -> None:
    """命令行入口：加载冻结协议 → 跑对照实验（scratch vs template）→ 打印结果 JSON。

    官方实验未完整完成（official_complete=false）时以非零码退出，便于脚本化判断。
    """
    parser = argparse.ArgumentParser(
        description="Experiment 5-13: compare an Agent created from scratch with one adapted from a proven Agent"
    )
    parser.add_argument("--requirements", default=DEFAULT_REQUIREMENTS)
    parser.add_argument("--output", type=Path, default=Path("runs/latest"))
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--live-task",
        default=None,
        help="Development-only single task override; it cannot complete the frozen book experiment",
    )
    parser.add_argument("--no-live", action="store_true", help="Skip real API execution of generated Agents")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse already generated arms in --output and repair/revalidate them",
    )
    args = parser.parse_args()
    result = run_experiment(
        args.requirements,
        args.output,
        live=not args.no_live,
        live_task=args.live_task,
        resume=args.resume,
        protocol_path=args.protocol,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["official_complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
