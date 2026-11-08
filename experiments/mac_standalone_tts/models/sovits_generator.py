"""Acoustic Decoder / HiFi-GAN Vocoder (SoVITS Generator) for Mac Standalone TTS.

Converts speech semantic tokens and speaker timbre embedding into high-fidelity
32kHz audio waveform. Optimized for Apple Silicon Metal (MPS).
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F

from ..config import SoVITSConfig


class ResBlock(nn.Module):
    """Multi-receptive field residual block with dilated convolutions."""

    def __init__(
        self,
        channels: int,
        kernel_size: int = 3,
        dilations: Tuple[int, ...] = (1, 3, 5),
    ):
        super().__init__()
        self.convs1 = nn.ModuleList([
            nn.Conv1d(
                channels,
                channels,
                kernel_size,
                stride=1,
                dilation=d,
                padding=(kernel_size * d - d) // 2,
            )
            for d in dilations
        ])
        self.convs2 = nn.ModuleList([
            nn.Conv1d(
                channels,
                channels,
                kernel_size,
                stride=1,
                dilation=1,
                padding=(kernel_size - 1) // 2,
            )
            for _ in dilations
        ])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for c1, c2 in zip(self.convs1, self.convs2):
            xt = F.leaky_relu(x, 0.1)
            xt = c1(xt)
            xt = F.leaky_relu(xt, 0.1)
            xt = c2(xt)
            x = x + xt
        return x


class SoVITSGenerator(nn.Module):
    """HiFi-GAN / VITS Acoustic Waveform Generator for Apple Silicon MPS."""

    def __init__(self, config: Optional[SoVITSConfig] = None):
        super().__init__()
        self.config = config or SoVITSConfig()

        # Semantic token projection
        self.sem_embedding = nn.Embedding(1024, self.config.semantic_dim)
        self.prenet = nn.Conv1d(self.config.semantic_dim, self.config.hidden_dim, kernel_size=7, padding=3)

        # Speaker timbre condition projection
        self.cond_proj = nn.Linear(self.config.prompt_dim, self.config.hidden_dim)

        # Upsampling blocks (8 * 8 * 2 * 2 = 256x upsampling to match 32kHz)
        self.ups = nn.ModuleList()
        in_ch = self.config.hidden_dim
        for u_rate, u_kernel in zip(self.config.upsample_rates, self.config.upsample_kernel_sizes):
            out_ch = in_ch // 2
            self.ups.append(
                nn.ConvTranspose1d(
                    in_ch,
                    out_ch,
                    kernel_size=u_kernel,
                    stride=u_rate,
                    padding=(u_kernel - u_rate) // 2,
                )
            )
            in_ch = out_ch

        # Multi-Receptive Field Residual Blocks
        self.resblocks = nn.ModuleList()
        ch = self.config.hidden_dim
        for u_rate in self.config.upsample_rates:
            ch = ch // 2
            for k, d in zip(self.config.resblock_kernel_sizes, self.config.resblock_dilation_sizes):
                self.resblocks.append(ResBlock(ch, kernel_size=k, dilations=d))

        self.num_upsamples = len(self.config.upsample_rates)
        self.num_resblocks_per_stage = len(self.config.resblock_kernel_sizes)

        # Final output projection to waveform (1 channel)
        self.conv_post = nn.Conv1d(ch, 1, kernel_size=7, stride=1, padding=3)

    def forward(
        self,
        semantic_tokens: torch.Tensor,
        timbre_emb: torch.Tensor,
    ) -> torch.Tensor:
        """Generate waveform from semantic tokens and timbre embedding.
        
        semantic_tokens: (B, T_sem) LongTensor
        timbre_emb: (B, prompt_dim) FloatTensor
        
        Returns: (B, 1, T_audio) synthesized waveform.
        """
        if semantic_tokens.ndim == 1:
            semantic_tokens = semantic_tokens.unsqueeze(0)
        if timbre_emb.ndim == 1:
            timbre_emb = timbre_emb.unsqueeze(0)

        # (B, T_sem, semantic_dim) -> (B, semantic_dim, T_sem)
        x = self.sem_embedding(semantic_tokens).transpose(1, 2)
        x = self.prenet(x)  # (B, hidden_dim, T_sem)

        # Add speaker timbre condition across time
        cond = self.cond_proj(timbre_emb).unsqueeze(-1)  # (B, hidden_dim, 1)
        x = x + cond

        # Progressive upsampling + multi-receptive field filtering
        res_idx = 0
        for i, up in enumerate(self.ups):
            x = F.leaky_relu(x, 0.1)
            x = up(x)
            # Parallel resblocks
            xs = torch.zeros_like(x)
            for _ in range(self.num_resblocks_per_stage):
                xs = xs + self.resblocks[res_idx](x)
                res_idx += 1
            x = xs / self.num_resblocks_per_stage

        x = F.leaky_relu(x, 0.1)
        waveform = torch.tanh(self.conv_post(x))  # (B, 1, T_audio)
        return waveform
