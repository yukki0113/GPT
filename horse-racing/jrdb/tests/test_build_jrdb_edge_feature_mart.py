"""Leakage and transition tests for the Edge Feature Mart builder."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import build_jrdb_edge_feature_mart as builder  # noqa: E402


def _source(tmp_path: Path) -> Path:
    path = tmp_path / "index.sqlite"
    c = sqlite3.connect(path)
    c.executescript(
        """
        CREATE TABLE race_context(
          race_key TEXT PRIMARY KEY,race_date TEXT,venue_code TEXT,race_no INTEGER,distance_m INTEGER,
          surface_code TEXT,turn_code TEXT,inner_outer_code TEXT,race_condition_code TEXT,grade_code TEXT,
          declared_field_size INTEGER,availability_class TEXT
        );
        CREATE TABLE runner_pre(
          race_key TEXT,horse_no INTEGER,frame_no INTEGER,horse_id TEXT,horse_name TEXT,sex_code TEXT,
          jockey_code TEXT,jockey_name TEXT,trainer_code TEXT,trainer_name TEXT,carried_weight_kg REAL,
          running_style_code TEXT,rotation_interval INTEGER,condition_class_code TEXT,
          PRIMARY KEY(race_key,horse_no)
        );
        CREATE TABLE runner_previous_link(
          race_key TEXT,horse_no INTEGER,sequence INTEGER,prev_result_key TEXT,prev_race_key TEXT,
          PRIMARY KEY(race_key,horse_no,sequence)
        );
        CREATE TABLE runner_result(
          race_key TEXT,horse_no INTEGER,result_key TEXT UNIQUE,finish INTEGER,abnormal_code TEXT,
          win_payout INTEGER,place_payout INTEGER,final_win_odds REAL,final_win_popularity INTEGER,
          PRIMARY KEY(race_key,horse_no)
        );
        CREATE TABLE horse_profile_observation(
          horse_id TEXT,data_date TEXT,sire_name TEXT,sire_line_code TEXT,
          broodmare_sire_name TEXT,broodmare_sire_line_code TEXT
        );
        """
    )
    c.execute("INSERT INTO race_context VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("RPREV", "2026-08-01", "05", 1, 1400, "2", "1", "1", "A3", "", 12, "PRE_RACE"))
    c.execute("INSERT INTO race_context VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("RCURR", "2026-09-01", "06", 2, 1600, "2", "2", "1", "A3", "", 12, "PRE_RACE"))
    c.execute("INSERT INTO runner_pre VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("RPREV", 3, 2, "H1", "Horse", "1", "J1", "J", "T1", "T", 55.0, "2", 3, "0"))
    c.execute("INSERT INTO runner_pre VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("RCURR", 3, 8, "H1", "Horse", "1", "J1", "J", "T1", "T", 55.0, "2", 3, "0"))
    c.execute("INSERT INTO runner_previous_link VALUES (?,?,?,?,?)", ("RCURR", 3, 1, "H120260801", "RPREV"))
    c.execute("INSERT INTO runner_result VALUES (?,?,?,?,?,?,?,?,?)", ("RPREV", 3, "H120260801", 2, "0", 0, 160, 4.5, 2))
    c.execute("INSERT INTO runner_result VALUES (?,?,?,?,?,?,?,?,?)", ("RCURR", 3, "H120260901", 1, "0", 850, 250, 8.5, 5))
    c.execute("INSERT INTO horse_profile_observation VALUES (?,?,?,?,?,?)", ("H1", "2026-08-15", "SireA", "1206", "DamSireA", "1503"))
    c.execute("INSERT INTO horse_profile_observation VALUES (?,?,?,?,?,?)", ("H1", "2026-09-10", "LEAK", "9999", "LEAK", "9999"))
    c.commit(); c.close()
    return path


def test_build_uses_only_asof_profile_and_strict_prior_run(tmp_path: Path) -> None:
    source = _source(tmp_path)
    output = tmp_path / "edge.sqlite"
    report = builder.build(source, output, ROOT / "schema/jrdb_edge_feature_mart_schema_v0_1.sql")
    assert report["status"] == "PASS"
    c = sqlite3.connect(output); c.row_factory = sqlite3.Row
    try:
        row = c.execute("SELECT * FROM edge_runner_fact WHERE race_key='RCURR' AND horse_no=3").fetchone()
        assert row["sire_name"] == "SireA"
        assert row["profile_asof_date"] == "2026-08-15"
        assert row["prev1_race_date"] == "2026-08-01"
        assert row["distance_change_m"] == 200
        assert row["distance_change_bucket"] == "EXTEND"
        assert row["frame_transition"] == "INNER->OUTER"
        assert row["label_win_hit"] == 1 and row["label_place_hit"] == 1
        assert row["calculation_status"] == "ELIGIBLE"
    finally:
        c.close()


def test_current_result_fallback_is_not_pre_race_eligible(tmp_path: Path) -> None:
    source = _source(tmp_path)
    c = sqlite3.connect(source)
    c.execute("UPDATE race_context SET availability_class='CURRENT_RESULT_FALLBACK' WHERE race_key='RCURR'")
    c.commit(); c.close()
    output = tmp_path / "edge.sqlite"
    builder.build(source, output, ROOT / "schema/jrdb_edge_feature_mart_schema_v0_1.sql")
    c = sqlite3.connect(output); c.row_factory = sqlite3.Row
    try:
        row = c.execute("SELECT * FROM edge_runner_fact WHERE race_key='RCURR'").fetchone()
        assert row["is_pre_race_eligible"] == 0
        assert row["calculation_status"] == "SOURCE_NOT_PRE_RACE"
    finally:
        c.close()
