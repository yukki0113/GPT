#!/usr/bin/env python3
"""RaceNote v0.5.3 Decision Core validator.

v0.5.3 rebuild r2 keeps the promoted v0.5.2 protected ordinary-five /
win-first / asymmetric-challenger contract and narrows the additional change
to one boundary-safety invariant.

Legacy pre-rebuild v0.5.3 sessions have no contract_revision and remain
verifiable under their original structural semantics. New sessions use
CONTRACT_REVISION and enforce the rebuilt deterministic boundary identity.
The validator intentionally does not score racing evidence.
"""
from __future__ import annotations

from racenote_decision_core_v052 import (
    COMPRESSION_FIELD,
    HONMEI_MODE,
    ROLE_FIELD,
    SHOT_MODE,
    validate_core as validate_v052_core,
)

LOGIC = "RaceNote-Human-Context-Reader-0.5.3-candidate"
VERSION = "racenote-decision-core-0.5.3"
CONTRACT_REVISION = "v053-boundary-safety-r2"


def _rebuilt_boundary_horse(ordinary: list[int], honmei: int, second: int) -> int:
    """Return the lowest ordinary-ranked non-anchor horse.

    r2 does not search the ordinary five for a convenient horse to remove.
    The external challenger may challenge only this pre-existing boundary.
    """
    for horse_no in reversed(ordinary):
        if horse_no not in {honmei, second}:
            return horse_no
    raise ValueError("ordinary five has no non-anchor boundary horse")


def validate_core(
    core: dict,
    reader: dict,
    *,
    contract_revision: str | None = None,
) -> None:
    if contract_revision not in {None, CONTRACT_REVISION}:
        raise ValueError(f"unsupported v0.5.3 contract revision: {contract_revision}")

    validate_v052_core(core, reader)

    race = reader["race"]
    venue = str(race["venue"])
    race_no = int(race["race_no"])
    review = core[COMPRESSION_FIELD]
    role = core[ROLE_FIELD]
    boundary = core.get("boundary_review")
    if not isinstance(boundary, dict):
        raise ValueError(f"{venue}{race_no}R: boundary_review must be an object")

    alternative = boundary.get("alternative_horse_no")
    challenger = review.get("external_challenger_horse_no")
    excluded = review.get("excluded_horse_no")
    decision = review.get("decision")

    if decision == "ADMIT_CHALLENGER":
        if alternative != excluded:
            raise ValueError(
                f"{venue}{race_no}R: v0.5.3 ADMIT boundary must review the displaced ordinary horse"
            )
        if contract_revision == CONTRACT_REVISION:
            expected = _rebuilt_boundary_horse(
                review["ordinary_five"],
                role["honmei_horse_no"],
                role["second_horse_no"],
            )
            if excluded != expected:
                raise ValueError(
                    f"{venue}{race_no}R: rebuilt v0.5.3 ADMIT must displace "
                    f"the lowest-ranked non-anchor ordinary horse {expected}"
                )
    elif decision == "KEEP_ORDINARY_FIVE":
        if alternative != challenger:
            raise ValueError(
                f"{venue}{race_no}R: v0.5.3 KEEP boundary must review the external challenger"
            )
    elif decision == "NO_EXTERNAL_CHALLENGER":
        if alternative is not None:
            raise ValueError(
                f"{venue}{race_no}R: v0.5.3 five-runner boundary alternative must be null"
            )
