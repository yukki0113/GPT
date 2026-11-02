"""Focused regression tests for v0.2 RECENT categorical-code canonicalization."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from build_jrdb_edge_feature_mart_v0_2 import build as build_mart  # noqa: E402
from jrdb_edge_v02_canonical import (  # noqa: E402
    canonical_stable_evaluation_code,
    canonical_training_arrow_code,
    canonical_uptrend_code,
)


def test_recent_code_helpers_treat_zero_and_unknown_as_missing() -> None:
    """Only documented JRDB domains survive canonicalization."""
    assert canonical_uptrend_code("1") == "1"
    assert canonical_uptrend_code(5) == "5"
    assert canonical_uptrend_code("0") is None
    assert canonical_uptrend_code(0) is None
    assert canonical_uptrend_code("9") is None
    assert canonical_uptrend_code("") is None

    assert canonical_training_arrow_code("1") == "1"
    assert canonical_training_arrow_code(5) == "5"
    assert canonical_training_arrow_code("0") is None
    assert canonical_training_arrow_code("9") is None

    assert canonical_stable_evaluation_code("1") == "1"
    assert canonical_stable_evaluation_code(4) == "4"
    assert canonical_stable_evaluation_code("0") is None
    assert canonical_stable_evaluation_code("5") is None


def test_feature_mart_canonicalizes_recent_codes_before_discovery(tmp_path: Path) -> None:
    """Historical Feature Mart must use the same RECENT domains as current facts."""
    source = tmp_path / "index.sqlite"
    output = tmp_path / "mart.sqlite"

    con = sqlite3.connect(source)
    con.executescript(
        (ROOT / "schema/jrdb_index_base_schema_v0_1.sql").read_text(encoding="utf-8")
    )
    con.execute(
        """INSERT INTO race_context(
        race_key,race_date,year,venue_code,race_no,availability_class,source_kind,
        record_hash,distance_m,surface_code,turn_code,declared_field_size
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("05250101", "2025-01-05", 2025, "05", 1, "PRE_RACE", "BAC", "r", 1600, "1", "1", 12),
    )
    runner_sql = """INSERT INTO runner_pre(
        race_key,horse_no,horse_id,horse_name,frame_no,sex_code,jockey_code,trainer_code,
        rotation_interval,pre_idm,training_score,stable_score,uptrend_code,
        training_arrow_code,stable_evaluation_code,record_hash
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    con.execute(
        runner_sql,
        ("05250101", 1, "H1", "VALID", 1, "1", "J1", "T1", 4, 55.0, 60.0, 58.0, "2", "1", "3", "p1"),
    )
    con.execute(
        runner_sql,
        ("05250101", 2, "H2", "MISSING", 2, "1", "J2", "T2", 4, 54.0, 59.0, 57.0, "0", "0", "0", "p2"),
    )
    result_sql = """INSERT INTO runner_result(
        race_key,horse_no,horse_id,horse_name,finish,abnormal_code,win_payout,place_payout,record_hash
        ) VALUES(?,?,?,?,?,?,?,?,?)"""
    con.execute(result_sql, ("05250101", 1, "H1", "VALID", 1, "0", 300, 150, "x1"))
    con.execute(result_sql, ("05250101", 2, "H2", "MISSING", 2, "0", 0, 120, "x2"))
    con.commit()
    con.close()

    result = build_mart(
        source,
        output,
        ROOT / "schema/jrdb_edge_feature_mart_schema_v0_2.sql",
    )
    assert result["rows"] == 2

    out = sqlite3.connect(output)
    rows = out.execute(
        """SELECT horse_no,uptrend_code,training_arrow_code,stable_evaluation_code
        FROM edge_runner_fact ORDER BY horse_no"""
    ).fetchall()
    builder_version = out.execute(
        "SELECT builder_version FROM meta_edge_feature_mart_build"
    ).fetchone()[0]
    out.close()

    assert rows == [(1, "2", "1", "3"), (2, None, None, None)]
    assert builder_version == "0.2.4"
