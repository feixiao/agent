"""Multi-Period and Multi-Scale Discriminators for Mac Standalone TTS Fine-Tuning.

Optimized for Apple Silicon Metal (MPS). Computes adversarial and feature matching losses.
"""

from __future__ import annotations

from typing import List, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F


class DiscriminatorP(nn.Module):
    """Period discriminator analyzing periodic harmonic structures."""

    def __init__(self, period: int, kernel_size: int = 5, stride: int = 3):
        super().__init__()
        self.period = period
        self.convs = nn.ModuleList([
            nn.Conv2d(1, 32, (kernel_size, 1), (stride, 1), padding=((kernel_size - 1) // 2, 0)),
            nn.Conv2d(32, 128, (kernel_size, 1), (stride, 1), padding=((kernel_size - 1) // 2, 0)),
            nn.Conv2d(128, 256, (kernel_size, 1), (stride, 1), padding=((kernel_size - 1) // 2, 0)),
            nn.Conv2d(256, 512, (kernel_size, 1), (stride, 1), padding=((kernel_size - 1) // 2, 0)),
            nn.Conv2d(512, 512, (kernel_size, 1), 1, padding=((kernel_size - 1) // 2, 0)),
        ])
        self.conv_post = nn.Conv2d(512, 1, (3, 1), 1, padding=(1, 0))

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, List[torch.Tensor]]:
        if x.ndim == 1:
            x = x.unsqueeze(0).unsqueeze(0)
        elif x.ndim == 2:
            x = x.unsqueeze(1)
        fmap = []
        # Pad to multiple of period
        b, c, t = x.shape
        if t % self.period != 0:
            n_pad = self.period - (t % self.period)
            x = F.pad(x, (0, n_pad), "reflect")
            t = t + n_pad
        x = x.view(b, c, t // self.period, self.period)

        for conv in self.convs:
            x = conv(x)
            x = F.leaky_relu(x, 0.1)
            fmap.append(x)
        x = self.conv_post(x)
        fmap.append(x)
        x = torch.flatten(x, 1, -1)
        return x, fmap


class MultiPeriodDiscriminator(nn.Module):
    """Ensemble of period discriminators covering speech pitch periods."""

    def __init__(self, periods: Tuple[int, ...] = (2, 3, 5, 7, 11)):
        super().__init__()
        self.discriminators = nn.ModuleList([DiscriminatorP(p) for p in periods])

    def forward(self, x: torch.Tensor) -> Tuple[List[torch.Tensor], List[List[torch.Tensor]]]:
        logits = []
        fmaps = []
        for d in self.discriminators:
            logit, fmap = d(x)
            logits.append(logit)
            fmaps.append(fmap)
        return logits, fmaps


class DiscriminatorS(nn.Module):
    """Scale discriminator operating on raw and downsampled waveform."""

    def __init__(self):
        super().__init__()
        self.convs = nn.ModuleList([
            nn.Conv1d(1, 64, 15, 1, padding=7),
            nn.Conv1d(64, 128, 41, 4, groups=4, padding=20),
            nn.Conv1d(128, 256, 41, 4, groups=16, padding=20),
            nn.Conv1d(256, 512, 41, 4, groups=16, padding=20),
            nn.Conv1d(512, 512, 5, 1, padding=2),
        ])
        self.conv_post = nn.Conv1d(512, 1, 3, 1, padding=1)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, List[torch.Tensor]]:
        if x.ndim == 1:
            x = x.unsqueeze(0).unsqueeze(0)
        elif x.ndim == 2:
            x = x.unsqueeze(1)
        fmap = []
        for conv in self.convs:
            x = conv(x)
            x = F.leaky_relu(x, 0.1)
            fmap.append(x)
        x = self.conv_post(x)
        fmap.append(x)
        x = torch.flatten(x, 1, -1)
        return x, fmap


class MultiScaleDiscriminator(nn.Module):
    """Ensemble of scale discriminators operating at 1x, 2x, 4x audio scales."""

    def __init__(self):
        super().__init__()
        self.discriminators = nn.ModuleList([
            DiscriminatorS(),
            DiscriminatorS(),
            DiscriminatorS(),
        ])
        self.meanpools = nn.ModuleList([
            nn.AvgPool1d(4, 2, padding=2),
            nn.AvgPool1d(4, 2, padding=2),
        ])

    def forward(self, x: torch.Tensor) -> Tuple[List[torch.Tensor], List[List[torch.Tensor]]]:
        logits = []
        fmaps = []
        for i, d in enumerate(self.discriminators):
            if i != 0:
                x = self.meanpools[i - 1](x)
            logit, fmap = d(x)
            logits.append(logit)
            fmaps.append(fmap)
        return logits, fmaps


def feature_loss(fmap_r: List[List[torch.Tensor]], fmap_g: List[List[torch.Tensor]]) -> torch.Tensor:
    """Compute L1 feature matching loss across discriminator intermediate layers."""
    loss = 0.0
    for dr, dg in zip(fmap_r, fmap_g):
        for rl, gl in zip(dr, dg):
            loss = loss + torch.mean(torch.abs(rl - gl))
    return loss * 2.0


def discriminator_loss(disc_real_outputs: List[torch.Tensor], disc_generated_outputs: List[torch.Tensor]) -> torch.Tensor:
    """Least-squares GAN loss for discriminator."""
    loss = 0.0
    for dr, dg in zip(disc_real_outputs, disc_generated_outputs):
        r_loss = torch.mean((1.0 - dr) ** 2)
        g_loss = torch.mean(dg ** 2)
        loss = loss + (r_loss + g_loss)
    return loss


def generator_adversarial_loss(disc_outputs: List[torch.Tensor]) -> torch.Tensor:
    """Least-squares GAN loss for generator."""
    loss = 0.0
    for dg in disc_outputs:
        loss = loss + torch.mean((1.0 - dg) ** 2)
    return loss
