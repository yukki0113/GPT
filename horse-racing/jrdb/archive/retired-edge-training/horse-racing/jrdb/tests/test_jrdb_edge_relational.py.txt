from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jrdb_edge_relational import connect_edge_mart  # noqa: E402
from prepare_jrdb_edge_feature_mart_duckdb import prepare_workspace  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_root(root: Path) -> Path:
    canonical = root / "feature"
    generation = "g1"
    asset = canonical / f"generations/{generation}/edge_runner_fact.parquet"
    asset.parent.mkdir(parents=True)
    con = duckdb.connect(":memory:")
    try:
        literal = str(asset).replace("'", "''")
        con.execute(
            """
            CREATE TABLE fact AS
            SELECT 'R1'::VARCHAR AS race_key,
                   1::INTEGER AS horse_no,
                   '2026-09-20'::VARCHAR AS race_date,
                   'ELIGIBLE'::VARCHAR AS calculation_status,
                   'H1'::VARCHAR AS horse_id,
                   NULL::VARCHAR AS horse_quality_model_version
            """
        )
        con.execute(
            f"COPY fact TO '{literal}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
    finally:
        con.close()
    audit = canonical / f"generations/{generation}/audit.json"
    audit.write_text('{"status":"PASS"}\n', encoding="utf-8")
    manifest = {
        "artifact_type": "jrdb_edge_feature_mart",
        "schema_version": "v0.2",
        "storage_format": "parquet",
        "storage_version": "1",
        "generation_id": generation,
        "validation_status": "PASS",
        "canonical_key": ["race_key", "horse_no"],
        "sort_by": ["race_date", "race_key", "horse_no"],
        "row_count": 1,
        "schema_hash": "test",
        "fact_asset": {
            "name": "edge_runner_fact",
            "relative_path": f"generations/{generation}/edge_runner_fact.parquet",
            "rows": 1,
            "size_bytes": asset.stat().st_size,
            "sha256": _sha(asset),
        },
        "audit": {
            "relative_path": f"generations/{generation}/audit.json",
            "size_bytes": audit.stat().st_size,
            "sha256": _sha(audit),
        },
    }
    (canonical / f"generations/{generation}/manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (canonical / "current.json").write_text(
        json.dumps(
            {
                "status": "CURRENT",
                "generation_id": generation,
                "manifest": f"generations/{generation}/manifest.json",
            }
        ),
        encoding="utf-8",
    )
    return canonical


def test_prepares_duckdb_workspace_from_parquet_canonical(tmp_path: Path) -> None:
    root = _canonical_root(tmp_path)
    output = tmp_path / "edge.duckdb"
    result = prepare_workspace(root, output)
    assert result["status"] == "PASS"
    assert result["workspace_engine"] == "duckdb"
    assert result["source_mode"] == "parquet_canonical"
    assert result["rows"] == 1

    con = connect_edge_mart(output)
    try:
        row = con.execute(
            "SELECT race_key,horse_no FROM edge_runner_fact"
        ).fetchone()
        assert row is not None
        assert row[0] == "R1"
        assert row["race_key"] == "R1"
        con.execute(
            "UPDATE edge_runner_fact SET horse_quality_model_version=? WHERE race_key=?",
            ["MODEL", "R1"],
        )
        con.commit()
    finally:
        con.close()

    check = duckdb.connect(str(output), read_only=True)
    try:
        assert check.execute(
            "SELECT horse_quality_model_version FROM edge_runner_fact"
        ).fetchone()[0] == "MODEL"
    finally:
        check.close()


def test_legacy_sqlite_workspace_remains_reproduction_compatible(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite"
    raw = sqlite3.connect(path)
    raw.execute("CREATE TABLE edge_runner_fact(race_key TEXT, horse_no INTEGER)")
    raw.execute("INSERT INTO edge_runner_fact VALUES('R2',2)")
    raw.commit()
    raw.close()

    con = connect_edge_mart(path, read_only=True)
    try:
        row = con.execute("SELECT * FROM edge_runner_fact").fetchone()
        assert row is not None
        assert row["race_key"] == "R2"
        assert row[1] == 2
    finally:
        con.close()
