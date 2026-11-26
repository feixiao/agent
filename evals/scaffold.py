"""Two-axis Subject vs. Scaffold versioning for reproducible Agent evaluations.

Adapted from the design principles of ``google-deepmind/gbench``
(``gbench/core/scaffold.py`` and ``docs/scaffold-versioning.md``):

* **Subject** is what is under test (checkpoint, quantization, or agent build).
* **Scaffold** is how it was asked and scored (prompt, schema, scoring logic,
  tool permissions, attempts, decode settings, dataset snapshot, serving
  environment, and load shape).

Hashing the two axes separately enables valid model/quantization sweeps while
breaking comparisons whenever the harness/scaffold silently moves. Honest
coverage tracks ``covers`` and ``unpinned`` fields explicitly so an ID never
over-promises rigor.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from enum import Enum

from typing import Any
CONTRACT_VERSION = 1


class ContractField(str, Enum):
    """Canonical fields in a benchmark condition contract."""

    MODEL_CHECKPOINT = "model_checkpoint"
    QUANTIZATION = "quantization"
    PROMPT_VERSION = "prompt_version"
    SCHEMA_VERSION = "schema_version"
    SCORING_VERSION = "scoring_version"
    TOOL_PERMISSIONS = "tool_permissions"
    ATTEMPTS = "attempts"
    DECODE = "decode"
    DATASET_SNAPSHOT = "dataset_snapshot"
    SERVING_ENVIRONMENT = "serving_environment"
    LOAD_SHAPE = "load_shape"


SUBJECT_FIELDS: frozenset[ContractField] = frozenset(
    {
        ContractField.MODEL_CHECKPOINT,
        ContractField.QUANTIZATION,
    }
)

SCAFFOLD_FIELDS: frozenset[ContractField] = frozenset(
    {
        ContractField.PROMPT_VERSION,
        ContractField.SCHEMA_VERSION,
        ContractField.SCORING_VERSION,
        ContractField.TOOL_PERMISSIONS,
        ContractField.ATTEMPTS,
        ContractField.DECODE,
        ContractField.DATASET_SNAPSHOT,
        ContractField.SERVING_ENVIRONMENT,
        ContractField.LOAD_SHAPE,
    }
)


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _short_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class SubjectSpec:
    """What is under test (weights / quantization / agent variant)."""

    model_checkpoint: str
    quantization: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def covered_fields(self) -> list[str]:
        covered = [ContractField.MODEL_CHECKPOINT.value]
        if self.quantization is not None:
            covered.append(ContractField.QUANTIZATION.value)
        return sorted(covered)

    def unpinned_fields(self) -> list[str]:
        covered = set(self.covered_fields())
        return sorted(f.value for f in SUBJECT_FIELDS if f.value not in covered)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model_checkpoint": self.model_checkpoint,
            "quantization": self.quantization,
        }
        if self.extra:
            payload["extra"] = dict(self.extra)
        return payload

    def subject_id(self) -> str:
        return _short_hash(self.to_dict())


@dataclass(frozen=True)
class ScaffoldSpec:
    """How the subject was asked, served, and scored."""

    prompt_version: str | None = None
    schema_version: str | None = None
    scoring_version: str | int | None = None
    tool_permissions: tuple[str, ...] | None = None
    attempts: int | None = None
    decode: dict[str, Any] | None = None
    dataset_snapshot: str | None = None
    serving_environment: dict[str, Any] | None = None
    load_shape: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        if raw["tool_permissions"] is not None:
            raw["tool_permissions"] = list(raw["tool_permissions"])
        return {k: v for k, v in raw.items() if v is not None}

    def covered_fields(self) -> list[str]:
        present = self.to_dict()
        return sorted(f.value for f in SCAFFOLD_FIELDS if f.value in present)

    def unpinned_fields(self) -> list[str]:
        covered = set(self.covered_fields())
        return sorted(f.value for f in SCAFFOLD_FIELDS if f.value not in covered)

    def scaffold_id(self) -> str | None:
        covered = self.covered_fields()
        if not covered:
            return None
        return _short_hash(self.to_dict())


@dataclass(frozen=True)
class RunCondition:
    """Combined Subject + Scaffold condition emitted alongside benchmark results."""

    pillar: str
    subject: SubjectSpec
    scaffold: ScaffoldSpec
    contract_version: int = CONTRACT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "pillar": self.pillar,
            "subject_id": self.subject.subject_id(),
            "subject": {
                **self.subject.to_dict(),
                "covers": self.subject.covered_fields(),
                "unpinned": self.subject.unpinned_fields(),
            },
            "scaffold_id": self.scaffold.scaffold_id(),
            "scaffold": {
                **self.scaffold.to_dict(),
                "covers": self.scaffold.covered_fields(),
                "unpinned": self.scaffold.unpinned_fields(),
            },
        }


def compare_conditions(baseline: RunCondition, candidate: RunCondition) -> dict[str, Any]:
    """Judge whether two runs can be compared on the same series.

    Mirrors gbench's two-axis rule:
    - subject only moved -> valid (model or quantization delta)
    - scaffold only moved -> new condition (break series, diff it)
    - both moved -> uninterpretable (do not plot on one line)
    """
    if baseline.pillar != candidate.pillar:
        return {
            "comparable": False,
            "verdict": "different_pillar",
            "reason": f"pillar changed: {baseline.pillar} -> {candidate.pillar}",
        }

    base_sid = baseline.subject.subject_id()
    cand_sid = candidate.subject.subject_id()
    base_hid = baseline.scaffold.scaffold_id()
    cand_hid = candidate.scaffold.scaffold_id()

    if base_hid is None or cand_hid is None:
        return {
            "comparable": False,
            "verdict": "unpinned_scaffold",
            "reason": "scaffold_id is null (no scaffold fields pinned)",
        }

    subject_moved = base_sid != cand_sid
    scaffold_moved = base_hid != cand_hid

    if not subject_moved and not scaffold_moved:
        return {
            "comparable": True,
            "verdict": "identical",
            "reason": "subject_id and scaffold_id both match",
        }
    if subject_moved and not scaffold_moved:
        return {
            "comparable": True,
            "verdict": "valid_subject_delta",
            "reason": f"scaffold held fixed ({base_hid}); valid model/quant delta",
        }
    if not subject_moved and scaffold_moved:
        return {
            "comparable": False,
            "verdict": "scaffold_changed_break_series",
            "reason": f"subject fixed ({base_sid}), scaffold moved ({base_hid} -> {cand_hid}); break series",
        }
    return {
        "comparable": False,
        "verdict": "both_changed_uninterpretable",
        "reason": f"both subject ({base_sid}->{cand_sid}) and scaffold ({base_hid}->{cand_hid}) moved",
    }
