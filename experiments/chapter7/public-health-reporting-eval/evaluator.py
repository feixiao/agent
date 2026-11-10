"""Objective structured scoring for public-health reporting agent traces.

【中文】客观评分器：把 Agent 轨迹与期望答案逐项核对（数值容差内的计算准确性、
证据引用是否真实、是否出现无依据声明等），每任务满分 6 分。纯确定性、无 LLM。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


MAX_SCORE = 6


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def expected_by_task(path: str | Path) -> dict[str, dict[str, Any]]:
    return {item["task_id"]: item for item in load_json(path)}


def _equivalent(actual: Any, expected: Any, tolerance: float) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return actual == expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isclose(float(actual), float(expected), abs_tol=tolerance)
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _equivalent(actual[key], expected[key], tolerance) for key in expected
        )
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _equivalent(left, right, tolerance) for left, right in zip(actual, expected)
        )
    return actual == expected


def _same_evidence(actual: list[Any], expected: list[Any]) -> bool:
    """Compare evidence as set-like collections, including JSON objects."""
    try:
        return set(actual) == set(expected)
    except TypeError:
        return all(item in expected for item in actual) and all(
            item in actual for item in expected
        )


def score_prediction(
    prediction: dict[str, Any], expected: dict[str, Any], tolerance: float = 0.01
) -> dict[str, Any]:
    """Score tool, arguments, answer, evidence and grounding (six points total)."""
    details = {
        "tool_selection": int(prediction.get("tool") == expected["tool"]),
        "arguments": int(prediction.get("arguments") == expected["arguments"]),
    }

    actual_result = prediction.get("result", {})
    if not isinstance(actual_result, dict):
        actual_result = {}
    expected_result = expected["result"]
    actual_values = {key: value for key, value in actual_result.items() if key != "evidence"}
    expected_values = {key: value for key, value in expected_result.items() if key != "evidence"}
    details["answer"] = 2 if _equivalent(actual_values, expected_values, tolerance) else 0
    actual_evidence = actual_result.get("evidence", [])
    if not isinstance(actual_evidence, list):
        actual_evidence = []
    expected_evidence = expected_result.get("evidence", []) if isinstance(expected_result, dict) else []
    if not isinstance(expected_evidence, list):
        expected_evidence = []
    details["evidence"] = int(_same_evidence(actual_evidence, expected_evidence))

    claims = prediction.get("claims", [])
    supported = expected.get("supported_claims", []) if isinstance(expected, dict) else []
    if not isinstance(supported, list):
        supported = []
    if not isinstance(claims, list):
        grounding = 0
    else:
        try:
            grounding = int(set(claims).issubset(set(supported)))
        except TypeError:
            grounding = int(all(item in supported for item in claims))
    details["grounding_and_safety"] = grounding
    return {
        "task_id": expected["task_id"],
        "score": sum(details.values()),
        "max_score": MAX_SCORE,
        "details": details,
    }


def evaluate(
    predictions: list[dict[str, Any]],
    expected_items: dict[str, dict[str, Any]],
    tolerance: float = 0.01,
) -> dict[str, Any]:
    prediction_map = {item["task_id"]: item for item in predictions}
    results = []
    for task_id, expected in expected_items.items():
        prediction = prediction_map.get(task_id, {"task_id": task_id})
        results.append(score_prediction(prediction, expected, tolerance))
    return {
        "score": sum(item["score"] for item in results),
        "max_score": len(results) * MAX_SCORE,
        "tasks": results,
    }
