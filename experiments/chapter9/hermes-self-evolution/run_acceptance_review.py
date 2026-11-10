#!/usr/bin/env python3
"""对候选补丁做一次全新的、只读的 Hermes 验收评审（实验 9-8 评审入口）。

评审者以独立 HERMES_HOME 运行（与被评审的运行互不共享记忆），工具集只有
terminal（只读检查）。评审前后各取一次 git status，若被评审的 checkout
被改动则直接抛错——评审者必须只读。

终止裁决按输出中的 VERDICT 行解析：ACCEPT→退出 0，REJECT→退出 3，
无法解析→退出 4。本地限制：provider 固定 openrouter（付费 API），
需要 OPENROUTER_API_KEY，缺 Key 时以退出码 2 结束。
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
MODEL = "openai/gpt-5.6-luna"
SECRET_PATTERNS = (
    re.compile(r"sk-or-v1-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--round", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not os.getenv("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY is required", file=sys.stderr)
        return 2

    source = ROOT / "worktree" / "hermes-agent"
    output = ROOT / "validation" / args.run_id / "raw" / (
        f"hermes-acceptance-review-{args.round}.txt"
    )
    reviewer_home = ROOT / ".hermes-home" / (
        f"{args.run_id}-acceptance-{args.round}"
    )
    env = os.environ.copy()
    env.update(
        {
            "HERMES_HOME": str(reviewer_home),
            "HERMES_YOLO_MODE": "1",
            "PYTHONUNBUFFERED": "1",
        }
    )
    prompt = (ROOT / "acceptance_review.md").read_text(encoding="utf-8")
    before = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=source,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout
    result = subprocess.run(
        [
            "uv", "run", "hermes", "chat",
            "--provider", "openrouter", "--model", args.model,
            "--toolsets", "terminal", "-q", prompt,
        ],
        cwd=source,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    text = result.stdout or ""
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        raise RuntimeError("credential-shaped value detected in review transcript")
    after = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=source,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout
    if after != before:
        raise RuntimeError("acceptance reviewer modified the candidate checkout")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    print(text)
    if result.returncode != 0:
        return result.returncode
    if "VERDICT: ACCEPT" in text and "VERDICT: REJECT" not in text:
        return 0
    if "VERDICT: REJECT" in text:
        return 3
    print("Reviewer did not emit a valid terminal verdict", file=sys.stderr)
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
