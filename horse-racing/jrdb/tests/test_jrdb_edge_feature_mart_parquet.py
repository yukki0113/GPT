from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT.parents[1] / "tools" / "data-storage"))

import audit_jrdb_edge_feature_mart_parquet_equivalence as equivalence  # noqa: E402
import build_jrdb_edge_feature_mart_parquet_generation as generation  # noqa: E402
import jrdb_edge_feature_mart_parquet as current  # noqa: E402


def _mart(tmp_path: Path) -> Path:
    path = tmp_path / "edge_mart.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE edge_runner_fact(
          race_key TEXT NOT NULL,
          horse_no INTEGER NOT NULL,
          race_date TEXT NOT NULL,
          is_pre_race_eligible INTEGER NOT NULL,
          track_condition_code TEXT,
          surface_code TEXT,
          label_finish INTEGER,
          calculation_status TEXT NOT NULL,
          metric REAL,
          PRIMARY KEY(race_key,horse_no)
        );
        """
    )
    connection.executemany(
        "INSERT INTO edge_runner_fact VALUES(?,?,?,?,?,?,?,?,?)",
        [
            ("R1", 1, "2025-01-01", 1, "1", "1", 1, "ELIGIBLE", 1.25),
            ("R1", 2, "2025-01-01", 1, None, "1", 4, "ELIGIBLE", None),
            ("R2", 1, "2025-01-02", 0, "2", "2", None, "SOURCE_NOT_PRE_RACE", -0.0),
        ],
    )
    connection.commit()
    connection.close()
    return path


def test_build_equivalence_and_current_resolve(tmp_path: Path) -> None:
    mart = _mart(tmp_path)
    root = tmp_path / "canonical"
    result = generation.build_generation(
        sqlite_path=mart,
        output_root=root,
        generation_id="edge_feature_mart_v0_2_test",
        source_generation_id="warehouse-test",
        source_manifest_sha256="a" * 64,
    )
    parquet = Path(result["parquet"])
    audit = equivalence.audit(mart, parquet)
    assert audit["status"] == "PASS"
    assert audit["canonical_row_hash_equal"] is True
    assert audit["null_semantics_equal"] is True
    assert audit["duplicate_key_rows_parquet"] == 0

    pointer = {
        "status": "CURRENT",
        "generation_id": result["generation_id"],
        "manifest": f"generations/{result['generation_id']}/manifest.json",
        "previous_generation_id": None,
        "updated_at": "2026-09-25T00:00:00+00:00",
    }
    (root / "current.json").write_text(json.dumps(pointer) + "\n", encoding="utf-8")
    resolved = current.resolve_current(root)
    assert resolved["rows"] == 3
    connection, report = current.connect_current(root)
    try:
        assert report["generation_id"] == result["generation_id"]
        assert connection.execute("SELECT count(*) FROM edge_runner_fact").fetchone()[0] == 3
    finally:
        connection.close()


def test_current_fails_closed_on_sha_mismatch(tmp_path: Path) -> None:
    mart = _mart(tmp_path)
    root = tmp_path / "canonical"
    result = generation.build_generation(
        sqlite_path=mart,
        output_root=root,
        generation_id="edge_feature_mart_v0_2_test",
    )
    pointer = {
        "status": "CURRENT",
        "generation_id": result["generation_id"],
        "manifest": f"generations/{result['generation_id']}/manifest.json",
    }
    (root / "current.json").write_text(json.dumps(pointer) + "\n", encoding="utf-8")
    parquet = Path(result["parquet"])
    parquet.write_bytes(parquet.read_bytes() + b"x")
    with pytest.raises(current.EdgeFeatureMartParquetError, match="size mismatch|SHA-256 mismatch"):
        current.resolve_current(root)


def test_current_fails_closed_on_unsafe_manifest_path(tmp_path: Path) -> None:
    root = tmp_path / "canonical"
    root.mkdir()
    (root / "current.json").write_text(
        json.dumps({
            "status": "CURRENT",
            "generation_id": "g1",
            "manifest": "../manifest.json",
        }) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(current.EdgeFeatureMartParquetError, match="does not match generation"):
        current.resolve_current(root)
