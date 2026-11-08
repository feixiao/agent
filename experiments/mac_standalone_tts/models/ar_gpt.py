"""Autoregressive Text-to-Semantic Transformer for Mac Standalone TTS.

Predicts discrete speech semantic tokens conditioned on text phoneme sequence
and acoustic prompt reference prefix. Fully compatible with Apple Silicon Metal (MPS).
"""

from __future__ import annotations

import math
from typing import Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F

from ..config import ARGptConfig


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding."""

    def __init__(self, d_model: int, max_len: int = 2048):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))  # (1, max_len, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, d_model)
        return x + self.pe[:, :x.size(1), :]


class ARGptModel(nn.Module):
    """Autoregressive Transformer predicting speech semantic tokens from text phonemes."""

    def __init__(self, config: Optional[ARGptConfig] = None):
        super().__init__()
        self.config = config or ARGptConfig()

        # Separate embeddings for text phonemes and semantic tokens
        self.text_embedding = nn.Embedding(self.config.text_vocab_size, self.config.d_model)
        self.semantic_embedding = nn.Embedding(self.config.semantic_vocab_size, self.config.d_model)

        # Modality type embedding (0 for text, 1 for speech semantic tokens)
        self.modality_embedding = nn.Embedding(2, self.config.d_model)

        self.pos_encoder = PositionalEncoding(self.config.d_model, self.config.max_seq_len)
        self.layer_norm = nn.LayerNorm(self.config.d_model)
        self.dropout = nn.Dropout(self.config.dropout)

        # Causal Transformer Decoder
        decoder_layer = nn.TransformerEncoderLayer(
            d_model=self.config.d_model,
            nhead=self.config.nhead,
            dim_feedforward=self.config.dim_feedforward,
            dropout=self.config.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(
            decoder_layer,
            num_layers=self.config.num_layers,
            enable_nested_tensor=False,
        )

        # Projection head to semantic token vocabulary
        self.head = nn.Linear(self.config.d_model, self.config.semantic_vocab_size)

        # Precomputed boolean causal mask buffer for fast Metal attention without per-step allocation
        causal_mask_bool = torch.triu(
            torch.ones((self.config.max_seq_len, self.config.max_seq_len), dtype=torch.bool),
            diagonal=1,
        )
        self.register_buffer("causal_mask_bool", causal_mask_bool)

    def _generate_causal_mask(self, sz: int, device: torch.device) -> torch.Tensor:
        """Return contiguous boolean upper-triangular causal mask."""
        if sz <= self.config.max_seq_len:
            return self.causal_mask_bool[:sz, :sz].contiguous()
        return torch.triu(torch.ones((sz, sz), dtype=torch.bool, device=device), diagonal=1)

    def forward(
        self,
        text_tokens: torch.Tensor,
        semantic_tokens: torch.Tensor,
        return_loss: bool = True,
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """Forward pass for training and evaluation on MPS.
        
        text_tokens: (B, T_text) LongTensor
        semantic_tokens: (B, T_sem) LongTensor
        
        Returns: (logits, loss)
        """
        device = text_tokens.device
        B = text_tokens.size(0)

        # Embed text
        text_emb = self.text_embedding(text_tokens) + self.modality_embedding(torch.zeros_like(text_tokens))

        # For autoregressive semantic token prediction, shift input by 1
        sem_input = semantic_tokens[:, :-1]
        sem_target = semantic_tokens[:, 1:]

        sem_emb = self.semantic_embedding(sem_input) + self.modality_embedding(torch.ones_like(sem_input))

        # Concatenate: [Text tokens] + [Semantic tokens]
        combined_emb = torch.cat([text_emb, sem_emb], dim=1)
        combined_emb = self.pos_encoder(combined_emb)
        combined_emb = self.layer_norm(self.dropout(combined_emb))

        total_len = combined_emb.size(1)
        causal_mask = self._generate_causal_mask(total_len, device)

        # Run Transformer on MPS
        hidden = self.transformer(combined_emb, mask=causal_mask, is_causal=True)

        # Extract semantic token output states
        t_text = text_tokens.size(1)
        sem_hidden = hidden[:, t_text:, :]  # (B, T_sem - 1, d_model)
        logits = self.head(sem_hidden)      # (B, T_sem - 1, semantic_vocab_size)

        loss = None
        if return_loss and sem_target.size(1) > 0:
            loss = F.cross_entropy(
                logits.reshape(-1, self.config.semantic_vocab_size),
                sem_target.reshape(-1),
                ignore_index=0,  # PAD_ID
            )

        return logits, loss

    @torch.no_grad()
    def generate(
        self,
        text_tokens: torch.Tensor,
        prompt_semantic_tokens: Optional[torch.Tensor] = None,
        max_new_tokens: int = 150,
        temperature: float = 0.8,
        top_k: int = 50,
        top_p: float = 0.95,
    ) -> torch.Tensor:
        """Autoregressively generate semantic tokens conditioned on text and acoustic prompt."""
        self.eval()
        device = text_tokens.device
        if text_tokens.ndim == 1:
            text_tokens = text_tokens.unsqueeze(0)

        B = text_tokens.size(0)
        text_mod = self.modality_embedding.weight[0].view(1, 1, -1)
        sem_mod = self.modality_embedding.weight[1].view(1, 1, -1)
        text_emb = self.text_embedding(text_tokens) + text_mod

        if prompt_semantic_tokens is not None and prompt_semantic_tokens.size(1) > 0:
            if prompt_semantic_tokens.ndim == 1:
                prompt_semantic_tokens = prompt_semantic_tokens.unsqueeze(0)
            curr_sem = prompt_semantic_tokens.clone()
        else:
            # Start with BOS semantic token (id=1)
            curr_sem = torch.ones((B, 1), dtype=torch.long, device=device)

        eos_id = 2

        for _ in range(max_new_tokens):
            sem_emb = self.semantic_embedding(curr_sem) + sem_mod
            combined_emb = torch.cat([text_emb, sem_emb], dim=1)
            combined_emb = self.pos_encoder(combined_emb)
            combined_emb = self.layer_norm(combined_emb)

            sz = combined_emb.size(1)
            mask = self._generate_causal_mask(sz, device)
            hidden = self.transformer(combined_emb, mask=mask, is_causal=True)

            next_logits = self.head(hidden[:, -1, :]) / max(temperature, 1e-4)

            # Top-K filtering
            if top_k > 0:
                min_val = torch.topk(next_logits, min(top_k, next_logits.size(-1)))[0][..., -1, None]
                next_logits = next_logits.masked_fill(next_logits < min_val, float("-inf"))

            # Top-P (nucleus) filtering
            if top_p < 1.0:
                sorted_logits, sorted_indices = torch.sort(next_logits, descending=True)
                cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                sorted_indices_to_remove = F.pad((cumulative_probs > top_p)[..., :-1], (1, 0), value=False)
                indices_to_remove = sorted_indices_to_remove.scatter(1, sorted_indices, sorted_indices_to_remove)
                next_logits = next_logits.masked_fill(indices_to_remove, float("-inf"))

            probs = F.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            curr_sem = torch.cat([curr_sem, next_token], dim=1)

            # Check if all batches reached EOS
            if (next_token == eos_id).all():
                break

        return curr_sem
