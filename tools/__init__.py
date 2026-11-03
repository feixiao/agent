"""
Tools Registry & Protocol:
标准工具装饰器与渐进式暴露机制 (L0: 紧凑摘要, L1: 详细参数, L2: 示例与反例)。
"""
from typing import Callable, Dict, Any, Optional
import inspect

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, Dict[str, Any]] = {}

    def register(self, name: Optional[str] = None, description: Optional[str] = None):
        def decorator(func: Callable):
            tool_name = name or func.__name__
            tool_desc = description or (func.__doc__ or "").strip()
            self._tools[tool_name] = func
            self._schemas[tool_name] = {
                "name": tool_name,
                "description": tool_desc,
                "signature": str(inspect.signature(func))
            }
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[Callable]:
        return self._tools.get(name)

    def list_schemas(self) -> Dict[str, Dict[str, Any]]:
        return self._schemas
