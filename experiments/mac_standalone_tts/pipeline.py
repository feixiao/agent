"""Mac Standalone TTS Pipeline.

Orchestrates audio preprocessing, AR-GPT semantic prediction, SoVITS waveform synthesis,
and local fine-tuning on Apple Silicon Metal (MPS).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import torch
import torch.nn.functional as F
import torch.optim as optim

from .config import MacTTSConfig, get_optimal_device
from .audio_processor import AudioProcessor
from .phoneme_aligner import PhonemeAligner
from .models.ar_gpt import ARGptModel
from .models.sovits_generator import SoVITSGenerator
from .models.discriminator import (
    MultiPeriodDiscriminator,
    MultiScaleDiscriminator,
    discriminator_loss,
    generator_adversarial_loss,
    feature_loss,
)


class MacTTSPipeline:
    """End-to-end standalone voice cloning and TTS pipeline on Mac Apple Silicon."""

    def __init__(self, config: Optional[MacTTSConfig] = None):
        self.config = config or MacTTSConfig()
        self.device = self.config.device
        self.audio_proc = AudioProcessor(self.config.audio, device=self.device)
        self.aligner = PhonemeAligner(vocab_size=self.config.gpt.text_vocab_size)

        # Initialize models
        self.gpt = ARGptModel(self.config.gpt).to(self.device)
        self.sovits = SoVITSGenerator(self.config.sovits).to(self.device)

        # Discriminators for fine-tuning
        self.mpd = MultiPeriodDiscriminator().to(self.device)
        self.msd = MultiScaleDiscriminator().to(self.device)

        # Optimizers (lazy init on fine-tuning)
        self.opt_gpt = None
        self.opt_sovits = None
        self.opt_disc = None
        self._step_count = 0

    def init_optimizers(self):
        """Initialize AdamW optimizers for Apple Silicon fine-tuning."""
        cfg = self.config.train
        self.opt_gpt = optim.AdamW(
            self.gpt.parameters(),
            lr=cfg.learning_rate_gpt,
            weight_decay=cfg.weight_decay,
            betas=(0.9, 0.999),
        )
        self.opt_sovits = optim.AdamW(
            self.sovits.parameters(),
            lr=cfg.learning_rate_sovits,
            weight_decay=cfg.weight_decay,
            betas=(0.8, 0.99),
        )
        disc_params = list(self.mpd.parameters()) + list(self.msd.parameters())
        self.opt_disc = optim.AdamW(
            disc_params,
            lr=cfg.learning_rate_disc,
            weight_decay=cfg.weight_decay,
            betas=(0.8, 0.99),
        )

    def extract_semantic_tokens_from_audio(self, wav: torch.Tensor) -> torch.Tensor:
        """Extract discrete speech semantic tokens from reference audio.
        
        Maps acoustic spectral frames into discrete token indices [0, semantic_vocab_size - 1].
        Deterministic feature clustering representation.
        """
        mel = self.audio_proc.compute_mel_spectrogram(wav)  # (1, 80, T_frames)
        # Quantize frame spectral energies into discrete token IDs
        # Combine energy and spectral slope
        energies = torch.norm(mel, dim=1).squeeze(0)  # (T_frames,)
        spec_diff = torch.mean(torch.diff(mel, dim=-1), dim=1).squeeze(0)  # (T_frames - 1,)
        spec_diff = F.pad(spec_diff, (0, 1))

        # Discretize into semantic vocabulary (reserve IDs 0..5 for special tokens)
        vocab_range = self.config.gpt.semantic_vocab_size - 10
        q_tokens = ((torch.abs(energies * 17.0 + spec_diff * 31.0).long()) % vocab_range) + 6
        return q_tokens.unsqueeze(0)  # (1, T_frames)

    def finetune_step(
        self,
        text_tokens: torch.Tensor,
        semantic_tokens: torch.Tensor,
        real_wav: torch.Tensor,
        timbre_emb: torch.Tensor,
    ) -> Dict[str, float]:
        """Execute one complete fine-tuning step on Apple Silicon Metal (MPS).
        
        Updates AR GPT, Discriminators, and SoVITS Generator with loss tracking.
        """
        if self.opt_gpt is None:
            self.init_optimizers()

        self.gpt.train()
        self.sovits.train()
        self.mpd.train()
        self.msd.train()

        text_tokens = text_tokens.to(self.device)
        semantic_tokens = semantic_tokens.to(self.device)
        real_wav = real_wav.to(self.device)
        timbre_emb = timbre_emb.to(self.device)

        step_t0 = time.perf_counter()

        # ---------------------------------------------------------
        # 1. AR GPT Text-to-Semantic Training
        # ---------------------------------------------------------
        self.opt_gpt.zero_grad(set_to_none=True)
        _, gpt_loss = self.gpt(text_tokens, semantic_tokens, return_loss=True)
        gpt_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.gpt.parameters(), self.config.train.max_grad_norm)
        self.opt_gpt.step()

        # ---------------------------------------------------------
        # 2. SoVITS Acoustic Generator Synthesis
        # ---------------------------------------------------------
        gen_wav = self.sovits(semantic_tokens, timbre_emb)

        # Align length between real and generated waveform
        min_len = min(real_wav.shape[-1], gen_wav.shape[-1])
        real_wav_cut = real_wav[..., :min_len]
        gen_wav_cut = gen_wav[..., :min_len]

        # ---------------------------------------------------------
        # 3. Discriminator Optimization
        # ---------------------------------------------------------
        self.opt_disc.zero_grad(set_to_none=True)

        # Real audio through MPD and MSD
        r_mpd_logits, _ = self.mpd(real_wav_cut)
        r_msd_logits, _ = self.msd(real_wav_cut)

        # Fake audio through MPD and MSD (detached)
        f_mpd_logits, _ = self.mpd(gen_wav_cut.detach())
        f_msd_logits, _ = self.msd(gen_wav_cut.detach())

        loss_d_mpd = discriminator_loss(r_mpd_logits, f_mpd_logits)
        loss_d_msd = discriminator_loss(r_msd_logits, f_msd_logits)
        loss_disc_total = loss_d_mpd + loss_d_msd
        loss_disc_total.backward()
        torch.nn.utils.clip_grad_norm_(
            list(self.mpd.parameters()) + list(self.msd.parameters()),
            self.config.train.max_grad_norm,
        )
        self.opt_disc.step()

        # ---------------------------------------------------------
        # 4. Generator Optimization
        # ---------------------------------------------------------
        self.opt_sovits.zero_grad(set_to_none=True)

        # Discriminator responses for generator gradient
        g_mpd_logits, g_mpd_fmaps = self.mpd(gen_wav_cut)
        g_msd_logits, g_msd_fmaps = self.msd(gen_wav_cut)
        _, r_mpd_fmaps = self.mpd(real_wav_cut)
        _, r_msd_fmaps = self.msd(real_wav_cut)

        # Adversarial loss
        loss_adv_mpd = generator_adversarial_loss(g_mpd_logits)
        loss_adv_msd = generator_adversarial_loss(g_msd_logits)
        loss_adv = loss_adv_mpd + loss_adv_msd

        # Feature matching loss
        loss_fm_mpd = feature_loss(r_mpd_fmaps, g_mpd_fmaps)
        loss_fm_msd = feature_loss(r_msd_fmaps, g_msd_fmaps)
        loss_fm = loss_fm_mpd + loss_fm_msd

        # Mel-spectrogram reconstruction loss
        real_mel = self.audio_proc.compute_mel_spectrogram(real_wav_cut)
        gen_mel = self.audio_proc.compute_mel_spectrogram(gen_wav_cut)
        min_mel_len = min(real_mel.shape[-1], gen_mel.shape[-1])
        loss_mel = F.l1_loss(real_mel[..., :min_mel_len], gen_mel[..., :min_mel_len]) * 45.0

        loss_gen_total = loss_adv + loss_fm + loss_mel
        loss_gen_total.backward()
        torch.nn.utils.clip_grad_norm_(self.sovits.parameters(), self.config.train.max_grad_norm)
        self.opt_sovits.step()

        step_elapsed = (time.perf_counter() - step_t0) * 1000.0  # ms

        # Periodic MPS unified memory cache clearance based on configured interval
        self._step_count += 1
        if self.device.type == "mps" and (self._step_count % self.config.train.empty_cache_interval == 0):
            torch.mps.empty_cache()
        return {
            "gpt_loss": float(gpt_loss.item()),
            "disc_loss": float(loss_disc_total.item()),
            "gen_loss": float(loss_gen_total.item()),
            "mel_loss": float(loss_mel.item()),
            "step_time_ms": step_elapsed,
        }

    @torch.no_grad()
    def synthesize(
        self,
        text: str,
        prompt_wav: Optional[torch.Tensor] = None,
        prompt_text: Optional[str] = None,
        temperature: float = 0.8,
        top_k: int = 50,
        top_p: float = 0.95,
        target_tokens_per_char: float = 3.5,
    ) -> Tuple[torch.Tensor, int, Dict[str, Any]]:
        """Synthesize natural speech from text using in-context prompt cloning on Apple Silicon.
        
        Returns: (waveform_tensor, sample_rate, metrics_dict)
        """
        self.gpt.eval()
        self.sovits.eval()

        t_start = time.perf_counter()

        # Step 1: Timbre embedding and prompt semantic tokens
        if prompt_wav is not None:
            prompt_wav = prompt_wav.to(self.device)
            timbre_emb = self.audio_proc.extract_timbre_embedding(prompt_wav, dim=self.config.sovits.prompt_dim)
            prompt_sem = self.extract_semantic_tokens_from_audio(prompt_wav).to(self.device)
            # Use up to 3 seconds of prompt semantic tokens
            max_prompt_frames = int(3.0 * (self.config.audio.sample_rate / self.config.audio.hop_length))
            if prompt_sem.size(1) > max_prompt_frames:
                prompt_sem = prompt_sem[:, :max_prompt_frames]
        else:
            # Default zero-shot timbre embedding
            timbre_emb = torch.zeros((1, self.config.sovits.prompt_dim), device=self.device)
            prompt_sem = None

        # Step 2: Text tokenization with pause markers ([SP], [AP])
        text_tokens = self.aligner.encode(text, device=self.device).unsqueeze(0)  # (1, T_text)

        # Step 3: Autoregressive Semantic Token Generation
        # Estimate semantic length based on text length
        clean_char_len = len(text.replace(" ", ""))
        expected_tokens = max(20, int(clean_char_len * target_tokens_per_char))

        t_gpt_start = time.perf_counter()
        gen_semantic_tokens = self.gpt.generate(
            text_tokens=text_tokens,
            prompt_semantic_tokens=prompt_sem,
            max_new_tokens=expected_tokens,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
        )
        gpt_time = (time.perf_counter() - t_gpt_start) * 1000.0

        # Step 4: SoVITS Waveform Synthesis on MPS
        t_sovits_start = time.perf_counter()
        # Take only the newly generated target tokens (excluding prompt prefix if present)
        if prompt_sem is not None:
            synth_sem = gen_semantic_tokens[:, prompt_sem.size(1):]
            if synth_sem.size(1) == 0:
                synth_sem = gen_semantic_tokens
        else:
            synth_sem = gen_semantic_tokens

        waveform = self.sovits(synth_sem, timbre_emb).squeeze(0)  # (1, T_audio)
        sovits_time = (time.perf_counter() - t_sovits_start) * 1000.0

        # Post-process: loudness normalization
        waveform = self.audio_proc.normalize_loudness(waveform, self.config.audio.target_lufs)

        t_end = time.perf_counter()
        total_latency_s = t_end - t_start
        total_latency_ms = total_latency_s * 1000.0

        audio_samples = waveform.shape[-1]
        audio_duration_s = audio_samples / self.config.audio.sample_rate

        # Calculate Real-Time Factor (RTF) and Throughput
        rtf = total_latency_s / max(audio_duration_s, 1e-4)
        throughput = audio_duration_s / max(total_latency_s, 1e-4)

        # Query MPS memory if running on Apple Silicon Metal
        mps_mem_mb = 0.0
        if self.device.type == "mps" and hasattr(torch.mps, "current_allocated_memory"):
            try:
                mps_mem_mb = torch.mps.current_allocated_memory() / (1024 * 1024)
            except Exception:
                mps_mem_mb = 0.0

        metrics = {
            "latency_ms": round(total_latency_ms, 2),
            "audio_duration_s": round(audio_duration_s, 3),
            "rtf": round(rtf, 4),
            "throughput_sec_per_sec": round(throughput, 2),
            "gpt_time_ms": round(gpt_time, 2),
            "sovits_time_ms": round(sovits_time, 2),
            "mps_memory_mb": round(mps_mem_mb, 2),
            "num_semantic_tokens": synth_sem.size(1),
        }

        return waveform, self.config.audio.sample_rate, metrics

    def save_checkpoint(self, path: Union[str, Path]):
        """Save pipeline weights to checkpoint file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "gpt": self.gpt.state_dict(),
            "sovits": self.sovits.state_dict(),
            "config": self.config,
        }
        torch.save(state, str(path))

    def load_checkpoint(self, path: Union[str, Path]):
        """Load pipeline weights from checkpoint file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {path}")
        state = torch.load(str(path), map_location=self.device)
        self.gpt.load_state_dict(state["gpt"])
        self.sovits.load_state_dict(state["sovits"])
