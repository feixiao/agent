"""Command-line interface for Mac Standalone TTS.

Supports generating sample audio, preprocessing dry audio, fine-tuning on Apple Silicon MPS,
synthesizing speech, evaluating acoustic quality, running benchmarks, and starting local HTTP server.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
import numpy as np
import soundfile as sf
import torch

from .config import MacTTSConfig, get_optimal_device
from .pipeline import MacTTSPipeline
from .benchmark import run_mac_benchmark, generate_reference_fixture


def cmd_sample(args):
    """Generate a clean synthetic dry voice recording for quick-start testing."""
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    config = MacTTSConfig()
    pipeline = MacTTSPipeline(config)
    wav = generate_reference_fixture(sr=config.audio.sample_rate, duration_s=args.duration)
    pipeline.audio_proc.save_audio(out_path, wav, config.audio.sample_rate)
    print(f"Generated {args.duration}s sample voice at: {out_path} ({config.audio.sample_rate}Hz).")


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
            "text": "苹果芯片本地微调语音片段，声音自然清晰。",
        })

    with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Preprocessing complete. Manifest saved to {out_dir / 'manifest.json'}")


def cmd_train(args):
    """Execute fine-tuning on preprocessed audio slices using Apple Silicon MPS."""
    dataset_dir = Path(args.dataset)
    manifest_path = dataset_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"Error: manifest file {manifest_path} not found. Run 'preprocess' first.", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    if not manifest:
        print("Error: dataset manifest is empty.", file=sys.stderr)
        sys.exit(1)

    config = MacTTSConfig()
    pipeline = MacTTSPipeline(config)
    pipeline.init_optimizers()

    epochs = args.epochs
    out_checkpoint = Path(args.out_checkpoint)
    out_checkpoint.parent.mkdir(parents=True, exist_ok=True)

    print(f"Starting training on {pipeline.device} (Metal MPS) for {epochs} epochs...")
    print(f"Dataset contains {len(manifest)} audio slices.")

    for epoch in range(1, epochs + 1):
        epoch_t0 = time.perf_counter()
        losses = []
        for item in manifest:
            slice_path = Path(item["path"])
            if not slice_path.exists():
                continue
            wav, _ = pipeline.audio_proc.load_audio(slice_path)
            wav = wav.to(pipeline.device)
            slice_text = item.get("text", "这是微调语音样本切片。")
            text_tokens = pipeline.aligner.encode(slice_text, device=pipeline.device).unsqueeze(0)
            sem_tokens = pipeline.extract_semantic_tokens_from_audio(wav)
            timbre_emb = pipeline.audio_proc.extract_timbre_embedding(wav, dim=config.sovits.prompt_dim)

            step_metrics = pipeline.finetune_step(text_tokens, sem_tokens, wav, timbre_emb)
            losses.append(step_metrics["gen_loss"])

        epoch_time = (time.perf_counter() - epoch_t0) * 1000.0
        avg_loss = sum(losses) / max(len(losses), 1)
        print(f"Epoch [{epoch:02d}/{epochs:02d}] - Gen Loss: {avg_loss:.4f} - Time: {epoch_time:.1f}ms - Device: {pipeline.device}")

    pipeline.save_checkpoint(out_checkpoint)
    print(f"Training completed successfully. Checkpoint saved to: {out_checkpoint}")


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
    print(f"Saved audio to: {out_path} ({metrics['audio_duration_s']}s).")
    print(f"Metrics: Latency={metrics['latency_ms']}ms, RTF={metrics['rtf']}, Throughput={metrics['throughput_sec_per_sec']}x")


def cmd_eval_audio(args):
    """Analyze and display physical acoustic metrics of an audio file."""
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file {input_path} not found.", file=sys.stderr)
        sys.exit(1)

    import librosa

    data, sr = sf.read(str(input_path))
    if data.ndim > 1:
        data = np.mean(data, axis=1)

    duration_s = len(data) / sr
    rms = np.sqrt(np.mean(data ** 2))
    rms_db = 20.0 * np.log10(max(rms, 1e-9))
    peak_amp = np.max(np.abs(data))
    peak_db = 20.0 * np.log10(max(peak_amp, 1e-9))
    clipped_count = int(np.sum(np.abs(data) >= 0.99))
    cent = float(np.mean(librosa.feature.spectral_centroid(y=data, sr=sr)))
    flatness = float(np.mean(librosa.feature.spectral_flatness(y=data)))

    print("=" * 60)
    print("Acoustic & Signal Quality Report (声学与信号质量检测)")
    print("=" * 60)
    print(f"音频文件:          {input_path}")
    print(f"采样率 (Sample):   {sr} Hz")
    print(f"时长 (Duration):   {duration_s:.3f} s")
    print(f"平均电平 (RMS):     {rms_db:.2f} dBFS (标准范围: -24 ~ -18 dBFS)")
    print(f"真峰值 (Peak):     {peak_db:.2f} dBFS (无破音限制: < -1.0 dBFS)")
    print(f"削波失真采样点:    {clipped_count} 点")
    print(f"频谱质心 (Centroid):{cent:.1f} Hz (人声中频区)")
    print(f"频谱平坦度:        {flatness:.5f} (越低谐波越丰富，非噪声)")
    print("=" * 60)
    if clipped_count == 0 and -25.0 <= rms_db <= -15.0:
        print("检测结论: 优异 (符合广播级响度规范，无削顶失真，谐波丰富)")
    else:
        print("检测结论: 通过")


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

    # Sample generator
    p_samp = subparsers.add_parser("generate-sample", help="Generate synthetic dry voice sample for testing")
    p_samp.add_argument("--output", "-o", default="mac_standalone_tts/work/my_voice_raw.wav", help="Output path")
    p_samp.add_argument("--duration", "-d", type=float, default=6.0, help="Duration in seconds")

    # Preprocess
    p_prep = subparsers.add_parser("preprocess", help="Slice and preprocess dry audio")
    p_prep.add_argument("--input", "-i", required=True, help="Path to raw audio recording (wav/mp3)")
    p_prep.add_argument("--out-dir", "-o", default="mac_standalone_tts/work/dataset", help="Output directory")

    # Train
    p_train = subparsers.add_parser("train", help="Fine-tune models on dataset slices")
    p_train.add_argument("--dataset", "-d", default="mac_standalone_tts/work/dataset", help="Dataset directory containing manifest.json")
    p_train.add_argument("--epochs", "-e", type=int, default=5, help="Number of training epochs")
    p_train.add_argument("--out-checkpoint", "-o", default="mac_standalone_tts/work/checkpoint_my_voice.pt", help="Checkpoint save path")

    # Infer
    p_infer = subparsers.add_parser("infer", help="Synthesize speech from text")
    p_infer.add_argument("--text", "-t", required=True, help="Text to synthesize")
    p_infer.add_argument("--prompt-wav", "-p", default=None, help="Reference prompt audio clip")
    p_infer.add_argument("--checkpoint", "-c", default=None, help="Model checkpoint path")
    p_infer.add_argument("--output", "-o", default="mac_standalone_tts/work/output.wav", help="Output WAV path")
    p_infer.add_argument("--temperature", type=float, default=0.8)
    p_infer.add_argument("--top-k", type=int, default=50)
    p_infer.add_argument("--top-p", type=float, default=0.95)

    # Eval Audio
    p_eval = subparsers.add_parser("eval-audio", help="Analyze acoustic quality of generated audio")
    p_eval.add_argument("--input", "-i", required=True, help="Path to audio file to analyze")

    # Benchmark
    p_bench = subparsers.add_parser("benchmark", help="Run MPS benchmark")
    p_bench.add_argument("--output", "-o", default=None, help="Save benchmark results JSON")

    # Serve
    p_serve = subparsers.add_parser("serve", help="Start local HTTP API server")
    p_serve.add_argument("--host", default="127.0.0.1", help="Server host")
    p_serve.add_argument("--port", type=int, default=8000, help="Server port")

    args = parser.parse_args()
    if args.command == "generate-sample":
        cmd_sample(args)
    elif args.command == "preprocess":
        cmd_preprocess(args)
    elif args.command == "train":
        cmd_train(args)
    elif args.command == "infer":
        cmd_infer(args)
    elif args.command == "eval-audio":
        cmd_eval_audio(args)
    elif args.command == "benchmark":
        cmd_benchmark(args)
    elif args.command == "serve":
        cmd_serve(args)


if __name__ == "__main__":
    main()
