"""
Planning & Task Decomposition:
DAG 依赖图管理、任务拆解与动态重规划。
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class PlanStep:
    id: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
    result: Optional[Any] = None

@dataclass
class Plan:
    goal: str
    steps: List[PlanStep] = field(default_factory=list)

    def get_executable_steps(self) -> List[PlanStep]:
        completed_ids = {s.id for s in self.steps if s.status == "COMPLETED"}
        return [
            s for s in self.steps
            if s.status == "PENDING" and all(dep in completed_ids for dep in s.dependencies)
        ]
