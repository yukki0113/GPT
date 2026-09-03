"""Smoke/regression tests for official Existing-Horse Ability v0.1 materialization."""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
BUILDER_PATH = SRC / "build_jrdb_official_existing_ability.py"
ABILITY_SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "jrdb_ability_snapshot_schema_v0_1.sql"
OFFICIAL_SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "jrdb_official_existing_ability_schema_v0_1.sql"


def _load(name: str, path: Path):
    """Load one repository module directly from path."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = _load("official_existing_ability_builder", BUILDER_PATH)


def _insert_snapshot_row(
    connection: sqlite3.Connection,
    *,
    race_date: str,
    race_key: str,
    horse_no: int,
    horse_id: str,
    year: int,
    career_count: int,
    recent: float | None,
    target_status: str | None,
    target_runperf: float | None,
) -> None:
    """Insert one compact but contract-complete Ability snapshot row."""
    connection.execute(
        """
        INSERT INTO ability_target_runner(
          race_date,race_key,horse_no,horse_id,year,venue_code,surface_code,distance_m,
          jockey_code,race_context_availability,current_carried_weight,race_mean_carried_weight,
          race_valid_weight_count,weight_relative,weight_relative_missing,as_of_exclusive,
          feature_builder_version,formula_version,source_snapshot,calculated_at,validation_status
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            race_date,race_key,horse_no,horse_id,year,"01","1",1600,"J1","PRE_RACE",
            55.0,55.0,2,0.0,0,race_date,"fixture","fixture","fixture","2026-09-03T00:00:00Z","OK",
        ),
    )

    missing = 1 if recent is None else 0
    n = 0 if recent is None else min(career_count, 5)
    neff = None if recent is None else float(max(1, n))
    peak1 = None if recent is None else recent + 0.10
    peak2 = None if recent is None else recent + 0.05
    mad = None if career_count < 3 else 0.08
    mad_n = 0 if mad is None else min(career_count, 5)
    mad_missing = 1 if mad is None else 0
    aptitude_n = 0 if career_count == 0 else min(career_count, 12)
    aptitude_neff = None if aptitude_n == 0 else float(aptitude_n)
    aptitude_missing = 1 if aptitude_n == 0 else 0
    aptitude_delta = None if aptitude_n == 0 else 0.03
    jockey_n = 0 if career_count == 0 else max(1, career_count)
    jockey_value = None if jockey_n == 0 else 0.02

    connection.execute(
        """
        INSERT INTO ability_feature_snapshot(
          race_key,horse_no,career_scored_run_count,recent_scored_run_count,last_scored_run_date,rest_days,is_debut,
          recent_perf_d070,recent_perf_d070_n,recent_perf_d070_neff,recent_perf_d070_missing,
          recent_perf_d080,recent_perf_d080_n,recent_perf_d080_neff,recent_perf_d080_missing,
          recent_perf_d090,recent_perf_d090_n,recent_perf_d090_neff,recent_perf_d090_missing,
          recent_perf_d100,recent_perf_d100_n,recent_perf_d100_neff,recent_perf_d100_missing,
          peak_best1_last5,peak_best2_mean_last5,
          performance_mad_last5,performance_mad_last5_n,performance_mad_last5_missing,
          surface_same_mean_raw,surface_overall_mean_raw,surface_fit_delta_raw,surface_fit_n,surface_fit_neff,surface_fit_missing,
          distance_d200_mean_raw,distance_d200_delta_raw,distance_d200_n,distance_d200_neff,distance_d200_missing,
          distance_d400_mean_raw,distance_d400_delta_raw,distance_d400_n,distance_d400_neff,distance_d400_missing,
          distance_d600_mean_raw,distance_d600_delta_raw,distance_d600_n,distance_d600_neff,distance_d600_missing,
          distance_d800_mean_raw,distance_d800_delta_raw,distance_d800_n,distance_d800_neff,distance_d800_missing,
          exact_distance_count,nearest_historical_distance_diff_m,
          course_exact_mean_raw,course_exact_delta_raw,course_exact_n,course_exact_neff,course_surface_backoff_mean_raw,course_fit_missing,
          going_same_mean_raw,going_same_n,going_fit_missing,going_target_availability,
          jockey_residual_mean_raw,jockey_residual_n,jockey_residual_last_date,jockey_residual_missing,
          recent_history_max_date,aptitude_history_max_date,jockey_history_max_date
        ) VALUES(
          ?,?,?,?,?,?,?,
          ?,?,?,?, ?,?,?,?, ?,?,?,?, ?,?,?,?,
          ?,?, ?,?,?,
          ?,?,?,?,?,?,
          ?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?,
          ?,?, ?,?,?,?,?,?,
          ?,?,?,?, ?,?,?,?, ?,?,?
        )
        """,
        (
            race_key,horse_no,career_count,min(career_count,5),"20121201" if career_count else None,30 if career_count else None,1 if career_count == 0 else 0,
            recent,n,neff,missing,recent,n,neff,missing,recent,n,neff,missing,recent,n,neff,missing,
            peak1,peak2,mad,mad_n,mad_missing,
            None if aptitude_n == 0 else recent, None if aptitude_n == 0 else recent - 0.03 if recent is not None else None, aptitude_delta, aptitude_n, aptitude_neff, aptitude_missing,
            None if aptitude_n == 0 else recent,aptitude_delta,aptitude_n,aptitude_neff,aptitude_missing,
            None if aptitude_n == 0 else recent,aptitude_delta,aptitude_n,aptitude_neff,aptitude_missing,
            None if aptitude_n == 0 else recent,aptitude_delta,aptitude_n,aptitude_neff,aptitude_missing,
            None if aptitude_n == 0 else recent,aptitude_delta,aptitude_n,aptitude_neff,aptitude_missing,
            aptitude_n,0 if aptitude_n else None,
            None if aptitude_n == 0 else recent,aptitude_delta,aptitude_n,aptitude_neff,None if aptitude_n == 0 else recent,aptitude_missing,
            None,0,1,"PRE_RACE_GOING_UNAVAILABLE",
            jockey_value,jockey_n,"20121201" if jockey_n else None,1 if jockey_n == 0 else 0,
            "20121201" if career_count else None,"20121201" if aptitude_n else None,"20121201" if jockey_n else None,
        ),
    )
    connection.execute(
        "INSERT INTO ability_current_result(race_key,horse_no,score_status,official_runperf_raw,score_provenance) VALUES(?,?,?,?,?)",
        (race_key,horse_no,target_status,target_runperf,"fixture" if target_status else None),
    )


