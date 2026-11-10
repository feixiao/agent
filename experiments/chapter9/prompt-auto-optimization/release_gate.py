"""提示词更新的候选清单（manifest）与发布门槛（release gate）。

候选必须携带：来源案例 id（学习信号）、作用域、改动理由、
old→new 编辑列表与 diff。发布门槛由模型外代码裁决（对照正文的
四条发布条件）：补丁非空、可审计（old→new 编辑齐全）、来源案例
有记录、保留集不回归、边界集有改善——全过才 release_to_canary。
"""

from __future__ import annotations

from typing import Any, Dict


def build_candidate_manifest(
    optimization: Dict[str, Any], learning_signal: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "artifact_type": "system_prompt_patch",
        "source_case_ids": list(learning_signal.get("source_case_ids", [])),
        "scope": learning_signal.get("scope", "system_prompt"),
        "rationale": optimization.get("rationale") or learning_signal.get("diagnosis", ""),
        "diff": optimization.get("diff", ""),
        "edits": list(optimization.get("edits", [])),
        "target_rule": "transfer only on explicit human request or urgent safety event; otherwise explain policy and seek compliant alternatives",
        "status": "candidate",
    }


def evaluate_release_gate(
    before: Dict[str, Any], after: Dict[str, Any], manifest: Dict[str, Any]
) -> Dict[str, Any]:
    holdout_before, holdout_total = before["holdout"]
    holdout_after, _ = after["holdout"]
    boundary_before, boundary_total = before["boundary"]
    boundary_after, _ = after["boundary"]

    checks = {
        "patch_is_nonempty": bool(manifest.get("diff", "").strip()),
        "patch_is_auditable_old_to_new_edit": bool(manifest.get("edits")) and all(
            isinstance(edit, dict)
            and isinstance(edit.get("old_str"), str) and bool(edit["old_str"])
            and isinstance(edit.get("new_str"), str) and bool(edit["new_str"])
            for edit in manifest.get("edits", [])
        ),
        "source_cases_are_recorded": bool(manifest.get("source_case_ids")),
        "holdout_did_not_regress": holdout_after >= holdout_before,
        "boundary_improved": boundary_after > boundary_before,
    }
    accepted = all(checks.values())
    return {
        "decision": "release_to_canary" if accepted else "reject_candidate",
        "accepted": accepted,
        "checks": checks,
        "metrics": {
            "holdout_before": [holdout_before, holdout_total],
            "holdout_after": [holdout_after, holdout_total],
            "boundary_before": [boundary_before, boundary_total],
            "boundary_after": [boundary_after, boundary_total],
        },
    }
