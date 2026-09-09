"""Lifecycle segmentation must follow the factor lifespan, not the condition lifespan."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import jrdb_edge_temporal_validator as validator  # noqa: E402
from test_jrdb_edge_temporal_validator import _candidate, _mart  # noqa: E402


def test_sire_lifecycle_starts_when_sire_anchor_first_appears(tmp_path: Path) -> None:
    mart = _mart(tmp_path)
    connection = sqlite3.connect(mart)
    try:
        # SireA exists from 2010, but the target condition is made to begin only in 2016.
        connection.execute(
            "UPDATE edge_runner_fact SET distance_m=1400 "
            "WHERE sire_name='SireA' AND distance_m=1600 AND race_date<'2016-01-01'"
        )
        connection.commit()
    finally:
        connection.close()

    policies = json.loads(
        (ROOT / "config/jrdb_edge_validation_policies_v0_1.json").read_text(encoding="utf-8")
    )
    candidate = _candidate("LIFECYCLE_SIRE_V1")
    candidate["first_observed_date"] = "2016-01-01"
    result = validator.validate_candidate(mart, candidate, policies)

    assert result["overall"]["first_date"] >= "2016-01-01"
    assert result["overall"]["baseline_first_date"] < "2016-01-01"
    # The lifecycle clock is anchored to SireA's history, so retained evidence can
    # come from a segment whose boundary itself starts before the condition appeared.
    assert result["slices"]
    assert result["slices"][0]["period_start"] < "2016-01-01"
