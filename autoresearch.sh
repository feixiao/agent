#!/usr/bin/env bash
set -euo pipefail

# Autoresearch Benchmark Entrypoint for Mac Standalone TTS
# Apple Silicon Metal (MPS) Closed-Loop TTS & Fine-Tuning Benchmark

export PYTHONPATH="."
export PYTHONUNBUFFERED=1
export PYTORCH_ENABLE_MPS_FALLBACK=1

# Execute deterministic benchmark on Mac Apple Silicon
uv run python -m experiments.mac_standalone_tts.benchmark
