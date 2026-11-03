"""
Execution Sandbox & Idempotency:
工具执行隔离、超时限制与写操作幂等性注入。
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional
import uuid

@dataclass
class ToolExecutionResult:
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0

def generate_idempotency_key(action_name: str, payload_hash: str) -> str:
    """为涉及资金、发信、关键状态修改的写操作工具强制注入唯一幂等键"""
    return f"{action_name}:{payload_hash}:{uuid.uuid4().hex[:8]}"
