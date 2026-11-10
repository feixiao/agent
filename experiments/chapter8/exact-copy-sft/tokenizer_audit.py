"""跨 tokenizer 家族的字节精确复述审计（实验 8-19 配套）。

对 data/eval.jsonl + data/boundary.jsonl 的探针字符串，在
Qwen3-8B / Qwen2.5-0.5B-Instruct / Mistral-7B 三个 tokenizer 上做
encode→decode 往返，统计 roundtrip 一致率与平均 token 数。
目的：把"复制失败"中属于 tokenizer/序列化层的部分与模型能力区分开
（例如 Qwen 系对部分 Unicode 字符往返不一致，不应记到模型头上）。
结果写入 validation/tokenizer_audit.json。
"""
from __future__ import annotations

import json
from pathlib import Path

from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parent
MODELS = [
    "Qwen/Qwen3-8B",
    "Qwen/Qwen2.5-0.5B-Instruct",
    "mistralai/Mistral-7B-v0.1",
]


def rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    # 中文注释：合并 eval + boundary 两份探针（训练后与边界集）逐个做往返测试
    probes = rows(ROOT / "data" / "eval.jsonl") + rows(ROOT / "data" / "boundary.jsonl")
    report = {"probe_count": len(probes), "tokenizers": {}}
    for model_id in MODELS:
        tok = AutoTokenizer.from_pretrained(model_id, use_fast=True)
        records = []
        for row in probes:
            ids = tok.encode(row["source"], add_special_tokens=False)
            decoded = tok.decode(ids, skip_special_tokens=False)
            records.append({"id": row["id"], "roundtrip": int(decoded == row["source"]), "tokens": len(ids)})
        report["tokenizers"][model_id] = {
            "vocab_size": len(tok),
            "roundtrip_rate": sum(r["roundtrip"] for r in records) / len(records),
            "mean_tokens": sum(r["tokens"] for r in records) / len(records),
            "failures": [r["id"] for r in records if not r["roundtrip"]][:20],
        }
    out = ROOT / "validation" / "tokenizer_audit.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