def _source_snapshot(tmp_path: Path) -> Path:
    """Create a chronology-valid minimal snapshot with 2012 training and 2013 targets."""
    source = tmp_path / "ability.sqlite"
    connection = sqlite3.connect(source)
    try:
        connection.executescript(ABILITY_SCHEMA.read_text(encoding="utf-8"))

        # Warm-up row retained but not used for the 2013 model because it has no prior scored history.
        _insert_snapshot_row(
            connection,race_date="20101201",race_key="W2010",horse_no=1,horse_id="HW",
            year=2010,career_count=0,recent=None,target_status="OK",target_runperf=0.10,
        )

        # Four prior-year existing-horse labeled rows form the 2013 training cohort.
        for index, value in enumerate((0.15,0.30,0.45,0.60), start=1):
            _insert_snapshot_row(
                connection,race_date=f"2012120{index}",race_key=f"T2012{index}",horse_no=1,horse_id=f"H{index}",
                year=2012,career_count=index,recent=value,target_status="OK",target_runperf=value + 0.04,
            )

        # 2013 existing horses must score even when their target result is not yet available.
        _insert_snapshot_row(
            connection,race_date="20130105",race_key="R2013A",horse_no=1,horse_id="H1",
            year=2013,career_count=2,recent=0.28,target_status=None,target_runperf=None,
        )
        _insert_snapshot_row(
            connection,race_date="20130105",race_key="R2013A",horse_no=2,horse_id="H2",
            year=2013,career_count=3,recent=0.42,target_status=None,target_runperf=None,
        )
        # Debut/no-scored-history target remains explicitly unscored.
        _insert_snapshot_row(
            connection,race_date="20130105",race_key="R2013A",horse_no=3,horse_id="HD",
            year=2013,career_count=0,recent=None,target_status=None,target_runperf=None,
        )
        connection.commit()
    finally:
        connection.close()
    return source


