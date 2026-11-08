"""Text normalization, Phonemizer, and alignment tokenizer for Mac Standalone TTS.

Supports Chinese characters, Pinyin/Phonemes, English words, numbers, and
special acoustic breath/pause markers ([SP] short pause, [AP] aspiration/breath).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Union
import torch


# Special acoustic token IDs
PAD_ID = 0
BOS_ID = 1
EOS_ID = 2
UNK_ID = 3
SP_ID = 4  # Short pause (comma, semicolon, ~150-250ms)
AP_ID = 5  # Aspiration / breath pause (full stop, exclamation, question, ~350-500ms)


class PhonemeAligner:
    """Handles text normalization, G2P phoneme conversion, and tokenization."""

    # Chinese number words
    NUM_MAP = {
        "0": "零", "1": "一", "2": "二", "3": "三", "4": "四",
        "5": "五", "6": "六", "7": "七", "8": "八", "9": "九",
    }

    def __init__(self, vocab_size: int = 1024):
        self.vocab_size = vocab_size
        self._vocab: Dict[str, int] = {
            "<pad>": PAD_ID,
            "<bos>": BOS_ID,
            "<eos>": EOS_ID,
            "<unk>": UNK_ID,
            "[SP]": SP_ID,
            "[AP]": AP_ID,
        }
        self._rev_vocab: Dict[int, str] = {v: k for k, v in self._vocab.items()}
        self._init_extended_vocab()

    def _init_extended_vocab(self):
        """Populate initial phoneme and character vocabulary."""
        # Common Chinese initials and finals (pinyin phonemes)
        initials = [
            "b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h",
            "j", "q", "x", "zh", "ch", "sh", "r", "z", "c", "s", "y", "w"
        ]
        finals = [
            "a", "o", "e", "i", "u", "v", "ai", "ei", "ui", "ao", "ou",
            "iu", "ie", "ve", "er", "an", "en", "in", "un", "vn",
            "ang", "eng", "ing", "ong", "ia", "ian", "iang", "iao", "iong",
            "ua", "uai", "uan", "uang", "uo"
        ]
        tones = ["1", "2", "3", "4", "5"]

        # Add pinyin combinations
        for init in initials:
            if init not in self._vocab and len(self._vocab) < self.vocab_size:
                idx = len(self._vocab)
                self._vocab[init] = idx
                self._rev_vocab[idx] = init

        for fin in finals:
            for tone in tones:
                sym = f"{fin}{tone}"
                if sym not in self._vocab and len(self._vocab) < self.vocab_size:
                    idx = len(self._vocab)
                    self._vocab[sym] = idx
                    self._rev_vocab[idx] = sym

        # Common ASCII letters and symbols
        for ch in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if ch not in self._vocab and len(self._vocab) < self.vocab_size:
                idx = len(self._vocab)
                self._vocab[ch] = idx
                self._rev_vocab[idx] = ch

    def normalize_text(self, text: str) -> str:
        """Normalize numbers, clean spaces, and standardize punctuation."""
        # Normalize digits to Chinese characters
        for digit, word in self.NUM_MAP.items():
            text = text.replace(digit, word)
        # Remove quotation marks and extraneous symbols first
        text = re.sub(r"[\"“”'‘’（）()《》【】\[\]{}—…]+", " ", text)
        # Standardize punctuation to breath/pause markers
        # Full stop, question mark, exclamation mark -> [AP] (aspiration / breath)
        text = re.sub(r"[。！？!?]+", " [AP] ", text)
        # Comma, semicolon, colon, dash -> [SP] (short pause)
        text = re.sub(r"[，；：、,;:]+", " [SP] ", text)
        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def tokenize(self, text: str, add_special_tokens: bool = True) -> List[int]:
        """Convert normalized text with [SP]/[AP] markers into token IDs."""
        normalized = self.normalize_text(text)
        tokens: List[int] = []

        if add_special_tokens:
            tokens.append(BOS_ID)

        # Split by whitespace while preserving [SP] and [AP]
        parts = normalized.split()
        for part in parts:
            if part == "[SP]":
                tokens.append(SP_ID)
            elif part == "[AP]":
                tokens.append(AP_ID)
            else:
                # Character / subword level tokenization
                for ch in part:
                    ch_lower = ch.lower()
                    if ch in self._vocab:
                        tokens.append(self._vocab[ch])
                    elif ch_lower in self._vocab:
                        tokens.append(self._vocab[ch_lower])
                    else:
                        # Dynamic assignment into remaining vocabulary space
                        if len(self._vocab) < self.vocab_size:
                            new_id = len(self._vocab)
                            self._vocab[ch] = new_id
                            self._rev_vocab[new_id] = ch
                            tokens.append(new_id)
                        else:
                            # Hash to existing token range above special tokens
                            h = (hash(ch) % (self.vocab_size - 10)) + 10
                            tokens.append(h)

        if add_special_tokens:
            tokens.append(EOS_ID)

        return tokens

    def encode(self, text: str, device: Optional[torch.device] = None) -> torch.Tensor:
        """Encode text to 1D LongTensor (seq_len,) or 2D (1, seq_len)."""
        token_ids = self.tokenize(text, add_special_tokens=True)
        tensor = torch.tensor(token_ids, dtype=torch.long)
        if device is not None:
            tensor = tensor.to(device)
        return tensor

    def decode(self, token_ids: Union[List[int], torch.Tensor]) -> str:
        """Decode token IDs back to human-readable string."""
        if isinstance(token_ids, torch.Tensor):
            token_ids = token_ids.detach().cpu().tolist()
        words = []
        for tid in token_ids:
            if tid in self._rev_vocab:
                words.append(self._rev_vocab[tid])
            else:
                words.append(f"<tok_{tid}>")
        return "".join(words)
