"""Command-line interface for Mac Standalone TTS.

Supports preprocessing dry audio, fine-tuning on Apple Silicon MPS,
synthesizing speech, running benchmarks, and starting local HTTP server.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
import torch

from .config import MacTTSConfig, get_optimal_device
from .pipeline import MacTTSPipeline
from .benchmark import run_mac_benchmark


def cmd_preprocess(args):
    """Preprocess raw dry audio: slicing, VAD, normalization, and feature extraction."""
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file {input_path} not found.", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    config = MacTTSConfig()
    pipeline = MacTTSPipeline(config)

    print(f"Loading {input_path}...")
    wav, sr = pipeline.audio_proc.load_audio(input_path)
    total_sec = wav.shape[-1] / sr
    print(f"Loaded {total_sec:.2f}s of audio at {sr}Hz.")

    print("Running energy-based VAD silence slicing...")
    chunks = pipeline.audio_proc.slice_by_silence(wav, sr)
    print(f"Generated {len(chunks)} audio slices (1.5s~12s).")

    manifest = []
    slices_dir = out_dir / "slices"
    slices_dir.mkdir(parents=True, exist_ok=True)

    for idx, (chunk_wav, s_sec, e_sec) in enumerate(chunks):
        slice_name = f"slice_{idx:04d}.wav"
        slice_path = slices_dir / slice_name
        pipeline.audio_proc.save_audio(slice_path, chunk_wav, sr)
        dur = chunk_wav.shape[-1] / sr
        manifest.append({
            "id": idx,
            "filename": slice_name,
            "path": str(slice_path),
            "start_s": round(s_sec, 2),
            "end_s": round(e_sec, 2),
            "duration_s": round(dur, 2),
        })

    import json
    with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Preprocessing complete. Manifest saved to {out_dir / 'manifest.json'}")


def cmd_infer(args):
    """Synthesize speech from input text and optional prompt audio."""
    config = MacTTSConfig()
    pipeline = MacTTSPipeline(config)

    if args.checkpoint:
        print(f"Loading checkpoint {args.checkpoint}...")
        pipeline.load_checkpoint(args.checkpoint)

    prompt_wav = None
    if args.prompt_wav:
        print(f"Loading reference prompt audio {args.prompt_wav}...")
        prompt_wav, _ = pipeline.audio_proc.load_audio(args.prompt_wav)

    print(f"Synthesizing: \"{args.text}\" on {pipeline.device}...")
    t0 = time.perf_counter()
    wav, sr, metrics = pipeline.synthesize(
        text=args.text,
        prompt_wav=prompt_wav,
        temperature=args.temperature,
        top_k=args.top_k,
        top_p=args.top_p,
    )
    t_elapsed = time.perf_counter() - t0

    out_path = Path(args.output)
    pipeline.audio_proc.save_audio(out_path, wav, sr)
    print(f"Saved audio to {out_path} ({metrics['audio_duration_s']}s).")
    print(f"Metrics: Latency={metrics['latency_ms']}ms, RTF={metrics['rtf']}, Throughput={metrics['throughput_sec_per_sec']}x")


def cmd_benchmark(args):
    """Run deterministic Apple Silicon MPS benchmark."""
    out_json = Path(args.output) if args.output else None
    res = run_mac_benchmark(output_json=out_json)
    print(f"METRIC rtf={res['rtf']}")
    print(f"METRIC latency_ms={res['latency_ms']}")
    print(f"METRIC throughput_sec_per_sec={res['throughput_sec_per_sec']}")
    print(f"METRIC finetune_step_ms={res['finetune_step_ms']}")
    print(f"METRIC mps_memory_mb={res['mps_memory_mb']}")
    print(f"METRIC audio_duration_s={res['audio_duration_s']}")


def cmd_serve(args):
    """Start standalone local HTTP server."""
    from .server import start_server
    start_server(host=args.host, port=args.port)


def main():
    parser = argparse.ArgumentParser(description="Mac Standalone TTS on Apple Silicon")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Preprocess
    p_prep = subparsers.add_parser("preprocess", help="Slice and preprocess dry audio")
    p_prep.add_argument("--input", "-i", required=True, help="Path to raw audio recording (wav/mp3)")
    p_prep.add_argument("--out-dir", "-o", default="experiments/mac-standalone-tts/work/dataset", help="Output directory")

    # Infer
    p_infer = subparsers.add_parser("infer", help="Synthesize speech from text")
    p_infer.add_argument("--text", "-t", required=True, help="Text to synthesize")
    p_infer.add_argument("--prompt-wav", "-p", default=None, help="Reference prompt audio clip")
    p_infer.add_argument("--checkpoint", "-c", default=None, help="Model checkpoint path")
    p_infer.add_argument("--output", "-o", default="experiments/mac-standalone-tts/work/output.wav", help="Output WAV path")
    p_infer.add_argument("--temperature", type=float, default=0.8)
    p_infer.add_argument("--top-k", type=int, default=50)
    p_infer.add_argument("--top-p", type=float, default=0.95)

    # Benchmark
    p_bench = subparsers.add_parser("benchmark", help="Run MPS benchmark")
    p_bench.add_argument("--output", "-o", default=None, help="Save benchmark results JSON")

    # Serve
    p_serve = subparsers.add_parser("serve", help="Start local HTTP API server")
    p_serve.add_argument("--host", default="127.0.0.1", help="Server host")
    p_serve.add_argument("--port", type=int, default=8000, help="Server port")

    args = parser.parse_args()
    if args.command == "preprocess":
        cmd_preprocess(args)
    elif args.command == "infer":
        cmd_infer(args)
    elif args.command == "benchmark":
        cmd_benchmark(args)
    elif args.command == "serve":
        cmd_serve(args)


if __name__ == "__main__":
    main()
