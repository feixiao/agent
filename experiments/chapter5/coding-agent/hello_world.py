#!/usr/bin/env python3
"""
hello_world.py —— coding-agent 实验的「最小任务样例」。

这是喂给 CodingAgent 的典型需求原文所指向的文件：
  1) 打印 "Hello, World!"；
  2) 定义 greet(name) 函数并演示调用。
跑 `python agent.py` 时，Agent 会创建/修改本文件并用 Bash 工具运行验证，
是观察「模型写代码 -> 执行 -> 读取输出」完整闭环的最小复现物。
"""

from typing import Any

def greet(name: str) -> str:
    """Return a friendly greeting for the given name.（需求 2：定义问候函数）"""
    return f"Hello, {name}!"


def main() -> None:
    # Requirement 1: Print "Hello, World!"
    print("Hello, World!")

    # Requirement 3: Demonstrate the function
    print(greet("Alice"))


if __name__ == "__main__":
    main()
