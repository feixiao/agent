"""从用户纠正的 before/after 对中开放式提炼候选写作规则。

本模块不包含预置模式库。模型直接比较用户给出的 before/after 与纠正原话，
发现已有清单之外的新规律。所有候选都统一使用 LLM judge；模型只能提出候选，
是否合并、校准和激活仍由模型外部代码决定。
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple

from llm_client import chat

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"


def load_pairs(path: Path | None = None) -> List[Dict[str, Any]]:
    """加载用户纠正的 before/after 反馈对（默认 data/feedback_pairs.json，共 26 条）。"""
    return json.loads((path or DATA_DIR / "feedback_pairs.json").read_text(encoding="utf-8"))


_LLM_EXTRACT_PROMPT = """你是写作规范的提炼助手。请比较本批用户纠正的 before/after 对，
从反馈本身归纳具体、可复核的写作规则。不要依赖任何预置的模式清单，也不要把规则限制在
正则表达式能检测的现象；语义、句法、语气和篇章层面的新规律都可以提出。

返回 JSON：{{"rules": [{{"id": "rule-<英文短横线命名>", "name": "...",
"definition": "清楚说明什么情况下命中，以及什么相似情况不应命中",
"bad_example": "取自 before 的原文片段", "good_example": "对应的 after 原文片段",
"rewrite_hint": "具体改写建议", "scope": ["适用场景"],
"source_ids": ["支撑该规则的反馈对 id"]}}]}}

要求：
1. 每条规则必须至少有一条 source_ids，且 id、坏例、好例都只能来自输入；不要编造证据。
2. 同一现象只返回一条规则。规则要区分“滥用”和合理使用，不能写成一刀切禁令。
3. 如果本批现象与“当前规则”语义相同，必须复用当前规则的 id；只有发现新规律才创建新 id。
4. 返回的候选将全部交给外部 LLM judge，用独立人工金标集校准后才可能激活。

当前规则（可能为空）：
{existing_rules}

本批反馈：
{pairs}
"""


def _strip_json_fence(content: str) -> str:
    """去掉模型输出首尾的 ```json 代码围栏，便于 json.loads 解析。"""
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)


def _validate_candidate(
    rule: Dict[str, Any], pair_by_id: Dict[str, Dict[str, Any]]
) -> Dict[str, Any] | None:
    """机械校验一条模型候选：字段齐全、id 合法、证据必须真实来自输入。

    关键防自洽闭环措施：bad_example 必须能在某条 source 反馈的 before 中找到、
    good_example 必须在对应 after 中找到，否则整条候选作废（返回 None）。
    """
    # 必填字段缺一即拒绝
    required = (
        "id", "name", "definition", "bad_example", "good_example",
        "rewrite_hint", "source_ids",
    )
    if not all(rule.get(key) for key in required):
        return None
    # id 必须是唯一、可引用的短横线命名（如 rule-no-empty-claim）
    if not re.fullmatch(r"rule-[a-z0-9]+(?:-[a-z0-9]+)*", str(rule["id"])):
        return None

    # source_ids 去重且必须都指向真实存在的反馈对
    source_ids = list(dict.fromkeys(rule["source_ids"]))
    if not source_ids or any(source_id not in pair_by_id for source_id in source_ids):
        return None

    # 正反例必须真的出现在被引用的反馈对里，防止模型编造证据
    bad_example = str(rule["bad_example"])
    good_example = str(rule["good_example"])
    supported = any(
        bad_example in pair_by_id[source_id]["before"]
        and good_example in pair_by_id[source_id]["after"]
        for source_id in source_ids
    )
    if not supported:
        return None

    # 通过校验的候选统一固定 detector 为 llm：
    # 是否命中由独立 LLM judge 语义判定，而不是任何预置正则/词表。
    return {
        "id": rule["id"],
        "name": str(rule["name"]),
        "definition": str(rule["definition"]),
        "detector": {"type": "llm"},
        "bad_example": bad_example,
        "good_example": good_example,
        "rewrite_hint": str(rule["rewrite_hint"]),
        "scope": sorted({str(item) for item in rule.get("scope", [])}),
        "source_ids": source_ids,
        "status": "candidate",
    }


def extract_with_llm(
    pairs: List[Dict[str, Any]],
    *,
    provider: str,
    model: str | None = None,
    seed: int = 8901,
    existing_rules: List[Dict[str, Any]] | None = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """开放式提炼候选规则，返回 ``(候选列表, API 证据回执)``。"""
    brief = [
        {
            "id": pair["id"],
            "scene": pair["scene"],
            "before": pair["before"],
            "after": pair["after"],
            "correction": pair["correction"],
        }
        for pair in pairs
    ]
    current = [
        {"id": rule["id"], "name": rule["name"], "definition": rule["definition"]}
        for rule in (existing_rules or [])
    ]
    content, receipt = chat(
        [{
            "role": "user",
            "content": _LLM_EXTRACT_PROMPT.format(
                pairs=json.dumps(brief, ensure_ascii=False, indent=2),
                existing_rules=json.dumps(current, ensure_ascii=False, indent=2),
            ),
        }],
        provider=provider,
        model=model,
        seed=seed,
        max_tokens=16000,
    )
    payload = json.loads(_strip_json_fence(content))
    pair_by_id = {pair["id"]: pair for pair in pairs}
    candidates = []
    for rule in payload.get("rules", []):
        candidate = _validate_candidate(rule, pair_by_id)
        if candidate is not None:
            candidates.append(candidate)
    return candidates, receipt


def write_candidates(candidates: List[Dict[str, Any]], path: Path | None = None) -> Path:
    """把通过机械校验的候选规则落盘（data/candidate_rules.json），供事后审查。"""
    out = path or DATA_DIR / "candidate_rules.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
