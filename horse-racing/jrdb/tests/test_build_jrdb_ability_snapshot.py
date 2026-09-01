"""Regression coverage for leakage-safe Ability pre-race snapshots."""
from __future__ import annotations

import importlib.util
import math
import sqlite3
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
SCHEMA = Path(__file__).resolve().parents[1] / "schema/jrdb_ability_snapshot_schema_v0_1.sql"
OFFICIAL_TEST = Path(__file__).with_name("test_build_jrdb_official_runperf.py")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


BUILDER = _load("ability_builder", SRC / "build_jrdb_ability_snapshot.py")
AUDIT = _load("ability_audit", SRC / "audit_jrdb_ability_snapshot.py")
OFFICIAL = _load("ability_official_fixture", OFFICIAL_TEST)


def _snapshot(tmp_path: Path) -> Path:
    candidate, official = OFFICIAL._official_db(tmp_path)
    index = tmp_path / "index.sqlite"
    connection = sqlite3.connect(index)
    try:
        connection.execute("ALTER TABLE runner_pre ADD COLUMN horse_id TEXT")
        connection.execute("ALTER TABLE runner_pre ADD COLUMN jockey_code TEXT")
        connection.execute("UPDATE runner_pre SET horse_id='H' || horse_no, jockey_code='J' || (horse_no % 2)")
        connection.commit()
    finally:
        connection.close()
    # The existing fixture's candidate provenance identifies its original Index Base path.
    # It is reproducible here because the helper always creates this name.
    out = tmp_path / "ability.sqlite"
    BUILDER.build(index, official, out, SCHEMA)
    return out


def test_strict_prior_history_same_day_exclusion_and_debut_retention(tmp_path: Path) -> None:
    path = _snapshot(tmp_path)
    connection = sqlite3.connect(path); connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute("""SELECT t.*,f.* FROM ability_target_runner t
          JOIN ability_feature_snapshot f USING(race_key,horse_no) ORDER BY t.race_date,t.race_key,t.horse_no""").fetchall()
        assert rows
        assert all(row["recent_history_max_date"] is None or row["recent_history_max_date"] < row["race_date"] for row in rows)
        debut = [row for row in rows if row["is_debut"] == 1]
        assert debut and all(row["recent_perf_d090"] is None and row["recent_perf_d090_missing"] == 1 for row in debut)
    finally: connection.close()


def test_candidates_aptitude_going_jockey_and_weight_contracts(tmp_path: Path) -> None:
    path = _snapshot(tmp_path)
    connection = sqlite3.connect(path); connection.row_factory = sqlite3.Row
    try:
        row = connection.execute("""SELECT t.*,f.* FROM ability_target_runner t JOIN ability_feature_snapshot f USING(race_key,horse_no)
          WHERE f.career_scored_run_count>0 LIMIT 1""").fetchone()
        assert row is not None
        assert row["recent_perf_d070_n"] <= 5 and row["recent_perf_d070_neff"] <= row["recent_perf_d070_n"]
        assert row["distance_d200_n"] <= 12 and row["distance_d200_neff"] <= row["distance_d200_n"]
        assert row["going_same_mean_raw"] is None and row["going_fit_missing"] == 1
        assert row["going_target_availability"] == BUILDER.GOING_AVAILABILITY
        assert row["race_valid_weight_count"] >= 0
        if row["weight_relative"] is not None:
            assert math.isclose(row["weight_relative"],row["current_carried_weight"]-row["race_mean_carried_weight"],abs_tol=1e-12)
        assert row["jockey_residual_n"] >= 0
    finally: connection.close()


def test_audit_fails_closed_for_duplicate_market_and_nonfinite(tmp_path: Path) -> None:
    path = _snapshot(tmp_path)
    assert AUDIT.audit(path)["status"] == "PASS"
    connection = sqlite3.connect(path)
    try:
        connection.execute("ALTER TABLE ability_feature_snapshot ADD COLUMN market_probe REAL")
        connection.commit()
    finally: connection.close()
    report = AUDIT.audit(path)
    assert report["status"] == "FAIL" and report["violations"]["market_columns"] == 1
    connection = sqlite3.connect(path)
    try:
        connection.execute("UPDATE ability_feature_snapshot SET recent_perf_d070=?", (float("inf"),))
        connection.commit()
    finally: connection.close()
    assert AUDIT.audit(path)["violations"]["nonfinite_feature_values"] > 0
