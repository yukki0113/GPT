"""Tests for deterministic, baseline-relative Edge candidate discovery."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import jrdb_edge_discovery as discovery  # noqa: E402


def _mart(tmp_path: Path) -> Path:
    path = tmp_path / "mart.sqlite"
    c = sqlite3.connect(path)
    c.execute(
        """CREATE TABLE edge_runner_fact(
          race_key TEXT, horse_no INTEGER, race_date TEXT, venue_code TEXT, distance_m INTEGER,
          surface_code TEXT, turn_code TEXT, frame_zone TEXT, horse_id TEXT,
          sire_name TEXT, sire_line_code TEXT, broodmare_sire_name TEXT, broodmare_sire_line_code TEXT,
          jockey_code TEXT, trainer_code TEXT, distance_change_bucket TEXT,
          surface_transition TEXT, frame_transition TEXT, prev1_race_date TEXT,
          label_win_hit INTEGER, label_place_hit INTEGER, label_win_payout INTEGER,
          label_place_payout INTEGER, calculation_status TEXT
        )"""
    )
    rows = [
        ("R1",1,"2024-01-01","06",1600,"1","1","INNER","H1","SireA","1206",None,None,"J1","T1","EXTEND","1->1","INNER->INNER","2023-12-01",1,1,500,180,"ELIGIBLE"),
        ("R2",2,"2024-02-01","06",1600,"1","1","OUTER","H2","SireA","1206",None,None,"J2","T2","EXTEND","1->1","INNER->OUTER","2024-01-01",0,1,0,140,"ELIGIBLE"),
        ("R3",3,"2024-03-01","05",1800,"1","2","MIDDLE","H3","SireA","1206",None,None,"J3","T3","SAME_BAND","1->1","MIDDLE->MIDDLE","2024-02-01",0,0,0,0,"ELIGIBLE"),
        ("R4",4,"2024-04-01","05",1800,"1","2","MIDDLE","H4","SireA","1206",None,None,"J4","T4","SAME_BAND","1->1","MIDDLE->MIDDLE","2024-03-01",0,0,0,0,"ELIGIBLE"),
    ]
    c.executemany("INSERT INTO edge_runner_fact VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    c.commit(); c.close()
    return path


def _catalog() -> dict:
    return {
        "schema_version": "0.1",
        "template_version": "test.v1",
        "rules": {"max_modifier_count": 2},
        "templates": [
            {
                "template_id": "SIRE_TURN_DISTANCE_TEST",
                "family": "PEDIGREE",
                "anchor_type": "sire",
                "anchor_fields": ["sire_name"],
                "modifier_fields": ["turn_code", "distance_m"],
                "baseline": "same_anchor",
                "enabled": True,
            }
        ],
    }


def _policies() -> dict:
    return {
        "schema_version": "0.1",
        "policy_version": "test.v1",
        "policies": {
            "LIFECYCLE_SIRE_V1": {
                "validation_class": "LIFECYCLE", "min_total_n": 120,
                "mature_min_active_days": 730, "review_days": 180, "expiry_days": 730
            },
            "EMERGING_SIRE_V1": {
                "validation_class": "EMERGING", "watch_min_n": 2,
                "provisional_min_n": 2, "eligible_min_n": 3,
                "review_days": 30, "expiry_days": 45
            }
        }
    }


def test_discovery_uses_anchor_baseline_and_does_not_activate(tmp_path: Path) -> None:
    rows = discovery.discover(
        _mart(tmp_path), template_catalog=_catalog(), policy_catalog=_policies(), as_of_date="2024-04-01"
    )
    assert len(rows) == 2
    right_mile = next(row for row in rows if row["modifiers"] == {"turn_code": "1", "distance_m": 1600})
    assert right_mile["sample_n"] == 2
    assert right_mile["baseline_sample_n"] == 4
    assert right_mile["place_rate"] == 1.0
    assert right_mile["baseline_place_rate"] == 0.5
    assert right_mile["performance_lift"] == 2.0
    assert right_mile["place_roi"] == 1.6
    assert right_mile["initial_stage"] == "PROVISIONAL"
    assert right_mile["promotion_status"] == "NOT_VALIDATED"
    assert right_mile["validation_class"] == "EMERGING"


def test_candidate_id_is_deterministic(tmp_path: Path) -> None:
    kwargs = dict(template_catalog=_catalog(), policy_catalog=_policies(), as_of_date="2024-04-01")
    first = discovery.discover(_mart(tmp_path), **kwargs)
    second = discovery.discover(tmp_path / "mart.sqlite", **kwargs)
    assert [r["candidate_id"] for r in first] == [r["candidate_id"] for r in second]
