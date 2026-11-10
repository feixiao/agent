"""A deterministic reference agent for the reporting evaluation environment.

【中文】确定性参考 Agent：不做自由推理，只按任务里显式写好的 (工具, 参数)
计划调用合成 DHIS2 环境并回传结构化轨迹（工具+参数+结果+有依据声明），
用于给评估器提供可复现的对照基线。
"""

from __future__ import annotations

from typing import Any

from reporting_tools import ReportingEnvironment


class DeterministicReportingAgent:
    """Executes the task's explicit tool plan and returns a structured trace."""

    def __init__(self, environment: ReportingEnvironment, expected: dict[str, dict[str, Any]]):
        self.environment = environment
        self.expected = expected

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        result = self.environment.call(task["tool"], task["arguments"])
        expected = self.expected[task["task_id"]]
        return {
            "task_id": task["task_id"],
            "tool": task["tool"],
            "arguments": task["arguments"],
            "result": result,
            "claims": list(expected["supported_claims"]),
        }