def _materialized(tmp_path: Path) -> tuple[Path, Path]:
    """Build a small chronology-valid Ability snapshot and materialize the frozen model."""
    source = _source_snapshot(tmp_path)
    output = tmp_path / "official_existing_ability.sqlite"
    BUILDER.build(source, output, OFFICIAL_SCHEMA)
    return source, output


def test_materialization_reconciles_source_and_keeps_debut_unscored(tmp_path: Path) -> None:
    """All source targets remain present while debut/no-history rows remain explicitly unscored."""
    source, output = _materialized(tmp_path)
    source_connection = sqlite3.connect(source)
    output_connection = sqlite3.connect(output)
    try:
        source_count = source_connection.execute("SELECT COUNT(*) FROM ability_target_runner").fetchone()[0]
        output_count = output_connection.execute("SELECT COUNT(*) FROM official_existing_ability").fetchone()[0]
        assert output_count == source_count
        debut_count = output_connection.execute(
            "SELECT COUNT(*) FROM official_existing_ability WHERE score_status='DEBUT_MODEL_PENDING'"
        ).fetchone()[0]
        assert debut_count == 1
        scored_debut = output_connection.execute(
            "SELECT COUNT(*) FROM official_existing_ability WHERE score_status='OK' AND career_scored_run_count=0"
        ).fetchone()[0]
        assert scored_debut == 0
    finally:
        output_connection.close()
        source_connection.close()


def test_annual_model_snapshot_is_past_only_and_scores_existing_2013_rows(tmp_path: Path) -> None:
    """The 2013 model must use only earlier labeled rows and score finite existing-horse targets."""
    _, output = _materialized(tmp_path)
    connection = sqlite3.connect(output)
    connection.row_factory = sqlite3.Row
    try:
        snapshot = connection.execute("SELECT * FROM ability_model_snapshot WHERE target_year=2013").fetchone()
        assert snapshot is not None
        assert snapshot["training_through_year"] == 2012
        assert snapshot["training_row_count"] == 4
        assert snapshot["recent_decay"] == "070"
        assert snapshot["distance_bandwidth_m"] == 200
        assert snapshot["aptitude_shrink_k"] == 0
        assert snapshot["jockey_shrink_k"] == 0
        assert snapshot["alpha"] == 0.01
        assert snapshot["l1_ratio"] == 0.5
        scored = connection.execute(
            """
            SELECT COUNT(*) FROM official_existing_ability
            WHERE year=2013 AND career_scored_run_count>=1
              AND race_context_availability='PRE_RACE'
              AND score_status='OK' AND ability_raw IS NOT NULL
            """
        ).fetchone()[0]
        assert scored == 2
    finally:
        connection.close()


def test_warmup_rows_are_retained_without_ability_score(tmp_path: Path) -> None:
    """Pre-2013 rows remain materialized but cannot receive a production Ability score."""
    _, output = _materialized(tmp_path)
    connection = sqlite3.connect(output)
    try:
        count = connection.execute(
            "SELECT COUNT(*) FROM official_existing_ability WHERE year<2013 AND score_status='PRE_MODEL_WARMUP' AND ability_raw IS NULL"
        ).fetchone()[0]
        total = connection.execute("SELECT COUNT(*) FROM official_existing_ability WHERE year<2013").fetchone()[0]
        assert total == 5 and count == total
    finally:
        connection.close()


def test_schema_contains_no_market_columns(tmp_path: Path) -> None:
    """Official Ability tables must remain market-free."""
    _, output = _materialized(tmp_path)
    connection = sqlite3.connect(output)
    try:
        columns = []
        for table in ("official_existing_ability", "ability_model_snapshot"):
            columns.extend(str(row[1]).lower() for row in connection.execute(f"PRAGMA table_info({table})"))
        assert all("odds" not in column and "popularity" not in column and "market" not in column for column in columns)
    finally:
        connection.close()
