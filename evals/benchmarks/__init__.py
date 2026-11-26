"""Benchmark suites and deterministic smoke tests."""

from .golden_set import (
    DEFAULT_GOLDEN_CASES,
    SCORING_VERSION,
    CaseResult,
    GoldenCase,
    GoldenRunner,
    GoldenSuiteReport,
    PairDiagnostic,
    diagnose_template_pairs,
    openai_chat_completion,
)

__all__ = [
    "DEFAULT_GOLDEN_CASES",
    "SCORING_VERSION",
    "CaseResult",
    "GoldenCase",
    "GoldenRunner",
    "GoldenSuiteReport",
    "PairDiagnostic",
    "diagnose_template_pairs",
    "openai_chat_completion",
]
