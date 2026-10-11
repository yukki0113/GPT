#!/usr/bin/env python3
"""RaceNote v0.5.3 Decision Core validator.

v0.5.3 preserves the v0.5.2 protected ordinary-five / win-first / asymmetric
challenger contract and tightens the semantic meaning of the final boundary
comparison. It intentionally does not score racing evidence.
"""
from __future__ import annotations

from racenote_decision_core_v052 import (
    COMPRESSION_FIELD,
    DECISIONS,
    HONMEI_MODE,
    ROLE_FIELD,
    SHOT_MODE,
    validate_core as validate_v052_core,
)

LOGIC = "RaceNote-Human-Context-Reader-0.5.3-candidate"
VERSION = "racenote-decision-core-0.5.3"


def validate_core(core: dict, reader: dict) -> None:
    validate_v052_core(core, reader)

    race = reader["race"]
    venue = str(race["venue"])
    race_no = int(race["race_no"])
    review = core[COMPRESSION_FIELD]
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
