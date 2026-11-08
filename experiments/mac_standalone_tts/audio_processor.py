"""Audio processing and acoustic feature extraction for Mac Standalone TTS.

Handles audio loading, VAD silence slicing, LUFS loudness normalization,
MPS-accelerated Mel-spectrogram computation, and speaker timbre embedding extraction.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional, Tuple, Union
import numpy as np
import soundfile as sf
import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import AudioConfig


class AudioProcessor:
    """End-to-end audio processing pipeline optimized for Apple Silicon."""

    def __init__(self, config: Optional[AudioConfig] = None, device: Optional[torch.device] = None):
        self.config = config or AudioConfig()
        self.device = device or torch.device("cpu")
        self._mel_basis = None
        self._hann_window = None

    def load_audio(self, path_or_bytes: Union[str, Path, bytes], target_sr: Optional[int] = None) -> Tuple[torch.Tensor, int]:
        """Load audio file, convert to mono, resample if necessary, return (1, samples) tensor."""
        target_sr = target_sr or self.config.sample_rate
        if isinstance(path_or_bytes, (str, Path)):
            wav_np, sr = sf.read(str(path_or_bytes), dtype="float32")
        else:
            import io
            wav_np, sr = sf.read(io.BytesIO(path_or_bytes), dtype="float32")

        # Convert stereo to mono
        if wav_np.ndim > 1:
            wav_np = np.mean(wav_np, axis=1)

        wav = torch.from_numpy(wav_np).unsqueeze(0)  # (1, T)

        # Resample if sample rate doesn't match
        if sr != target_sr:
            import torchaudio.functional as AF
            wav = AF.resample(wav, sr, target_sr)
            sr = target_sr

        return wav, sr

    def save_audio(self, path: Union[str, Path], wav: torch.Tensor, sr: Optional[int] = None) -> Path:
        """Save waveform tensor (1, T) or (T,) to WAV file."""
        sr = sr or self.config.sample_rate
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if wav.ndim == 2:
            wav = wav.squeeze(0)
        wav_np = wav.detach().cpu().numpy().astype(np.float32)
        # Prevent clipping
        max_val = np.max(np.abs(wav_np))
        if max_val > 1.0:
            wav_np = wav_np / max_val * 0.98
        sf.write(str(path), wav_np, sr, subtype="PCM_16")
        return path

    def normalize_loudness(self, wav: torch.Tensor, target_db: float = -20.0) -> torch.Tensor:
        """Peak and RMS energy normalization to target dBFS."""
        rms = torch.sqrt(torch.mean(wav ** 2) + 1e-9)
        current_db = 20.0 * torch.log10(rms)
        gain = 10.0 ** ((target_db - current_db) / 20.0)
        normalized = wav * gain
        max_amp = torch.max(torch.abs(normalized))
        if max_amp > 0.95:
            normalized = normalized / max_amp * 0.95
        return normalized

    def slice_by_silence(
        self,
        wav: torch.Tensor,
        sr: Optional[int] = None,
    ) -> List[Tuple[torch.Tensor, float, float]]:
        """Slice long recording into 1.5s~12s voice chunks using energy-based VAD.
        
        Returns list of (chunk_tensor, start_sec, end_sec).
        Applies 10ms smooth fade-in/fade-out to avoid edge pop/click artifacts.
        """
        sr = sr or self.config.sample_rate
        if wav.ndim == 2:
            wav_1d = wav.squeeze(0)
        else:
            wav_1d = wav

        samples = wav_1d.shape[0]
        total_sec = samples / sr
        frame_len = int(sr * 0.03)  # 30ms window
        hop_len = int(sr * 0.01)    # 10ms hop

        # Energy calculation per frame
        unfolded = wav_1d.unfold(0, frame_len, hop_len)
        energies = torch.sum(unfolded ** 2, dim=1) + 1e-9
        db = 10.0 * torch.log10(energies)

        # Dynamic threshold based on background noise
        noise_floor = torch.quantile(db, 0.2)
        active_threshold = max(self.config.silence_threshold_db, (noise_floor + 12.0).item())

        is_voice = (db > active_threshold).cpu().numpy()
        min_silence_frames = int(self.config.min_silence_duration_ms / 10)  # 10ms per hop
        min_chunk_samples = int(self.config.min_chunk_duration_s * sr)
        max_chunk_samples = int(self.config.max_chunk_duration_s * sr)

        # Find voice segments
        segments = []
        in_voice = False
        start_frame = 0
        silence_count = 0

        for f_idx, active in enumerate(is_voice):
            if active:
                if not in_voice:
                    start_frame = max(0, f_idx - 5)  # 50ms pre-roll
                    in_voice = True
                silence_count = 0
            else:
                if in_voice:
                    silence_count += 1
                    if silence_count >= min_silence_frames:
                        end_frame = min(len(is_voice) - 1, f_idx - min_silence_frames + 5)
                        start_sample = start_frame * hop_len
                        end_sample = min(samples, end_frame * hop_len + frame_len)
                        if (end_sample - start_sample) >= min_chunk_samples:
                            segments.append((start_sample, end_sample))
                        in_voice = False
                        silence_count = 0

        if in_voice:
            start_sample = start_frame * hop_len
            end_sample = samples
            if (end_sample - start_sample) >= min_chunk_samples:
                segments.append((start_sample, end_sample))

        # Fallback if audio has no silent pauses or threshold didn't trigger
        if not segments:
            # Chunk evenly by max_chunk_duration_s
            chunk_step = int(8.0 * sr)
            for s in range(0, samples, chunk_step):
                e = min(samples, s + chunk_step)
                if (e - s) >= min_chunk_samples:
                    segments.append((s, e))

        # Split chunks that exceed max_chunk_samples
        final_chunks: List[Tuple[torch.Tensor, float, float]] = []
        fade_len = int(sr * 0.01)  # 10ms fade
        fade_in = torch.linspace(0.0, 1.0, fade_len)
        fade_out = torch.linspace(1.0, 0.0, fade_len)

        for s_samp, e_samp in segments:
            cur_s = s_samp
            while cur_s < e_samp:
                cur_e = min(e_samp, cur_s + max_chunk_samples)
                chunk = wav_1d[cur_s:cur_e].clone()
                # Apply anti-pop edge smoothing
                if chunk.shape[0] > 2 * fade_len:
                    chunk[:fade_len] = chunk[:fade_len] * fade_in
                    chunk[-fade_len:] = chunk[-fade_len:] * fade_out
                chunk = self.normalize_loudness(chunk.unsqueeze(0), self.config.target_lufs).squeeze(0)
                final_chunks.append((chunk.unsqueeze(0), cur_s / sr, cur_e / sr))
                cur_s = cur_e

        return final_chunks

    def compute_mel_spectrogram(self, wav: torch.Tensor) -> torch.Tensor:
        """Compute Mel-spectrogram on MPS/CPU with clamped log scale.
        
        Input: (B, T) or (1, T) waveform.
        Output: (B, n_mels, T_frames) Mel-spectrogram.
        """
        wav = wav.to(self.device)
        if wav.ndim == 1:
            wav = wav.unsqueeze(0)
        elif wav.ndim == 3 and wav.size(1) == 1:
            wav = wav.squeeze(1)

        # STFT on device
        window = torch.hann_window(self.config.win_length, device=wav.device)
        stft = torch.stft(
            wav,
            n_fft=self.config.n_fft,
            hop_length=self.config.hop_length,
            win_length=self.config.win_length,
            window=window,
            center=True,
            pad_mode="reflect",
            normalized=False,
            onesided=True,
            return_complex=True,
        )
        magnitudes = torch.abs(stft)  # (B, n_fft//2 + 1, frames)

        # Mel filterbank
        if self._mel_basis is None or self._mel_basis.device != wav.device:
            import torchaudio.functional as AF
            mel_fb = AF.melscale_fbanks(
                n_freqs=self.config.n_fft // 2 + 1,
                f_min=self.config.f_min,
                f_max=self.config.f_max,
                n_mels=self.config.n_mels,
                sample_rate=self.config.sample_rate,
                norm="slaney",
                mel_scale="slaney",
            ).to(wav.device)
            self._mel_basis = mel_fb.transpose(0, 1)  # (n_mels, n_freqs)

        mel = torch.matmul(self._mel_basis, magnitudes)
        log_mel = torch.log(torch.clamp(mel, min=1e-5))
        return log_mel

    def extract_timbre_embedding(self, wav: torch.Tensor, dim: int = 128) -> torch.Tensor:
        """Extract a fixed-dimension acoustic timbre speaker embedding from prompt audio.
        
        Computes multi-resolution acoustic statistics (Mel mean, Mel std, spectral centroid, dynamics)
        and projects to target embedding dimension. Deterministic and fast on Apple Silicon.
        """
        mel = self.compute_mel_spectrogram(wav)  # (B, n_mels, T)
        # Acoustic statistical moments
        mean_feat = torch.mean(mel, dim=-1)      # (B, 80)
        std_feat = torch.std(mel, dim=-1)        # (B, 80)
        max_feat = torch.max(mel, dim=-1)[0]     # (B, 80)
        combined = torch.cat([mean_feat, std_feat, max_feat], dim=-1)  # (B, 240)

        # Deterministic projection to target dim
        generator = torch.Generator(device="cpu").manual_seed(1337)
        proj_matrix = torch.randn(combined.shape[-1], dim, generator=generator).to(combined.device)
        # Normalize projection matrix
        proj_matrix = proj_matrix / math.sqrt(combined.shape[-1])
        embedding = torch.matmul(combined, proj_matrix)
        embedding = F.normalize(embedding, p=2, dim=-1)
        return embedding
