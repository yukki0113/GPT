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
CONTRACT_REVISION = "v054-authored-prose-r3"
R2_CONTRACT_REVISION = "v054-authored-prose-r2"
LEGACY_CONTRACT_REVISIONS = {"v054-context-evidence-r1", R2_CONTRACT_REVISION}
SUPPORTED_CONTRACT_REVISIONS = LEGACY_CONTRACT_REVISIONS | {CONTRACT_REVISION}

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
_PROGRAMMATIC_TEMPLATE_PHRASES = (
    "勝ち切る形を最も描きやすい",
    "現条件へのつながりで◎を上に置く",
    "主線と異なる流れで浮上余地がある",
)


def validate_prose(
    core: dict[str, Any],
    *,
    contract_revision: str | None = None,
    require_authorship: bool | None = None,
) -> None:
    """Validate reader prose while preserving the pre-r3 direct-call API.

    Production validation passes contract_revision explicitly. Calls using the
    historical require_authorship flag retain the old r1/r2 behavior for tests
    and immutable verification utilities.
    """
    legacy_direct_call = contract_revision is None
    if contract_revision is None:
        contract_revision = R2_CONTRACT_REVISION if require_authorship else "v054-context-evidence-r1"
    prose = core.get("reader_facing_reason")
    if not isinstance(prose, str):
        raise ValueError("reader_facing_reason must be model-authored text")
    prose = prose.strip()
    if not 35 <= len(prose) <= 240:
        raise ValueError("reader_facing_reason must be a useful compact newspaper note (35-240 chars)")
    for bad in _INTERNAL:
        if bad in prose:
            raise ValueError(f"reader_facing_reason contains internal/template language: {bad}")
    for pattern in _GENERIC_PATTERNS:
        if re.search(pattern, prose):
            raise ValueError("reader_facing_reason repeats mark-enumeration template")
    marks = core.get("marks", [])
    if len(marks) != 5:
        raise ValueError("five marks required")

    if contract_revision in {"v054-context-evidence-r1", R2_CONTRACT_REVISION}:
        if not any(token in prose for token in (f"◎{marks[0]}", f"{marks[0]}を◎", f"{marks[0]}は", f"{marks[0]}の")):
            raise ValueError("reader_facing_reason must concretely discuss the ◎ horse")
        if not any(token in prose for token in (f"○{marks[1]}", f"{marks[1]}を○", f"{marks[1]}は", f"{marks[1]}も")):
            raise ValueError("reader_facing_reason must discuss the ○ comparison")

    authorship_required = (
        contract_revision in {R2_CONTRACT_REVISION, CONTRACT_REVISION}
        or (legacy_direct_call and require_authorship is True)
    )
    if authorship_required:
        for phrase in _PROGRAMMATIC_TEMPLATE_PHRASES:
            if phrase in prose:
                raise ValueError(
                    f"reader_facing_reason contains prohibited programmatic-template phrase: {phrase}"
                )
        authorship = core.get("reader_facing_reason_authorship")
        if not isinstance(authorship, dict):
            raise ValueError("reader_facing_reason_authorship required")
        if authorship.get("mode") != "MODEL_AUTHORED_PER_RACE":
            raise ValueError("reader_facing_reason must be model-authored per race")
        if authorship.get("programmatic_template") is not False:
            raise ValueError("programmatic newspaper-prose templates are prohibited")
        basis = authorship.get("basis")
        allowed_basis = {
            "race_model", "mainline_cases", "single_shot_case", "boundary_review",
            "honmei_win_case", "second_case", "ranking_reason",
        }
        if not isinstance(basis, list) or not basis or any(x not in allowed_basis for x in basis):
            raise ValueError("reader-facing prose must cite its authored Decision Core basis")
        if contract_revision == R2_CONTRACT_REVISION and (
            "honmei_win_case" not in basis or "ranking_reason" not in basis
        ):
            raise ValueError("r2 reader-facing prose basis requires honmei_win_case and ranking_reason")
    # Language/style checks are heuristics. Source support is a human/model audit.


def validate_core(
    core: dict[str, Any],
    reader: dict[str, Any],
    *,
    contract_revision: str = CONTRACT_REVISION,
) -> None:
    if contract_revision not in SUPPORTED_CONTRACT_REVISIONS:
        raise ValueError(f"unsupported v0.5.4 revision: {contract_revision}")
    legacy_core = {k: v for k, v in core.items() if k != "reader_facing_reason_authorship"}
    validate_v053_core(
        legacy_core,
        reader,
        contract_revision="v053-boundary-safety-r2",
        rrdb_contract="rrdb-recommendation-signals-v0.5",
    )
    validate_prose(core, contract_revision=contract_revision)


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
