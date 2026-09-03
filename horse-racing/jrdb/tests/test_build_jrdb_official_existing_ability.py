"""Smoke/regression tests for official Existing-Horse Ability v0.1 materialization."""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
ABILITY_FIXTURE = Path(__file__).with_name("test_build_jrdb_ability_snapshot.py")
BUILDER_PATH = SRC / "build_jrdb_official_existing_ability.py"
SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "jrdb_official_existing_ability_schema_v0_1.sql"


def _load(name: str, path: Path):
    """Load one repository module directly from path."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ABILITY = _load("official_existing_ability_snapshot_fixture", ABILITY_FIXTURE)
BUILDER = _load("official_existing_ability_builder", BUILDER_PATH)


def _materialized(tmp_path: Path) -> tuple[Path, Path]:
    """Build a small Ability snapshot then materialize the frozen existing-horse model."""
    source = ABILITY._snapshot(tmp_path)
    output = tmp_path / "official_existing_ability.sqlite"
    BUILDER.build(source, output, SCHEMA)
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
        assert debut_count > 0
        scored_debut = output_connection.execute(
            """
            SELECT COUNT(*) FROM official_existing_ability
            WHERE score_status='OK' AND career_scored_run_count=0
            """
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
        snapshot = connection.execute(
            "SELECT * FROM ability_model_snapshot WHERE target_year=2013"
        ).fetchone()
        assert snapshot is not None
        assert snapshot["training_through_year"] < 2013
        assert snapshot["training_row_count"] > 0
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
        assert scored > 0
    finally:
        connection.close()


def test_warmup_rows_are_retained_without_ability_score(tmp_path: Path) -> None:
    """Pre-2013 rows remain materialized but cannot receive a production Ability score."""
    _, output = _materialized(tmp_path)
    connection = sqlite3.connect(output)
    try:
        count = connection.execute(
            """
            SELECT COUNT(*) FROM official_existing_ability
            WHERE year<2013 AND score_status='PRE_MODEL_WARMUP' AND ability_raw IS NULL
            """
        ).fetchone()[0]
        total = connection.execute(
            "SELECT COUNT(*) FROM official_existing_ability WHERE year<2013"
        ).fetchone()[0]
        assert total > 0 and count == total
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
