#!/usr/bin/env python3
"""RaceNote v0.5.2 Decision Core validator.

v0.5.2 preserves the v0.5.1 six-to-five candidate-set protection while
separating candidate membership from aggressive role assignment.

1. Build an ordinary five without creating a vacancy for an external shot.
2. Re-rank only inside that ordinary five to choose a win-first ◎ and ○.
3. Search exactly one external asymmetric challenger.
4. The challenger may enter only as ▲ and may not displace the chosen ◎/○.
5. If the challenger loses, the ordinary five remains intact and ▲ is chosen
   from the remaining three ordinary horses.

This lets ◎/○ be more attack-oriented than v0.5.1 without returning to the
v0.5.0 failure mode where role assignment could destabilize the whole set.
"""
from __future__ import annotations

from typing import Any

from racenote_save_venue_batch_v046 import validate_core as validate_v046_core

LOGIC = "RaceNote-Human-Context-Reader-0.5.2-candidate"
VERSION = "racenote-decision-core-0.5.2"

COMPRESSION_FIELD = "candidate_compression"
ROLE_FIELD = "role_assignment"
COMPRESSION_FIELDS = {
    "ordinary_five",
    "external_challenger_horse_no",
    "external_challenger_case",
    "excluded_horse_no",
    "decision",
    "reason",
}
ROLE_FIELDS = {
    "honmei_horse_no",
    "second_horse_no",
    "honmei_win_case",
    "second_case",
    "honmei_selection_mode",
    "shot_selection_mode",
    "ranking_reason",
}
DECISIONS = {"ADMIT_CHALLENGER", "KEEP_ORDINARY_FIVE", "NO_EXTERNAL_CHALLENGER"}
HONMEI_MODE = "WIN_FIRST_NOT_PLACE_FIRST"
SHOT_MODE = "ASYMMETRIC_PAYOUT_ROUTE_NOT_ORDINARY_RANK"


def _text(value: Any, minimum: int, label: str) -> None:
    if len(str(value or "").strip()) < minimum:
        raise ValueError(f"{label} too short")


def validate_core(core: dict, reader: dict) -> None:
    if not isinstance(core, dict):
        raise ValueError("Decision Core must be an object")
    if COMPRESSION_FIELD not in core or ROLE_FIELD not in core:
        raise ValueError("v0.5.2 requires candidate_compression and role_assignment")

    base = {k: v for k, v in core.items() if k not in {COMPRESSION_FIELD, ROLE_FIELD}}
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

    role = core.get(ROLE_FIELD)
    if not isinstance(role, dict) or set(role) != ROLE_FIELDS:
        raise ValueError(f"{venue}{race_no}R: role_assignment fields mismatch")
    honmei = role.get("honmei_horse_no")
    second = role.get("second_horse_no")
    if (
        not isinstance(honmei, int)
        or isinstance(honmei, bool)
        or not isinstance(second, int)
        or isinstance(second, bool)
        or honmei == second
        or honmei not in ordinary
        or second not in ordinary
    ):
        raise ValueError(f"{venue}{race_no}R: ◎/○ must be two distinct ordinary-five horses")
    if marks[0] != honmei or marks[1] != second:
        raise ValueError(f"{venue}{race_no}R: final ◎/○ must equal audited role_assignment")
    if role.get("honmei_selection_mode") != HONMEI_MODE:
        raise ValueError(f"{venue}{race_no}R: invalid honmei_selection_mode")
    if role.get("shot_selection_mode") != SHOT_MODE:
        raise ValueError(f"{venue}{race_no}R: invalid shot_selection_mode")
    _text(role.get("honmei_win_case"), 16, f"{venue}{race_no}R ◎ win case")
    _text(role.get("second_case"), 12, f"{venue}{race_no}R ○ case")
    _text(role.get("ranking_reason"), 20, f"{venue}{race_no}R ranking reason")

    challenger = review.get("external_challenger_horse_no")
    excluded = review.get("excluded_horse_no")
    decision = review.get("decision")
    if decision not in DECISIONS:
        raise ValueError(f"{venue}{race_no}R: invalid candidate_compression decision")
    _text(review.get("external_challenger_case"), 12, f"{venue}{race_no}R challenger case")
    _text(review.get("reason"), 16, f"{venue}{race_no}R compression reason")

    if len(roster) == 5:
        if decision != "NO_EXTERNAL_CHALLENGER" or challenger is not None or excluded is not None:
            raise ValueError(f"{venue}{race_no}R: five-runner field requires NO_EXTERNAL_CHALLENGER")
        if set(ordinary) != roster or set(marks) != set(ordinary):
            raise ValueError(f"{venue}{race_no}R: five-runner field must retain the full ordinary five")
        if marks[2] not in set(ordinary) - {honmei, second}:
            raise ValueError(f"{venue}{race_no}R: retained ▲ must be a non-anchor ordinary horse")
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
        if excluded in {honmei, second}:
            raise ValueError(f"{venue}{race_no}R: challenger cannot displace audited ◎/○")
        if marks[2] != challenger:
            raise ValueError(f"{venue}{race_no}R: admitted external challenger must be ▲")
    else:
        if excluded != challenger:
            raise ValueError(f"{venue}{race_no}R: KEEP_ORDINARY_FIVE must exclude the challenger")
        if set(marks) != set(ordinary):
            raise ValueError(f"{venue}{race_no}R: ordinary five must remain intact")
        if marks[2] not in set(ordinary) - {honmei, second}:
            raise ValueError(f"{venue}{race_no}R: retained ▲ must be a non-anchor ordinary horse")
