"""Regression tests for leakage-safe JRDB Edge current facts."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from build_jrdb_edge_current_facts import (  # noqa: E402
    CurrentFactError,
    build_runner_fact,
    lookup_previous_fact,
    select_profile_asof,
)


def _analysis(*rows) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """CREATE TABLE fact_entry_result_lite(
            race_key TEXT, race_date TEXT, horse_no INTEGER, horse_id TEXT,
            track_type TEXT, distance INTEGER, frame_no INTEGER
        )"""
    )
    if rows:
        connection.executemany(
            "INSERT INTO fact_entry_result_lite VALUES(?,?,?,?,?,?,?)", rows
        )
    return connection


def test_profile_asof_uses_latest_non_future_snapshot():
    status, profile = select_profile_asof(
        [
            {"data_date": "20260901", "sire_line_code": "1001"},
            {"data_date": "20260908", "sire_line_code": "1002"},
            {"data_date": "20260910", "sire_line_code": "9999"},
        ],
        "2026-09-09",
    )
    assert status == "MATCHED"
    assert profile is not None
    assert profile["sire_line_code"] == "1002"


def test_profile_asof_never_uses_future_only_snapshot():
    status, profile = select_profile_asof(
        [{"data_date": "20260910", "sire_line_code": "9999"}],
        "2026-09-09",
    )
    assert (status, profile) == ("MISSING_ASOF", None)


def test_previous_lookup_uses_exact_kyi_link_without_fallback():
    connection = _analysis(
        ("09010101", "2026-08-20", 3, "H0000001", "1", 1800, 5),
        ("09010201", "2026-08-30", 3, "H0000001", "2", 1400, 1),
    )
    status, previous = lookup_previous_fact(
        connection,
        prev_race_key="09010101",
        horse_id="H0000001",
        target_date="2026-09-09",
    )
    assert status == "RESOLVED"
    assert previous == {
        "race_date": "2026-08-20",
        "surface_code": "1",
        "distance_m": 1800,
        "frame_no": 5,
    }

    status, previous = lookup_previous_fact(
        connection,
        prev_race_key="09019999",
        horse_id="H0000001",
        target_date="2026-09-09",
    )
    assert (status, previous) == ("LINK_NOT_RESOLVED", None)


def test_previous_lookup_rejects_same_day_or_future_row():
    connection = _analysis(
        ("09010101", "2026-09-09", 3, "H0000001", "1", 1800, 5),
    )
    with pytest.raises(CurrentFactError, match="strictly prior"):
        lookup_previous_fact(
            connection,
            prev_race_key="09010101",
            horse_id="H0000001",
            target_date="2026-09-09",
        )


def test_runner_fact_uses_canonical_transitions_and_degrades_without_history():
    race = {
        "race_date": "2026-09-09",
        "race_key": "0926a101",
        "venue_code": "09",
        "race_no": 1,
        "distance_m": 1600,
        "surface_code": "1",
        "turn_code": "2",
    }
    entry = {
        "race_horse_key": "0926a10103",
        "horse_no": 3,
        "horse_id": "H0000001",
        "horse_name": "TEST HORSE",
        "frame_no": 2,
        "jockey_code": "01234",
        "trainer_code": "05678",
        "prev1_race_key": "09010101",
    }
    previous = {
        "race_date": "2026-08-20",
        "distance_m": 2000,
        "surface_code": "2",
        "frame_no": 5,
    }
    fact = build_runner_fact(
        race,
        entry,
        {"data_date": "20260908", "sire_line_code": "1001"},
        previous,
        profile_status="MATCHED",
        previous_status="RESOLVED",
    )
    assert fact["frame_zone"] == "INNER"
    assert fact["distance_change_m"] == -400
    assert fact["distance_change_bucket"] == "LARGE_SHORTEN"
    assert fact["surface_transition"] == "2->1"
    assert fact["frame_transition"] == "MIDDLE->INNER"
    assert fact["profile_asof_date"] == "2026-09-08"
    assert fact["source_availability_class"] == "PRE_RACE"

    degraded = build_runner_fact(
        race,
        {**entry, "frame_no": 8},
        None,
        None,
        profile_status="MISSING_ASOF",
        previous_status="NO_HISTORY_SOURCE",
    )
    assert degraded["frame_zone"] == "OUTER"
    assert degraded["distance_m"] == 1600
    assert degraded["distance_change_bucket"] is None
    assert degraded["surface_transition"] is None
    assert degraded["frame_transition"] is None
