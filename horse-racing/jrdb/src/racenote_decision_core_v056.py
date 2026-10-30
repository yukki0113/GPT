#!/usr/bin/env python3
"""RaceNote v0.5.6 Decision Core validator (shared BTDAY/FORWARD).

v0.5.5 keeps the v0.5.4 horse-selection semantics but replaces the persisted
Decision Core with a smaller audit surface. Confidence means confidence that
the ◎ horse wins the race. It is not pairwise certainty over ○.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

LOGIC = "RaceNote-Human-Context-Reader-0.5.6-candidate"
VERSION = "racenote-decision-core-0.5.6"
R4_CONTRACT_REVISION = "v055-prediction-freeze-confidence-review-r4"
R5_CONTRACT_REVISION = "v055-prediction-freeze-confidence-review-r5"
CONTRACT_REVISION = "v056-prediction-confidence-audit-newspaper-v1"
TWO_STAGE_CONTRACT_REVISIONS = {CONTRACT_REVISION}
SUPPORTED_CONTRACT_REVISIONS = {CONTRACT_REVISION}

DECISIONS = {"ADMIT_CHALLENGER", "KEEP_ORDINARY_FIVE", "NO_EXTERNAL_CHALLENGER"}
CONFIDENCE = {"A", "B", "C"}
RRDB_ROLES = {
    "UPGRADE_RECENT_FORM",
    "DOWNGRADE_APPARENT_FORM",
    "SUPPORT_REPEATABILITY",
    "SUPPORT_COUNTERARGUMENT",
    "CONTEXT_ONLY",
}

_INTERNAL = (
    "sealed Reader", "ordinary five", "ordinary_five",
    "boundary KEEP", "KEEP_ORDINARY_FIVE", "ADMIT_CHALLENGER",
    "contract_revision", "confidence_pre_result", "A5", "A7",
)
_MARK_ENUMERATION = re.compile(r"◎[0-9０-９]+[・,、 ]*○[0-9０-９]+[・,、 ]*▲[0-9０-９]+")
_MARKER = re.compile(r"[0-9０-９]+")


def _text(value: Any, minimum: int, label: str) -> str:
    text = str(value or "").strip()
    if len(text) < minimum:
        raise ValueError(f"{label} too short")
    return text


def _roster(reader: dict[str, Any]) -> set[int]:
    result = set()
    for horse in reader.get("horses", []):
        basic = horse.get("basic") or horse.get("identity") or {}
        no = basic.get("horse_no")
        if isinstance(no, int) and not isinstance(no, bool):
            result.add(no)
    return result


def _boundary_horse(ordinary: list[int], honmei: int, second: int) -> int:
    for horse in reversed(ordinary):
        if horse not in {honmei, second}:
            return horse
    raise ValueError("ordinary five has no non-anchor boundary horse")


def validate_core(
    core: dict[str, Any],
    reader: dict[str, Any],
    *,
    contract_revision: str = CONTRACT_REVISION,
) -> None:
    if contract_revision not in SUPPORTED_CONTRACT_REVISIONS:
        raise ValueError(f"unsupported v0.5.5 revision: {contract_revision}")
    if not isinstance(core, dict):
        raise ValueError("Decision Core must be an object")

    expected = {
        "venue", "race_no", "marks", "candidate_selection",
        "honmei_win", "shot_case", "rrdb_refs", "prediction_audit_comment",
    }
    if set(core) != expected:
        raise ValueError("v0.5.6 Decision Core fields mismatch")

    race = reader["race"]
    venue = str(race["venue"])
    race_no = int(race["race_no"])
    if core.get("venue") != venue or core.get("race_no") != race_no:
        raise ValueError(f"{venue}{race_no}R: Decision Core identity mismatch")

    roster = _roster(reader)
    marks = core.get("marks")
    if (
        not isinstance(marks, list)
        or len(marks) != 5
        or any(not isinstance(x, int) or isinstance(x, bool) for x in marks)
        or len(set(marks)) != 5
        or not set(marks) <= roster
    ):
        raise ValueError(f"{venue}{race_no}R: exactly five unique Reader horses required")
    honmei, second, shot = marks[0], marks[1], marks[2]

    selection = core.get("candidate_selection")
    selection_fields = {
        "ordinary_five", "external_challenger_horse_no",
        "excluded_horse_no", "decision", "boundary_reason",
    }
    if not isinstance(selection, dict) or set(selection) != selection_fields:
        raise ValueError(f"{venue}{race_no}R: candidate_selection fields mismatch")

    ordinary = selection.get("ordinary_five")
    if (
        not isinstance(ordinary, list)
        or len(ordinary) != 5
        or any(not isinstance(x, int) or isinstance(x, bool) for x in ordinary)
        or len(set(ordinary)) != 5
        or not set(ordinary) <= roster
        or honmei not in ordinary
        or second not in ordinary
    ):
        raise ValueError(f"{venue}{race_no}R: invalid ordinary five")

    decision = selection.get("decision")
    challenger = selection.get("external_challenger_horse_no")
    excluded = selection.get("excluded_horse_no")
    if decision not in DECISIONS:
        raise ValueError(f"{venue}{race_no}R: invalid candidate-selection decision")

    if len(roster) == 5:
        if decision != "NO_EXTERNAL_CHALLENGER" or challenger is not None or excluded is not None:
            raise ValueError(f"{venue}{race_no}R: five-runner field requires NO_EXTERNAL_CHALLENGER")
        if set(ordinary) != roster or set(marks) != roster:
            raise ValueError(f"{venue}{race_no}R: five-runner field must retain all runners")
        if shot not in set(ordinary) - {honmei, second}:
            raise ValueError(f"{venue}{race_no}R: ▲ must be a non-anchor ordinary horse")
    else:
        if (
            not isinstance(challenger, int)
            or isinstance(challenger, bool)
            or challenger not in roster
            or challenger in ordinary
        ):
            raise ValueError(f"{venue}{race_no}R: challenger must be one external Reader horse")
        if (
            not isinstance(excluded, int)
            or isinstance(excluded, bool)
            or excluded not in set(ordinary) | {challenger}
        ):
            raise ValueError(f"{venue}{race_no}R: invalid excluded horse")
        boundary = _boundary_horse(ordinary, honmei, second)
        _text(selection.get("boundary_reason"), 16, f"{venue}{race_no}R boundary reason")
        if decision == "ADMIT_CHALLENGER":
            if excluded != boundary:
                raise ValueError(
                    f"{venue}{race_no}R: admitted challenger must displace fixed boundary horse {boundary}"
                )
            if shot != challenger:
                raise ValueError(f"{venue}{race_no}R: admitted challenger must be ▲")
            expected_marks = (set(ordinary) | {challenger}) - {excluded}
            if set(marks) != expected_marks:
                raise ValueError(f"{venue}{race_no}R: admitted five mismatch")
        elif decision == "KEEP_ORDINARY_FIVE":
            if excluded != challenger or set(marks) != set(ordinary):
                raise ValueError(f"{venue}{race_no}R: KEEP must retain ordinary five")
            if shot not in set(ordinary) - {honmei, second}:
                raise ValueError(f"{venue}{race_no}R: retained ▲ must be non-anchor")
        else:
            raise ValueError(f"{venue}{race_no}R: NO_EXTERNAL_CHALLENGER only valid in five-runner field")

    honmei_win = core.get("honmei_win")
    expected_honmei_fields = (
        {"evidence", "main_risk"}
        if contract_revision == CONTRACT_REVISION
        else {"evidence", "main_risk", "confidence"}
    )
    if not isinstance(honmei_win, dict) or set(honmei_win) != expected_honmei_fields:
        raise ValueError(f"{venue}{race_no}R: honmei_win fields mismatch")
    _text(honmei_win.get("evidence"), 18, f"{venue}{race_no}R ◎ win evidence")
    _text(honmei_win.get("main_risk"), 10, f"{venue}{race_no}R ◎ main risk")
    if contract_revision != CONTRACT_REVISION and honmei_win.get("confidence") not in CONFIDENCE:
        raise ValueError(f"{venue}{race_no}R: confidence must be A/B/C")

    shot_case = core.get("shot_case")
    if not isinstance(shot_case, dict) or set(shot_case) != {"case"}:
        raise ValueError(f"{venue}{race_no}R: shot_case fields mismatch")
    _text(shot_case.get("case"), 12, f"{venue}{race_no}R ▲ case")

    refs = core.get("rrdb_refs")
    if not isinstance(refs, list):
        raise ValueError(f"{venue}{race_no}R: rrdb_refs must be an array")
    seen = set()
    horses = {}
    for horse in reader.get("horses", []):
        basic = horse.get("basic") or horse.get("identity") or {}
        if isinstance(basic.get("horse_no"), int):
            horses[int(basic["horse_no"])] = horse
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {"horse_no", "decision_role"}:
            raise ValueError(f"{venue}{race_no}R: RRDB ref fields mismatch")
        no = ref.get("horse_no")
        if not isinstance(no, int) or isinstance(no, bool) or no not in roster or no in seen:
            raise ValueError(f"{venue}{race_no}R: invalid or duplicate RRDB ref")
        seen.add(no)
        if ref.get("decision_role") not in RRDB_ROLES:
            raise ValueError(f"{venue}{race_no}R: invalid RRDB decision role")
        review = horses[no].get("racereview") or {}
        recommendation = review.get("recommendation") or {}
        if recommendation.get("contract_version") != "rrdb-recommendation-signals-v0.5":
            raise ValueError(f"{venue}{race_no}R: cited horse lacks RRDB v0.5 evidence")

    # Internal audit commentary is not the reader-facing newspaper text.
    # It may contain race numbers, evidence labels and shorthand.
    from racenote_v056_contract_gates import check_prediction_audit_comment
    check_prediction_audit_comment(core)


def validate_prose_collection(cores: list[dict[str, Any]]) -> None:
    seen: list[tuple[str, str]] = []
    for core in cores:
        label = f"{core.get('venue')}{core.get('race_no')}R"
        note = _MARKER.sub("#", str(core.get("prediction_audit_comment") or ""))
        note = re.sub(r"\s+", "", note)
        for prev_label, prev in seen:
            if len(note) >= 18 and SequenceMatcher(None, note, prev).ratio() >= 0.94:
                raise ValueError(f"repeated near-template audit commentary: {prev_label} / {label}")
        seen.append((label, note))
