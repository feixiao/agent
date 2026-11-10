#!/usr/bin/env python3
"""对留存的实验 6-5 本地运行做「失败即关闭」的确定性校验。

校验：实验编号、精确模型 id + 钉住 revision、确实用了 CUDA、原生音频塔开启、
未声称 thinking、4 个用例双臂齐全、语音波形落盘且哈希/采样率匹配、
实现文件哈希与证据一致、零外部 API 调用。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from speech_model import MODEL_ID, MODEL_REVISION, sha256_file


HERE = Path(__file__).resolve().parent


def validate(evidence_path: Path) -> dict:
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    implementation_hashes = evidence.get("implementation_sha256", {})
    checks = {
        "experiment_is_6_5": evidence.get("experiment") == "6-5",
        "exact_model": evidence.get("model", {}).get("model_id") == MODEL_ID,
        "pinned_revision": evidence.get("model", {}).get("model_revision") == MODEL_REVISION,
        "cuda_used": evidence.get("model", {}).get("cuda_available") is True,
        "native_audio_enabled": evidence.get("model", {}).get("init_audio") is True,
        "thinking_not_claimed": evidence.get("protocol", {}).get("enable_thinking") is False,
        "four_cases": len(evidence.get("cases", [])) == 4,
        "both_arms_complete": all(
            (case.get("direct") or {}).get("response")
            and (case.get("self_cascade") or {}).get("response")
            and (case.get("self_cascade") or {}).get("transcript")
            for case in evidence.get("cases", [])
        ),
        "speech_waveform_recorded": False,
        "implementation_hashes_match": bool(implementation_hashes) and all(
            (HERE / name).is_file() and sha256_file(HERE / name) == digest
            for name, digest in implementation_hashes.items()
        ),
        "no_external_api": evidence.get("external_api_calls") == 0,
    }
    audio = (evidence.get("speech_output") or {}).get("output_audio") or {}
    if audio.get("path") and audio.get("sha256"):
        path = Path(audio["path"])
        if not path.is_absolute():
            path = (HERE / path).resolve()
        checks["speech_waveform_recorded"] = (
            path.is_file()
            and sha256_file(path) == audio["sha256"]
            and audio.get("sample_rate_hz") == 24000
            and audio.get("duration_seconds", 0) > 0
        )
    return {"passed": all(checks.values()), "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(args.evidence)
    output = args.output or args.evidence.with_name("acceptance.json")
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
