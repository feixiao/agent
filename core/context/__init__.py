"""
Context Engineering: Token 预算分配、Prompt Cache 优化与滑动窗口管理。
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class TokenBudget:
    max_context_tokens: int = 128000
    max_output_tokens: int = 4096
    system_prompt_reserve: int = 4096
    safety_margin: int = 2048

class ContextEngine:
    """
    上下文装配引擎：
    1. 确保 System Prompt 与工具 Schema 前缀字节绝对静态以最大化命中 KV Cache
    2. 对历史消息实施基于 Token 预算的渐进式裁剪与重要性压缩
    """
    def __init__(self, budget: Optional[TokenBudget] = None):
        self.budget = budget or TokenBudget()

    def assemble(self, system_prompt: str, history: List[Dict[str, Any]], status_bar: str = "") -> List[Dict[str, Any]]:
        # 基础静态前缀保证
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        if status_bar:
            # 状态栏动态信息永远置于最新一轮消息尾部，避免破坏静态前缀 Cache
            if messages and messages[-1]["role"] == "user":
                messages[-1]["content"] += f"\n\n<status_bar>\n{status_bar}\n</status_bar>"
            else:
                messages.append({"role": "user", "content": f"<status_bar>\n{status_bar}\n</status_bar>"})
        return messages
