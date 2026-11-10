#!/usr/bin/env python3
"""Build a revision-pinned official AIME 2024 benchmark for Experiment 5-1.

（实验 5-1 基准构建脚本）从 HuggingFace 下载【版本锁定】的官方 AIME 2024 数据集
（parquet），校验后转换为 aime_2024.json（30 道题，仅题面 + 已公布的整数答案，
解题过程绝不下发给模型）+ 清单文件（含源文件 sha256，保证基准可复现）。

用法:
    python build_aime_2024.py --output aime_2024.json --manifest aime_2024.manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import urllib.request
from pathlib import Path

import pyarrow.parquet as parquet


# 版本锁定：数据集名 + git 式 revision，保证任何时候下载到的都是同一份数据
DATASET = "HuggingFaceH4/aime_2024"
REVISION = "2fe88a2f1091d5048c0f36abc874fb997b3dd99a"
SOURCE_PATH = "data/train-00000-of-00001.parquet"


def download() -> bytes:
    """从 HuggingFace 下载指定 revision 的原始 parquet 字节流。"""
    url = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{SOURCE_PATH}?download=true"
    request = urllib.request.Request(url, headers={"User-Agent": "ai-agent-book-exp5-1/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def convert(rows):
    """把 parquet 行转换为实验内部格式，并做数据完整性校验。

    校验点：答案必须在 000-999 内（AIME 规则）；源 id 不得重复；
    最终必须恰好 30 题（AIME I + II 各 15 题），缺一即报错。
    """
    problems = []
    seen_ids = set()
    for row in rows:
        answer = int(row["answer"])
        if not 0 <= answer <= 999:
            raise ValueError(f"AIME answer outside 000--999: {answer}")
        source_id = int(row["id"])
        if source_id in seen_ids:
            raise ValueError(f"duplicate source id: {source_id}")
        seen_ids.add(source_id)
        problems.append({
            "id": f"aime2024-{source_id}",
            "question": row["problem"],
            "answer": answer,
            "topic": "official AIME 2024",
            "source": {
                "dataset": DATASET,
                "revision": REVISION,
                "source_id": source_id,
                "year": row["year"],
                "problem_url": row["url"],
            },
        })
    if len(problems) != 30:
        raise ValueError(f"expected 30 AIME 2024 problems, got {len(problems)}")
    return sorted(problems, key=lambda item: item["id"])


def build():
    """下载 -> 转 parquet 行为题目列表 -> 附清单（sha256 等溯源信息）。"""
    raw = download()
    with tempfile.NamedTemporaryFile(suffix=".parquet") as handle:
        handle.write(raw)
        handle.flush()
        rows = parquet.read_table(handle.name).to_pylist()
    problems = convert(rows)
    manifest = {
        "schema_version": "1.0",
        "experiment": "5-1",
        "dataset": DATASET,
        "revision": REVISION,
        "source_path": SOURCE_PATH,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "split": "train",
        "problems": len(problems),
        "selection": "all published AIME I and AIME II 2024 problems",
        "answers": "published integer answer field; solutions are never sent to the model",
    }
    return problems, manifest


def main():
    """命令行入口：生成题目 JSON 与基准清单 JSON。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("aime_2024.json"))
    parser.add_argument("--manifest", type=Path, default=Path("aime_2024.manifest.json"))
    args = parser.parse_args()
    problems, manifest = build()
    args.output.write_text(json.dumps(problems, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"problems": len(problems), "revision": REVISION,
                      "output": str(args.output), "manifest": str(args.manifest)}))


if __name__ == "__main__":
    main()
