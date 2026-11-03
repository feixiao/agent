"""
Memory Subsystem: 短期工作记忆与长期记忆持久化。
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseMemory(ABC):
    @abstractmethod
    def add(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        pass

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass

class WorkingMemory(BaseMemory):
    """短期会话记忆与 Scratchpad 临时状态池"""
    def __init__(self):
        self._store: Dict[str, Any] = {}

    def add(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._store[key] = {"value": value, "metadata": metadata or {}}

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        return [{"key": k, "data": v} for k, v in list(self._store.items())[:top_k]]

    def clear(self) -> None:
        self._store.clear()
