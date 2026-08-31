from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "build_jrdb_runperf_features.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema" / "jrdb_runperf_schema_v0_1.sql"
SPEC = importlib.util.spec_from_file_location("runperf_builder", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _make_source(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE race_context(
              race_key TEXT PRIMARY KEY,
              race_date TEXT NOT NULL,
              year INTEGER NOT NULL,
              venue_code TEXT NOT NULL,
              surface_code TEXT,
              distance_m INTEGER,
              race_type_code TEXT,
              race_condition_code TEXT,
              grade_code TEXT,
              availability_class TEXT NOT NULL
            );
            CREATE TABLE runner_pre(
              race_key TEXT NOT NULL,
              horse_no INTEGER NOT NULL,
              carried_weight_kg REAL,
              PRIMARY KEY(race_key,horse_no)
            );
            CREATE TABLE runner_result(
              race_key TEXT NOT NULL,
              horse_no INTEGER NOT NULL,
              horse_id TEXT,
              finish INTEGER,
              abnormal_code TEXT,
              time_sec REAL,
              raw_score REAL,
              idm REAL,
              PRIMARY KEY(race_key,horse_no)
            );
            """
        )
        races = [
            ("R1", "2010-01-01", 2010, "01", "1", 1600, "14", "A3", "", "PRE_RACE"),
            ("R2", "2010-01-02", 2010, "01", "1", 1600, "14", "A3", "", "PRE_RACE"),
            ("R3", "2010-01-03", 2010, "01", "1", 1600, "14", "A3", "", "PRE_RACE"),
            ("R4", "2010-01-03", 2010, "01", "1", 1600, "14", "A3", "", "PRE_RACE"),
            ("R5", "2013-01-04", 2013, "01", "1", 1600, "14", "A3", "", "PRE_RACE"),
        ]
        connection.executemany("INSERT INTO race_context VALUES (?,?,?,?,?,?,?,?,?,?)", races)
        times = {
            "R1": [100.0, 101.0, 102.0, 103.0],
            "R2": [101.0, 102.0, 103.0, 104.0],
            "R3": [102.0, 103.0, 104.0, 105.0],
            "R4": [110.0, 111.0, 112.0, 113.0],
            "R5": [99.0, 100.0, 101.0, 102.0],
        }
        for race_key, values in times.items():
            for index, time_sec in enumerate(values, start=1):
                connection.execute("INSERT INTO runner_pre VALUES (?,?,?)", (race_key, index, 55.0 + index))
                connection.execute(
                    "INSERT INTO runner_result VALUES (?,?,?,?,?,?,?,?)",
                    (race_key, index, f"H{index}", index, "0", time_sec, 50 + index, 60 + index),
                )
        connection.commit()
    finally:
        connection.close()


def _build(tmp_path: Path, methods: tuple[str, ...]) -> Path:
    source = tmp_path / "index.sqlite"
    output = tmp_path / "runperf.sqlite"
    _make_source(source)
    MODULE.build(source, output, SCHEMA_PATH, methods)
    return output


def test_expected_time_is_strictly_past_only_and_same_day_isolated(tmp_path: Path) -> None:
    output = _build(tmp_path, ("EXPANDING",))
    connection = sqlite3.connect(output)
    connection.row_factory = sqlite3.Row
    try:
        r3 = connection.execute(
            "SELECT * FROM race_expected_time WHERE baseline_method='EXPANDING' AND race_key='R3'"
        ).fetchone()
        r4 = connection.execute(
            "SELECT * FROM race_expected_time WHERE baseline_method='EXPANDING' AND race_key='R4'"
        ).fetchone()
        assert r3 is not None and r4 is not None
        assert r3["course_history_last_date"] == "2010-01-02"
        assert r4["course_history_last_date"] == "2010-01-02"
        assert r3["course_base_time_sec"] == r4["course_base_time_sec"]
        assert r3["class_adjustment_sec"] == r4["class_adjustment_sec"]
        assert r3["expected_time_sec"] == r4["expected_time_sec"]
    finally:
        connection.close()


def test_runperf_components_and_track_bias_are_arithmetically_consistent(tmp_path: Path) -> None:
    output = _build(tmp_path, ("EXPANDING",))
    connection = sqlite3.connect(output)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM runner_runperf_features WHERE baseline_method='EXPANDING' AND race_key='R3' AND horse_no=1"
        ).fetchone()
        assert row is not None
        assert row["margin_sec"] == 0.0
        assert row["finish_percentile"] == 1.0
        assert row["weight_relative_kg"] == -1.5
        assert row["expected_time_sec"] is not None
        assert row["day_bias_raw_sec"] is not None
        expected = row["expected_time_sec"] - (row["actual_time_sec"] - row["day_bias_raw_sec"])
        assert abs(row["time_residual_raw_bias_sec"] - expected) < 1e-9
    finally:
        connection.close()


def test_rolling_two_year_window_expires_old_course_history(tmp_path: Path) -> None:
    output = _build(tmp_path, ("ROLLING_2Y",))
    connection = sqlite3.connect(output)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM race_expected_time WHERE baseline_method='ROLLING_2Y' AND race_key='R5'"
        ).fetchone()
        assert row is not None
        assert row["course_history_count"] == 0
        assert row["course_base_time_sec"] is None
        assert row["calculation_status"] == "MISSING_COURSE_HISTORY"
    finally:
        connection.close()


def test_abnormal_runner_is_kept_but_excluded(tmp_path: Path) -> None:
    source = tmp_path / "index.sqlite"
    output = tmp_path / "runperf.sqlite"
    _make_source(source)
    connection = sqlite3.connect(source)
    try:
        connection.execute("UPDATE runner_result SET abnormal_code='4' WHERE race_key='R3' AND horse_no=4")
        connection.commit()
    finally:
        connection.close()
    MODULE.build(source, output, SCHEMA_PATH, ("EXPANDING",))
    connection = sqlite3.connect(output)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute("SELECT * FROM runner_runperf_features WHERE race_key='R3' AND horse_no=4").fetchone()
        assert row is not None
        assert row["calculation_status"] == "EXCLUDED_ABNORMAL"
        assert row["finish_percentile"] is None
        assert row["margin_sec"] is None
    finally:
        connection.close()
