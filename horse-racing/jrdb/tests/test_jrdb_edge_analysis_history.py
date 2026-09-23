"""Regression tests for Edge Analysis history backends."""
from __future__ import annotations

import json
import sqlite3
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import jrdb_edge_analysis_history as target  # noqa: E402


def _sqlite(path: Path) -> None:
    con = sqlite3.connect(path)
    con.execute(
        """CREATE TABLE fact_entry_result_lite(
            race_key TEXT, race_date TEXT, horse_no INTEGER, horse_id TEXT,
            track_type TEXT, distance INTEGER, frame_no INTEGER
        )"""
    )
    con.execute(
        "INSERT INTO fact_entry_result_lite VALUES(?,?,?,?,?,?,?)",
        ("09010101", "2026-08-20", 3, "H0000001", "1", 1800, 5),
    )
    con.commit()
    con.close()


def test_sqlite_history_preserves_exact_previous_lookup(tmp_path: Path) -> None:
    path = tmp_path / "analysis.sqlite"
    _sqlite(path)
    source = target.open_analysis_history(analysis_db=path)
    assert source is not None
    try:
        previous = source.lookup(
            prev_race_key="09010101",
            horse_id="H0000001",
            target_date="2026-09-09",
        )
        assert previous == {
            "race_date": "2026-08-20",
            "surface_code": "1",
            "distance_m": 1800,
            "frame_no": 5,
        }
        assert source.source_info["kind"] == "SQLITE"
        assert source.source_info["rows"] == 1
    finally:
        source.close()


def test_history_backends_are_mutually_exclusive(tmp_path: Path) -> None:
    path = tmp_path / "analysis.sqlite"
    _sqlite(path)
    with pytest.raises(target.AnalysisHistoryError, match="only one"):
        target.open_analysis_history(analysis_db=path, analysis_root=tmp_path)


class _FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0]


class _FakeDuckConnection:
    def __init__(self):
        self.closed = False

    def execute(self, sql, params=None):
        if sql.startswith("CREATE VIEW"):
            return _FakeResult([])
        if sql == "DESCRIBE analysis_fact":
            return _FakeResult([(name,) for name in sorted(target.REQUIRED_COLUMNS)])
        if sql.startswith("SELECT MIN(race_date)"):
            return _FakeResult([("2010-01-05", "2026-09-06", 12345)])
        if "WHERE race_key=? AND horse_id=?" in sql:
            if params == ["09010101", "H0000001"]:
                return _FakeResult([("2026-08-20", "1", 1800, 5)])
            return _FakeResult([])
        raise AssertionError(sql)

    def close(self):
        self.closed = True


def test_parquet_history_uses_validated_current_generation(tmp_path: Path) -> None:
    root = tmp_path / "analysis"
    manifest = root / "generations" / "g1" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "fact_table": {
                    "partitions": [
                        {"year": 2026, "relative_path": "objects/fact/year=2026/a.parquet"}
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    fake_connection = _FakeDuckConnection()
    fake_duckdb = types.SimpleNamespace(connect=lambda _: fake_connection)
    report = {"generation_id": "g1", "manifest": manifest}

    with patch.object(target, "resolve_current", return_value=report), patch.dict(
        sys.modules, {"duckdb": fake_duckdb}
    ):
        source = target.open_analysis_history(analysis_root=root)

    assert source is not None
    try:
        assert source.source_info["kind"] == "PARQUET"
        assert source.source_info["generation_id"] == "g1"
        assert source.source_info["rows"] == 12345
        assert source.lookup(
            prev_race_key="09010101",
            horse_id="H0000001",
            target_date="2026-09-09",
        ) == {
            "race_date": "2026-08-20",
            "surface_code": "1",
            "distance_m": 1800,
            "frame_no": 5,
        }
    finally:
        source.close()
    assert fake_connection.closed is True
