"""Regression tests for frozen official RunPerf v0.1 materialization."""
from __future__ import annotations

import importlib.util
import math
import sqlite3
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))
BUILD_PATH = SRC_DIR / "build_jrdb_runperf_features.py"
OFFICIAL_PATH = SRC_DIR / "build_jrdb_official_runperf.py"
FIXTURE_PATH = Path(__file__).with_name("test_build_jrdb_runperf_features.py")
RUNPERF_SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "jrdb_runperf_schema_v0_1.sql"
OFFICIAL_SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "jrdb_official_runperf_schema_v0_1.sql"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FEATURES = _load("official_runperf_features_test", BUILD_PATH)
OFFICIAL = _load("official_runperf_builder_test", OFFICIAL_PATH)
FIXTURE = _load("official_runperf_fixture", FIXTURE_PATH)


def _candidate_db(tmp_path: Path, abnormal: bool = False) -> Path:
    index_path = tmp_path / "index.sqlite"
    runperf_path = tmp_path / "runperf.sqlite"
    FIXTURE._make_source(index_path)
    if abnormal:
        connection = sqlite3.connect(index_path)
        try:
            connection.execute("UPDATE runner_result SET abnormal_code='4' WHERE race_key='R3' AND horse_no=4")
            connection.commit()
        finally:
            connection.close()
    FEATURES.build(index_path, runperf_path, RUNPERF_SCHEMA, ("EXPANDING",))
    return runperf_path


def _official_db(tmp_path: Path, abnormal: bool = False) -> tuple[Path, Path]:
    candidate = _candidate_db(tmp_path, abnormal)
    official = tmp_path / "official.sqlite"
    OFFICIAL.build(candidate, official, OFFICIAL_SCHEMA)
    return candidate, official


def test_annual_snapshot_scores_normal_rows_and_preserves_arithmetic(tmp_path: Path) -> None:
    _, official = _official_db(tmp_path)
    connection = sqlite3.connect(official)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM official_runperf WHERE race_key='R5' AND horse_no=1"
        ).fetchone()
        assert row is not None
        assert row["year"] == 2013
        assert row["score_status"] == "OK"
        assert row["coefficient_snapshot_target_year"] == 2013
        assert row["coefficient_asof_through_year"] == 2012
        assert row["score_provenance"] == "ANNUAL_ASOF_LITERAL_NEXT_START"
        expected = (
            row["coefficient_intercept"]
            + row["coefficient_beta_time"] * row["time_raw_bias_sec"]
            + row["coefficient_beta_margin"] * row["margin_score"]
        )
        assert math.isclose(row["runperf_raw"], expected, rel_tol=0.0, abs_tol=1.0e-12)
    finally:
        connection.close()


def test_warmup_rows_use_only_permitted_2013_retrospective_snapshot(tmp_path: Path) -> None:
    _, official = _official_db(tmp_path)
    connection = sqlite3.connect(official)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM official_runperf WHERE race_key='R3' AND horse_no=1"
        ).fetchone()
        assert row is not None
        assert row["year"] == 2010
        assert row["score_status"] == "OK"
        assert row["coefficient_snapshot_target_year"] == 2013
        assert row["coefficient_asof_through_year"] == 2012
        assert row["score_provenance"] == "WARMUP_RETROSPECTIVE_2013_SNAPSHOT"
    finally:
        connection.close()


def test_excluded_source_row_is_retained_without_zero_imputation(tmp_path: Path) -> None:
    _, official = _official_db(tmp_path, abnormal=True)
    connection = sqlite3.connect(official)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM official_runperf WHERE race_key='R3' AND horse_no=4"
        ).fetchone()
        assert row is not None
        assert row["source_calculation_status"] == "EXCLUDED_ABNORMAL"
        assert row["score_status"] == "EXCLUDED_SOURCE_CALCULATION_STATUS"
        assert row["runperf_raw"] is None
        assert row["coefficient_snapshot_target_year"] is None
    finally:
        connection.close()


def test_nonfinite_snapshot_fails_closed(tmp_path: Path, monkeypatch) -> None:
    candidate = _candidate_db(tmp_path)
    output = tmp_path / "official.sqlite"
    original = OFFICIAL.fit_snapshot

    def invalid_snapshot(*args, **kwargs):
        snapshot = original(*args, **kwargs)
        snapshot["coefficients"]["time_raw_bias"] = float("nan")
        return snapshot

    monkeypatch.setattr(OFFICIAL, "fit_snapshot", invalid_snapshot)
    try:
        OFFICIAL.build(candidate, output, OFFICIAL_SCHEMA)
    except ValueError as exc:
        assert "non-finite" in str(exc)
    else:
        raise AssertionError("non-finite snapshot must fail closed")


def test_output_does_not_materialize_market_columns(tmp_path: Path) -> None:
    _, official = _official_db(tmp_path)
    connection = sqlite3.connect(official)
    try:
        columns = {row[1].lower() for row in connection.execute("PRAGMA table_info(official_runperf)")}
        assert all("odds" not in column and "popularity" not in column for column in columns)
    finally:
        connection.close()
