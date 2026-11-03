"""
Agent Loop & State Machine:
显式状态机、死循环检测、熔断机制与 Step 计步器。
"""
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

class AgentState(str, Enum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    AWAITING_INPUT = "AWAITING_INPUT"
    REFLECTING = "REFLECTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CIRCUIT_BROKEN = "CIRCUIT_BROKEN"

@dataclass
class LoopConfig:
    max_steps: int = 30
    consecutive_error_limit: int = 3
    identical_call_limit: int = 2

class CircuitBreaker:
    """
    熔断控制器：专门防御 Agent 重复调用相同报错工具陷入死循环（排雷地图问题 1）。
    """
    def __init__(self, config: Optional[LoopConfig] = None):
        self.config = config or LoopConfig()
        self.step_count = 0
        self.consecutive_errors = 0
        self.history_actions: List[str] = []

    def record_action(self, action_signature: str, is_error: bool = False) -> bool:
        self.step_count += 1
        if self.step_count > self.config.max_steps:
            return False  # 超出最大步数熔断

        if is_error:
            self.consecutive_errors += 1
            if self.consecutive_errors >= self.config.consecutive_error_limit:
                return False  # 连续错误熔断
        else:
            self.consecutive_errors = 0

        # 检测相同参数的重复动作
        recent = self.history_actions[-self.config.identical_call_limit:]
        if len(recent) == self.config.identical_call_limit and all(a == action_signature for a in recent):
            return False  # 动作死循环熔断

        self.history_actions.append(action_signature)
        return True
