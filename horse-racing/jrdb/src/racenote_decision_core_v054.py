#!/usr/bin/env python3
"""v0.5.4 Decision Core guard: preserve v0.5.3 r2 boundary and assess prose.

The validator is intentionally mechanical. It cannot prove that a claim is
true or that a model has made a sound judgment.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any
from racenote_decision_core_v053 import validate_core as validate_v053_core

LOGIC = "RaceNote-Human-Context-Reader-0.5.4-candidate"
VERSION = "racenote-decision-core-0.5.4"
CONTRACT_REVISION = "v054-context-evidence-r1"

_INTERNAL = (
    "sealed Reader", "ordinary five", "ordinary_five",
    "boundary KEEP", "KEEP_ORDINARY_FIVE", "ADMIT_CHALLENGER",
    "contract_revision", "v053-boundary", "r2既定", "r2の固定",
    "全馬比較し", "通常五頭を先に固定", "通常五頭を維持",
)
_GENERIC_PATTERNS = (
    r"◎\d+・○\d+を選択",
    r"勝ち切り優先で◎",
    r"主線二頭と異なる.*勝ち筋を評価",
)


def validate_prose(core: dict[str, Any]) -> None:
    prose = core.get("reader_facing_reason")
    if not isinstance(prose, str):
        raise ValueError("reader_facing_reason must be model-authored text")
    prose = prose.strip()
    if not 45 <= len(prose) <= 240:
        raise ValueError("reader_facing_reason must be a useful compact newspaper note (45-240 chars)")
    for bad in _INTERNAL:
        if bad in prose:
            raise ValueError(f"reader_facing_reason contains internal/template language: {bad}")
    for pattern in _GENERIC_PATTERNS:
        if re.search(pattern, prose):
            raise ValueError("reader_facing_reason repeats mark-enumeration template")
    marks = core.get("marks", [])
    if len(marks) != 5:
        raise ValueError("five marks required")
    if not any(token in prose for token in (f"◎{marks[0]}", f"{marks[0]}を◎", f"{marks[0]}は", f"{marks[0]}の")):
        raise ValueError("reader_facing_reason must concretely discuss the ◎ horse")
    if not any(token in prose for token in (f"○{marks[1]}", f"{marks[1]}を○", f"{marks[1]}は", f"{marks[1]}も")):
        raise ValueError("reader_facing_reason must discuss the ○ comparison")
    # Language/style checks are heuristics. Source support is a human/model audit.


def validate_core(
    core: dict[str, Any],
    reader: dict[str, Any],
    *,
    contract_revision: str = CONTRACT_REVISION,
) -> None:
    if contract_revision != CONTRACT_REVISION:
        raise ValueError(f"unsupported v0.5.4 revision: {contract_revision}")
    validate_v053_core(
        core,
        reader,
        contract_revision="v053-boundary-safety-r2",
        rrdb_contract="rrdb-recommendation-signals-v0.5",
    )
    validate_prose(core)


def validate_prose_collection(cores: list[dict[str, Any]]) -> None:
    """Catch a card-wide formula with only horse numbers changed.

    Race-specific wording remains a model-authorship obligation; this is a
    deterministic near-duplicate warning barrier, not a naturalness score.
    """
    seen: list[tuple[str, str]] = []
    for core in cores:
        venue = str(core.get("venue") or "")
        race_no = str(core.get("race_no") or "")
        label = f"{venue}{race_no}R"
        note = re.sub(r"[0-9０-９]+", "#", str(core.get("reader_facing_reason") or ""))
        note = re.sub(r"\s+", "", note)
        for previous_label, previous in seen:
            if SequenceMatcher(None, note, previous).ratio() >= 0.94:
                raise ValueError(
                    f"repeated near-template newspaper prose: {previous_label} / {label}"
                )
        seen.append((label, note))
