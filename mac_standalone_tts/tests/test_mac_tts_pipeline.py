"""Unit and Integration Tests for Mac Standalone TTS Pipeline."""

import math
import pytest
import torch
import numpy as np

from mac_standalone_tts.config import MacTTSConfig, get_optimal_device
from mac_standalone_tts.audio_processor import AudioProcessor
from mac_standalone_tts.phoneme_aligner import PhonemeAligner, SP_ID, AP_ID
from mac_standalone_tts.models.ar_gpt import ARGptModel
from mac_standalone_tts.models.sovits_generator import SoVITSGenerator
from mac_standalone_tts.models.discriminator import MultiPeriodDiscriminator, MultiScaleDiscriminator
from mac_standalone_tts.pipeline import MacTTSPipeline
from mac_standalone_tts.benchmark import generate_reference_fixture, run_mac_benchmark


def test_device_detection():
    device = get_optimal_device()
    assert device.type in ("mps", "cpu")
    if torch.backends.mps.is_available():
        assert device.type == "mps"


def test_phoneme_aligner():
    aligner = PhonemeAligner()
    # Chinese + numbers + punctuation
    text = "测试123，这是逗号；这是句号。还有感叹号！"
    norm = aligner.normalize_text(text)
    assert "一二三" in norm
    assert "[SP]" in norm
    assert "[AP]" in norm

    tokens = aligner.tokenize(text)
    assert len(tokens) > 5
    assert SP_ID in tokens
    assert AP_ID in tokens

    encoded = aligner.encode(text)
    assert isinstance(encoded, torch.Tensor)
    assert encoded.dtype == torch.long


def test_audio_processor_and_features():
    device = get_optimal_device()
    proc = AudioProcessor(device=device)
    sr = 32000
    duration = 2.0
    wav = generate_reference_fixture(sr=sr, duration_s=duration)

    # Normalization
    norm_wav = proc.normalize_loudness(wav, target_db=-20.0)
    assert norm_wav.shape == wav.shape

    # Mel-spectrogram
    mel = proc.compute_mel_spectrogram(norm_wav)
    assert mel.dim() == 3
    assert mel.size(1) == 80  # 80 mels
    expected_frames = int(duration * sr / 256)
    assert abs(mel.size(2) - expected_frames) <= 2

    # Timbre embedding
    timbre = proc.extract_timbre_embedding(norm_wav, dim=128)
    assert timbre.shape == (1, 128)
    # Norm should be close to 1
    assert torch.isclose(torch.norm(timbre, dim=-1), torch.tensor([1.0], device=device), atol=1e-3)


def test_ar_gpt_forward_and_generate():
    device = get_optimal_device()
    gpt = ARGptModel().to(device)
    gpt.eval()

    text_tokens = torch.randint(0, 100, (2, 15), device=device)
    sem_tokens = torch.randint(0, 100, (2, 25), device=device)

    # Forward with loss
    logits, loss = gpt(text_tokens, sem_tokens, return_loss=True)
    assert logits.shape == (2, 24, 1024)
    assert loss is not None
    assert loss.item() > 0

    # Autoregressive generation
    gen_sem = gpt.generate(text_tokens[:1], max_new_tokens=10)
    assert gen_sem.size(0) == 1
    assert gen_sem.size(1) >= 2


def test_sovits_generator_and_discriminators():
    device = get_optimal_device()
    gen = SoVITSGenerator().to(device)
    mpd = MultiPeriodDiscriminator().to(device)
    msd = MultiScaleDiscriminator().to(device)

    sem_tokens = torch.randint(0, 100, (1, 20), device=device)
    timbre_emb = torch.randn(1, 128, device=device)

    wav = gen(sem_tokens, timbre_emb)
    # Upsample factor is 256 -> 20 * 256 = 5120 audio samples
    assert wav.shape == (1, 1, 5120)

    # Discriminator forward
    mpd_logits, _ = mpd(wav)
    msd_logits, _ = msd(wav)
    assert len(mpd_logits) == 5
    assert len(msd_logits) == 3


def test_pipeline_synthesize_and_finetune():
    device = get_optimal_device()
    config = MacTTSConfig(device=device)
    pipeline = MacTTSPipeline(config)

    ref_wav = generate_reference_fixture(sr=config.audio.sample_rate, duration_s=2.0)
    text = "单机测试苹果芯片本地推理。"

    # Synthesize
    wav, sr, metrics = pipeline.synthesize(text=text, prompt_wav=ref_wav)
    assert wav.dim() == 2
    assert sr == 32000
    assert metrics["audio_duration_s"] > 0.1
    assert metrics["rtf"] > 0
    assert metrics["latency_ms"] > 0

    # Fine-tuning step
    text_tokens = pipeline.aligner.encode("测试微调", device=device).unsqueeze(0)
    sem_tokens = pipeline.extract_semantic_tokens_from_audio(ref_wav.to(device))
    timbre_emb = pipeline.audio_proc.extract_timbre_embedding(ref_wav.to(device), dim=config.sovits.prompt_dim)

    ft_metrics = pipeline.finetune_step(text_tokens, sem_tokens, ref_wav.to(device), timbre_emb)
    assert "gpt_loss" in ft_metrics
    assert "gen_loss" in ft_metrics
    assert "disc_loss" in ft_metrics
    assert "step_time_ms" in ft_metrics
    assert ft_metrics["step_time_ms"] > 0


def test_benchmark_run():
    res = run_mac_benchmark()
    assert "rtf" in res
    assert "latency_ms" in res
    assert "finetune_step_ms" in res
    assert res["rtf"] > 0
