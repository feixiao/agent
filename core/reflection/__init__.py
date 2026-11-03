"""
Reflection & Self-Correction:
反思、评审与环境状态比对。
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class ValidationResult:
    passed: bool
    feedback: str
    suggested_revision: Optional[str] = None
