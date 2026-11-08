"""Mac Standalone TTS Configuration for Apple Silicon.

Optimized for Apple Silicon M-series unified memory and Metal Performance Shaders (MPS).
Provides configurations for audio processing, AR-GPT model, SoVITS generator, and MPS fine-tuning.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple
import torch


def get_optimal_device() -> torch.device:
    """Detect and return the optimal compute device.
    
    Prefers Apple Silicon MPS (Metal Performance Shaders) when available,
    with graceful fallback to CPU. Configures MPS allocator environment variables.
    """
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        # MPS environment optimizations for Apple Silicon unified memory
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        return torch.device("mps")
    return torch.device("cpu")


@dataclass
class AudioConfig:
    """Audio signal processing and acoustic feature parameters."""
    sample_rate: int = 32000
    n_fft: int = 1024
    hop_length: int = 256  # 32000 / 256 = 125 frames/second -> 8ms per frame
    win_length: int = 1024
    n_mels: int = 80
    f_min: float = 0.0
    f_max: float = 16000.0
    silence_threshold_db: float = -40.0
    min_silence_duration_ms: int = 200
    min_chunk_duration_s: float = 1.5
    max_chunk_duration_s: float = 12.0
    target_lufs: float = -20.0  # Normalized dry voice loudness


@dataclass
class ARGptConfig:
    """Autoregressive Text-to-Semantic GPT parameters."""
    text_vocab_size: int = 1024      # Phonemes, tones, and special markers
    semantic_vocab_size: int = 1024  # Discrete speech semantic tokens
    d_model: int = 256
    nhead: int = 4
    num_layers: int = 4
    dim_feedforward: int = 512
    max_seq_len: int = 1024
    dropout: float = 0.1
    temperature: float = 0.8
    top_k: int = 50
    top_p: float = 0.95


@dataclass
class SoVITSConfig:
    """Acoustic Decoder (HiFi-GAN / VITS Generator) parameters."""
    semantic_dim: int = 256
    prompt_dim: int = 128            # Timbre speaker embedding dimension
    hidden_dim: int = 192
    upsample_rates: Tuple[int, ...] = (8, 8, 2, 2)  # Product: 8*8*2*2 = 256 == hop_length
    upsample_kernel_sizes: Tuple[int, ...] = (16, 16, 4, 4)
    resblock_kernel_sizes: Tuple[int, ...] = (3, 7, 11)
    resblock_dilation_sizes: Tuple[Tuple[int, ...], ...] = (
        (1, 3, 5),
        (1, 3, 5),
        (1, 3, 5),
    )


@dataclass
class TrainConfig:
    """Apple Silicon MPS Fine-tuning parameters."""
    batch_size: int = 4
    learning_rate_gpt: float = 1e-4
    learning_rate_sovits: float = 2e-4
    learning_rate_disc: float = 2e-4
    weight_decay: float = 1e-2
    gradient_accumulation_steps: int = 2
    max_grad_norm: float = 1.0
    epochs: int = 10
    seed: int = 42
    save_interval: int = 5
    empty_cache_interval: int = 10  # Call torch.mps.empty_cache() periodically


@dataclass
class MacTTSConfig:
    """Top-level configuration bundle."""
    audio: AudioConfig = field(default_factory=AudioConfig)
    gpt: ARGptConfig = field(default_factory=ARGptConfig)
    sovits: SoVITSConfig = field(default_factory=SoVITSConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
    device: torch.device = field(default_factory=get_optimal_device)
    work_dir: Path = field(default_factory=lambda: Path("experiments/mac-standalone-tts/work"))

    def __post_init__(self):
        self.work_dir.mkdir(parents=True, exist_ok=True)
