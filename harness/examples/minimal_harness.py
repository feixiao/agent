#!/usr/bin/env python3
"""
minimal_harness.py - 白盒单文件最小生产级 Agent Harness 示例

本脚本用纯 Python 原生代码（无 LangChain/三方重依赖）演示了一个工业级 Harness
必须具备的确定性工程机制：
  1. 静态前缀保护（Prefix Caching Preservation）
  2. 工具注册中心与强类型参数校验（Tool Registry & Type Validation）
  3. 执行死循环与振荡熔断器（Circuit Breaker）
  4. 上下文滑动预算管理（Context Budgeting & Compaction）
  5. 确定性事件观察与回传循环（ReAct Execution Loop）

可直接运行：python minimal_harness.py
"""

from __future__ import annotations
import inspect
import json
import hashlib
from typing import Any, Callable, Dict, List, Optional


# ============================================================================
# 1. 工具注册与安全沙箱 (Tool Registry & Validation)
# ============================================================================

class ToolRegistry:
    """管理外部工具的注册、模式提取与安全调用"""
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: List[Dict[str, Any]] = []

    def register(self, func: Callable):
        """将 Python 函数注册为 Agent 可用的结构化工具"""
        sig = inspect.signature(func)
        doc = func.__doc__ or "无描述"
        properties = {}
        required = []

        for name, param in sig.parameters.items():
            param_type = "string"
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == bool:
                param_type = "boolean"
            
            properties[name] = {
                "type": param_type,
                "description": f"参数 {name}"
            }
            if param.default == inspect.Parameter.empty:
                required.append(name)

        schema = {
            "name": func.__name__,
            "description": doc.strip().split("\n")[0],
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
        self._tools[func.__name__] = func
        self._schemas.append(schema)
        return func

    def get_schemas(self) -> List[Dict[str, Any]]:
        return self._schemas

    def execute(self, tool_name: str, args: Dict[str, Any]) -> str:
        """带安全沙箱拦截与错误捕获的工具执行器"""
        if tool_name not in self._tools:
            return f"Error: 未知工具 '{tool_name}'"
        func = self._tools[tool_name]
        try:
            result = func(**args)
            return json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
        except TypeError as e:
            return f"ParameterError: 工具参数类型不匹配: {e}"
        except Exception as e:
            return f"ExecutionError: 工具执行异常: {e}"


# ============================================================================
# 2. 防死循环与振荡熔断器 (Circuit Breaker)
# ============================================================================

class CircuitBreaker:
    """监控 Agent 行为，防止重复调用死循环、无限重试和资源爆表"""
    def __init__(self, max_turns: int = 10, max_repeated_calls: int = 2):
        self.max_turns = max_turns
        self.max_repeated_calls = max_repeated_calls
        self.call_history: List[str] = []

    def check(self, turn: int, tool_name: Optional[str], args: Optional[Dict[str, Any]]) -> Optional[str]:
        # 1. 步数上限熔断
        if turn >= self.max_turns:
            return f"CircuitBreaker: 已达到最大步数上限 ({self.max_turns} 步)，强制中止以保护系统资源。"

        if tool_name and args is not None:
            # 2. 连续相同调用与参数指纹检测
            args_str = json.dumps(args, sort_keys=True)
            fingerprint = hashlib.md5(f"{tool_name}:{args_str}".encode()).hexdigest()
            self.call_history.append(fingerprint)

            if len(self.call_history) >= self.max_repeated_calls:
                recent = self.call_history[-self.max_repeated_calls:]
                if all(fp == recent[0] for fp in recent):
                    return f"CircuitBreaker: 检测到连续重复调用同名工具及相同入参 ('{tool_name}')，触发死循环熔断！"
        return None


# ============================================================================
# 3. 上下文与记忆预算治理器 (Context Manager)
# ============================================================================

class ContextManager:
    """管理上下文窗口，保护前缀静止（Prefix Caching）并适时裁剪"""
    def __init__(self, static_system_prompt: str, max_messages: int = 12):
        self.static_system_prompt = static_system_prompt
        self.max_messages = max_messages
        self.messages: List[Dict[str, str]] = []

    def add_user(self, text: str):
        self.messages.append({"role": "user", "content": text})

    def add_assistant(self, text: str):
        self.messages.append({"role": "assistant", "content": text})

    def add_tool_result(self, tool_name: str, result: str):
        self.messages.append({"role": "observation", "name": tool_name, "content": result})

    def get_prompt_payload(self) -> List[Dict[str, str]]:
        """
        组装发给模型的完整 Prompt：
        确保 static_system_prompt 始终在数组最头部（保持 KV-Cache 前缀静止），
        对历史消息进行滑动窗口滚动裁剪。
        """
        # 滑动窗口：只保留最近的消息
        trimmed_history = self.messages[-self.max_messages:] if len(self.messages) > self.max_messages else self.messages
        return [
            {"role": "system", "content": self.static_system_prompt},
            *trimmed_history
        ]


# ============================================================================
# 4. 模拟模型推理 (Mock LLM Engine)
# ============================================================================

def mock_llm_think_step(history: List[Dict[str, str]], turn: int) -> Dict[str, Any]:
    """模拟大模型的单步输出（包含意图与工具调用）"""
    last_msg = history[-1]
    
    # 模拟任务：查询天气 -> 查日程 -> 汇报
    if turn == 0:
        return {
            "thought": "用户询问今天杭州天气并安排提醒，我需要先查天气。",
            "tool_call": {"name": "get_weather", "args": {"city": "杭州"}}
        }
    elif turn == 1:
        return {
            "thought": "天气为晴天，现在我需要调用日历工具安排一条提醒。",
            "tool_call": {"name": "add_calendar_event", "args": {"title": "出门带太阳伞", "time": "14:00"}}
        }
    else:
        return {
            "thought": "所有必要信息已经获取完毕，给用户生成最终答复。",
            "final_answer": "今天杭州天气晴朗（28℃），已为您在 14:00 创建日程提醒【出门带太阳伞】。"
        }


# ============================================================================
# 5. 主执行循环 (The Minimal Agent Harness Loop)
# ============================================================================

class MinimalAgentHarness:
    def __init__(self, system_prompt: str, registry: ToolRegistry):
        self.registry = registry
        self.context_mgr = ContextManager(static_system_prompt=system_prompt)
        self.breaker = CircuitBreaker(max_turns=6, max_repeated_calls=2)

    def run(self, user_goal: str) -> str:
        print(f"\n🚀 [Harness] 启动智能体任务: '{user_goal}'")
        self.context_mgr.add_user(user_goal)
        turn = 0

        while True:
            # 1. 熔断检查
            break_reason = self.breaker.check(turn, None, None)
            if break_reason:
                print(f"🛑 [Harness 熔断] {break_reason}")
                return f"任务终止: {break_reason}"

            # 2. 组装上下文（前缀静止 + 窗口裁剪）
            payload = self.context_mgr.get_prompt_payload()

            # 3. 驱动大模型推理
            print(f"\n--- [第 {turn + 1} 轮推理 (Turn {turn})] ---")
            response = mock_llm_think_step(payload, turn)
            thought = response.get("thought", "")
            print(f"🧠 [模型思考] {thought}")

            # 4. 判断是否完成
            if "final_answer" in response:
                print(f"✅ [达成目标] {response['final_answer']}")
                return response["final_answer"]

            # 5. 调度工具执行沙箱
            tool_call = response.get("tool_call")
            if tool_call:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                print(f"🛠️ [发起工具调用] {tool_name}({tool_args})")

                # 工具级重复熔断检查
                break_reason = self.breaker.check(turn, tool_name, tool_args)
                if break_reason:
                    print(f"🛑 [Harness 熔断] {break_reason}")
                    return f"任务终止: {break_reason}"

                # 执行工具并获得观察结果（确定性沙箱）
                obs = self.registry.execute(tool_name, tool_args)
                print(f"👀 [环境反馈 Observation] {obs}")

                # 6. 回填状态机与上下文
                self.context_mgr.add_assistant(f"Thought: {thought}\nAction: {tool_name}({json.dumps(tool_args)})")
                self.context_mgr.add_tool_result(tool_name, obs)

            turn += 1


# ============================================================================
# 6. 运行验证
# ============================================================================

if __name__ == "__main__":
    registry = ToolRegistry()

    @registry.register
    def get_weather(city: str) -> str:
        """获取指定城市的天气状况"""
        return f"{city}天气晴朗，气温 28℃，无降水。"

    @registry.register
    def add_calendar_event(title: str, time: str) -> str:
        """在系统日历中添加日程提醒"""
        return f"已成功创建日历事件：'{title}'，时间设为 {time}。"

    system_prompt = (
        "你是一个可靠的日程助手。你的职责是借助确定性工具帮助用户完成任务。"
        "严格依据观察结果行事，不得编造虚假信息。"
    )

    harness = MinimalAgentHarness(system_prompt=system_prompt, registry=registry)
    result = harness.run("帮我查下杭州天气，如果是晴天帮我建个 14:00 的带伞提醒")
    print(f"\n🎉 最终产出结果:\n{result}")
