"""Deterministic Benchmark Suite for Mac Standalone TTS on Apple Silicon.

Measures Real-Time Factor (RTF), inference latency, throughput, MPS fine-tuning step time,
and unified memory utilization. Emits METRIC lines for autoresearch harness.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path
import numpy as np
import torch

from .config import MacTTSConfig, get_optimal_device
from .pipeline import MacTTSPipeline


def generate_reference_fixture(sr: int = 32000, duration_s: float = 3.0) -> torch.Tensor:
    """Generate a deterministic synthetic voice prompt fixture with natural speech harmonics."""
    t = torch.linspace(0, duration_s, int(sr * duration_s))
    # Fundamental frequency (F0) at 160 Hz with prosodic inflection
    f0 = 160.0 + 15.0 * torch.sin(2 * math.pi * 1.5 * t)
    phase = 2 * math.pi * torch.cumsum(f0 / sr, dim=0)

    # Harmonics (1st, 2nd, 3rd, 4th formant-like overtones)
    wav = (
        0.50 * torch.sin(phase) +
        0.25 * torch.sin(2 * phase) +
        0.15 * torch.sin(3 * phase) +
        0.08 * torch.sin(4 * phase)
    )

    # Syllabic envelope modulation (~4 syllables per second)
    syllables = 0.5 + 0.5 * torch.sin(2 * math.pi * 4.0 * t).clamp(min=0.0)
    wav = wav * syllables

    # Smooth fade-in and fade-out
    fade_len = int(sr * 0.05)
    wav[:fade_len] *= torch.linspace(0.0, 1.0, fade_len)
    wav[-fade_len:] *= torch.linspace(1.0, 0.0, fade_len)
    return wav.unsqueeze(0)  # (1, T)


def run_mac_benchmark(output_json: Optional[Path] = None) -> dict:
    """Run deterministic benchmark on Mac Apple Silicon."""
    # Determinism
    torch.manual_seed(42)
    np.random.seed(42)

    device = get_optimal_device()
    config = MacTTSConfig(device=device)
    pipeline = MacTTSPipeline(config=config)

    # Generate synthetic voice reference prompt
    ref_wav = generate_reference_fixture(sr=config.audio.sample_rate, duration_s=3.0)
    ref_prompt_text = "这是麦克风录入的三秒参考干声音色。"

    test_sentence = "苹果芯片的统一内存与Metal加速，让本地语音微调和离线推理成为现实。"

    # -------------------------------------------------------------
    # 1. Warmup Pass on MPS (JIT compile Metal shaders)
    # -------------------------------------------------------------
    _ = pipeline.synthesize(
        text="预热测试。",
        prompt_wav=ref_wav,
        prompt_text=ref_prompt_text,
    )
    if device.type == "mps":
        torch.mps.synchronize()

    # -------------------------------------------------------------
    # 2. Inference Benchmark
    # -------------------------------------------------------------
    num_eval_runs = 3
    rtf_list = []
    latency_list = []
    duration_list = []
    throughput_list = []

    last_wav = None
    for _ in range(num_eval_runs):
        if device.type == "mps":
            torch.mps.synchronize()
        wav, sr, metrics = pipeline.synthesize(
            text=test_sentence,
            prompt_wav=ref_wav,
            prompt_text=ref_prompt_text,
            temperature=0.8,
            top_k=50,
            top_p=0.95,
        )
        if device.type == "mps":
            torch.mps.synchronize()

        rtf_list.append(metrics["rtf"])
        latency_list.append(metrics["latency_ms"])
        duration_list.append(metrics["audio_duration_s"])
        throughput_list.append(metrics["throughput_sec_per_sec"])
        last_wav = wav

    avg_rtf = float(np.mean(rtf_list))
    avg_latency_ms = float(np.mean(latency_list))
    avg_duration_s = float(np.mean(duration_list))
    avg_throughput = float(np.mean(throughput_list))

    # -------------------------------------------------------------
    # 3. Fine-Tuning Step Benchmark on Apple Silicon MPS
    # -------------------------------------------------------------
    pipeline.init_optimizers()
    timbre_emb = pipeline.audio_proc.extract_timbre_embedding(ref_wav.to(device), dim=config.sovits.prompt_dim)
    sem_tokens = pipeline.extract_semantic_tokens_from_audio(ref_wav.to(device))
    text_tokens = pipeline.aligner.encode(ref_prompt_text, device=device).unsqueeze(0)

    # Warmup fine-tuning step
    _ = pipeline.finetune_step(text_tokens, sem_tokens, ref_wav.to(device), timbre_emb)
    if device.type == "mps":
        torch.mps.synchronize()

    step_times = []
    for _ in range(5):
        if device.type == "mps":
            torch.mps.synchronize()
        ft_metrics = pipeline.finetune_step(text_tokens, sem_tokens, ref_wav.to(device), timbre_emb)
        if device.type == "mps":
            torch.mps.synchronize()
        step_times.append(ft_metrics["step_time_ms"])

    avg_finetune_step_ms = float(np.mean(step_times))

    # MPS memory usage
    mps_mem_mb = 0.0
    if device.type == "mps" and hasattr(torch.mps, "current_allocated_memory"):
        try:
            mps_mem_mb = float(torch.mps.current_allocated_memory() / (1024 * 1024))
        except Exception:
            mps_mem_mb = 0.0

    # Save output audio artifact
    artifacts_dir = Path("experiments/mac-standalone-tts/work/artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    if last_wav is not None:
        pipeline.audio_proc.save_audio(artifacts_dir / "bench_sample.wav", last_wav, config.audio.sample_rate)

    results = {
        "device": str(device),
        "primary_metric": "rtf",
        "rtf": round(avg_rtf, 4),
        "latency_ms": round(avg_latency_ms, 2),
        "throughput_sec_per_sec": round(avg_throughput, 2),
        "finetune_step_ms": round(avg_finetune_step_ms, 2),
        "mps_memory_mb": round(mps_mem_mb, 2),
        "audio_duration_s": round(avg_duration_s, 3),
        "sample_rate": config.audio.sample_rate,
    }

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    return results


def main():
    json_path = Path("experiments/mac-standalone-tts/work/benchmark_latest.json")
    res = run_mac_benchmark(output_json=json_path)

    # Print canonical METRIC lines
    print(f"METRIC rtf={res['rtf']}")
    print(f"METRIC latency_ms={res['latency_ms']}")
    print(f"METRIC throughput_sec_per_sec={res['throughput_sec_per_sec']}")
    print(f"METRIC finetune_step_ms={res['finetune_step_ms']}")
    print(f"METRIC mps_memory_mb={res['mps_memory_mb']}")
    print(f"METRIC audio_duration_s={res['audio_duration_s']}")


if __name__ == "__main__":
    main()
