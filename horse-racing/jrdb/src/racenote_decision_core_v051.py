#!/usr/bin/env python3
"""RaceNote v0.5.1 Decision Core validator.

v0.5.1 keeps the v0.5.0 normal_view but changes five-horse compression:
1. Author an ordered ordinary five first: [◎ anchor, ○ anchor, support A/B/C].
2. Independently author one external asymmetric challenger outside that five.
3. Compare six candidates explicitly.
4. The challenger may enter only as ▲ and may not displace the two anchors.
5. If the challenger loses, the ordinary five remains intact and ▲ is assigned
   from its three ordinary support horses.

The final public marks remain [◎, ○, ▲, △1, △2], preserving downstream
settlement compatibility while making the compression decision auditable.
"""
from __future__ import annotations

from typing import Any

from racenote_save_venue_batch_v046 import validate_core as validate_v046_core

LOGIC = "RaceNote-Human-Context-Reader-0.5.1-candidate"
VERSION = "racenote-decision-core-0.5.1"

COMPRESSION_FIELD = "candidate_compression"
COMPRESSION_FIELDS = {
    "ordinary_five",
    "external_challenger_horse_no",
    "external_challenger_case",
    "excluded_horse_no",
    "decision",
    "reason",
}
DECISIONS = {"ADMIT_CHALLENGER", "KEEP_ORDINARY_FIVE", "NO_EXTERNAL_CHALLENGER"}


def _text(value: Any, minimum: int, label: str) -> None:
    if len(str(value or "").strip()) < minimum:
        raise ValueError(f"{label} too short")


def validate_core(core: dict, reader: dict) -> None:
    if not isinstance(core, dict):
        raise ValueError("Decision Core must be an object")
    if COMPRESSION_FIELD not in core:
        raise ValueError("v0.5.1 requires candidate_compression")

    # Reuse the mature v0.4.6 structural validator for the final five marks,
    # RRDB citations and reader-facing prose. v0.5.1 adds one audited layer.
    base = {k: v for k, v in core.items() if k != COMPRESSION_FIELD}
    validate_v046_core(base, reader)

    race = reader["race"]
    venue = str(race["venue"])
    race_no = int(race["race_no"])
    roster = {int(h["basic"]["horse_no"]) for h in reader.get("horses", [])}
    marks = core["marks"]

    review = core.get(COMPRESSION_FIELD)
    if not isinstance(review, dict) or set(review) != COMPRESSION_FIELDS:
        raise ValueError(f"{venue}{race_no}R: candidate_compression fields mismatch")

    ordinary = review.get("ordinary_five")
    if (
        not isinstance(ordinary, list)
        or len(ordinary) != 5
        or any(not isinstance(x, int) or isinstance(x, bool) for x in ordinary)
        or len(set(ordinary)) != 5
        or not set(ordinary) <= roster
    ):
        raise ValueError(f"{venue}{race_no}R: ordinary_five must be five unique Reader horses")

    challenger = review.get("external_challenger_horse_no")
    excluded = review.get("excluded_horse_no")
    decision = review.get("decision")
    if decision not in DECISIONS:
        raise ValueError(f"{venue}{race_no}R: invalid candidate_compression decision")

    _text(review.get("external_challenger_case"), 12, f"{venue}{race_no}R challenger case")
    _text(review.get("reason"), 16, f"{venue}{race_no}R compression reason")

    # ◎ and ○ are decided before asymmetric exploration and are protected.
    if marks[0] != ordinary[0] or marks[1] != ordinary[1]:
        raise ValueError(f"{venue}{race_no}R: ◎/○ must remain the ordinary-five anchors")

    if len(roster) == 5:
        if decision != "NO_EXTERNAL_CHALLENGER" or challenger is not None or excluded is not None:
            raise ValueError(f"{venue}{race_no}R: five-runner field requires NO_EXTERNAL_CHALLENGER")
        if set(ordinary) != roster or set(marks) != set(ordinary):
            raise ValueError(f"{venue}{race_no}R: five-runner field must retain the full ordinary five")
        if marks[2] not in ordinary[2:]:
            raise ValueError(f"{venue}{race_no}R: retained ▲ must come from ordinary support")
        return

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
        raise ValueError(f"{venue}{race_no}R: excluded_horse_no must belong to the six-candidate pool")
    if decision == "NO_EXTERNAL_CHALLENGER":
        raise ValueError(f"{venue}{race_no}R: NO_EXTERNAL_CHALLENGER is only valid in a five-runner field")

    final_expected = (set(ordinary) | {challenger}) - {excluded}
    if set(marks) != final_expected:
        raise ValueError(f"{venue}{race_no}R: final marks must equal the audited six-to-five compression")

    if decision == "ADMIT_CHALLENGER":
        if excluded == challenger:
            raise ValueError(f"{venue}{race_no}R: admitted challenger cannot be excluded")
        if excluded in ordinary[:2]:
            raise ValueError(f"{venue}{race_no}R: challenger cannot displace ◎/○ anchors")
        if marks[2] != challenger:
            raise ValueError(f"{venue}{race_no}R: admitted external challenger must be ▲")
    else:
        if excluded != challenger:
            raise ValueError(f"{venue}{race_no}R: KEEP_ORDINARY_FIVE must exclude the challenger")
        if set(marks) != set(ordinary):
            raise ValueError(f"{venue}{race_no}R: ordinary five must remain intact")
        if marks[2] not in ordinary[2:]:
            raise ValueError(f"{venue}{race_no}R: retained ▲ must come from ordinary support")
