from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# Another legacy regression module installs a stub under this module name at
# import time. Ensure this test exercises the real production implementation.
sys.modules.pop("update_jrdb_analysis_incremental", None)

import build_jrdb_analysis_post_race_parquet_native as target  # noqa: E402
from update_jrdb_analysis_incremental import FACT_COLUMNS  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_parquet(path: Path, table: str, columns: list[str], rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    try:
        definitions = ",".join(f'"{name}" VARCHAR' for name in columns)
        con.execute(f'CREATE TABLE "{table}" ({definitions})')
        if rows:
            marks = ",".join("?" for _ in columns)
            con.executemany(f'INSERT INTO "{table}" VALUES ({marks})', rows)
        literal = str(path).replace("'", "''")
        con.execute(f"COPY (SELECT * FROM \"{table}\") TO '{literal}' (FORMAT PARQUET)")
    finally:
        con.close()


def _fact_row(date: str, race_key: str, horse_no: str) -> tuple:
    values = {name: None for name in FACT_COLUMNS}
    values.update(
        {
            "race_date": date,
            "year": date[:4],
            "venue_code": "09",
            "race_no": "1",
            "track_type": "1",
            "distance": "1600",
            "race_key": race_key,
            "horse_no": horse_no,
            "horse_id": f"H{horse_no}",
        }
    )
    return tuple(values[name] for name in FACT_COLUMNS)


def _asset(root: Path, path: Path, rows: int) -> dict:
    return {
        "relative_path": str(path.relative_to(root)),
        "sha256": _sha(path),
        "size_bytes": path.stat().st_size,
        "rows": rows,
    }


def _make_current(root: Path) -> None:
    fact_2025 = root / "objects/fact_entry_result_lite/year=2025/base2025.parquet"
    fact_2026 = root / "objects/fact_entry_result_lite/year=2026/base2026.parquet"
    _write_parquet(fact_2025, "fact", list(FACT_COLUMNS), [_fact_row("2025-12-28", "R2025", "1")])
    _write_parquet(fact_2026, "fact", list(FACT_COLUMNS), [_fact_row("2026-09-19", "ROLD", "1")])

    build_cols = [
        "build_id", "builder_version", "schema_version", "source_core_sha256",
        "started_at", "finished_at", "status", "row_count",
    ]
    ingest_cols = [
        "batch_id", "target_date", "builder_version", "schema_version",
        "started_at", "finished_at", "status", "source_manifest",
        "source_sha256s", "race_count", "row_count", "replaced_row_count",
        "message",
    ]
    build = root / "metadata/build.parquet"
    ingest = root / "metadata/ingest.parquet"
    _write_parquet(
        build,
        "build",
        build_cols,
        [("1", "legacy", "v1.3", None, "x", "x", "SUCCESS", "2")],
    )
    _write_parquet(
        ingest,
        "ingest",
        ingest_cols,
        [("1", "2026-09-19", "legacy", "v1.3", "x", "x", "SUCCESS", "{}", "{}", "1", "1", "0", "legacy")],
    )

    generation = root / "generations/g0"
    generation.mkdir(parents=True)
    manifest = {
        "artifact_type": "jrdb_analysis",
        "schema_version": "v1.3",
        "storage_format": "parquet",
        "storage_version": "1",
        "generation_id": "g0",
        "validation_status": "PASS",
        "fact_table": {
            "name": "fact_entry_result_lite",
            "canonical_key": ["race_key", "horse_no"],
            "sort_by": ["race_date", "race_key", "horse_no"],
            "partitions": [
                {"year": 2025, **_asset(root, fact_2025, 1)},
                {"year": 2026, **_asset(root, fact_2026, 1)},
            ],
        },
        "metadata_tables": {
            "meta_analysis_build": _asset(root, build, 1),
            "meta_analysis_ingest_batch": _asset(root, ingest, 1),
        },
        "period_from": "2025-12-28",
        "period_to": "2026-09-19",
        "total_rows": 2,
    }
    (generation / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "current.json").write_text(
        json.dumps(
            {
                "status": "CURRENT",
                "generation_id": "g0",
                "manifest": "generations/g0/manifest.json",
            }
        ),
        encoding="utf-8",
    )


class NativePostRaceCandidateTest(unittest.TestCase):
    def test_rewrites_only_affected_year_without_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            root = tmp_path / "analysis"
            _make_current(root)
            current_before = (root / "current.json").read_bytes()

            update = {
                "date": "2026-09-20",
                "year": 2026,
                "rows": [_fact_row("2026-09-20", "RNEW", "2")],
                "metadata": {
                    "source_manifest": {"PACI": "paci", "SED": "sed"},
                    "source_sha256s": {"PACI": "a", "SED": "b"},
                    "race_count": 1,
                    "row_count": 1,
                    "missing_profile_rows": 0,
                    "source_mode": "paci_sed",
                },
                "sha256s": {"PACI": "a", "SED": "b"},
            }

            with patch.object(target, "_load_update", return_value=update):
                result = target.build_native_candidate(
                    analysis_root=root,
                    generation_id="g1",
                    paci_files=[tmp_path / "paci.zip"],
                    sed_files=[tmp_path / "sed.zip"],
                )

            self.assertEqual(result["status"], "CANDIDATE_PASS")
            self.assertIs(result["audit"]["native_parquet_update"], True)
            self.assertIs(result["audit"]["full_sqlite_materialization"], False)
            self.assertEqual((root / "current.json").read_bytes(), current_before)

            old_manifest = json.loads((root / "generations/g0/manifest.json").read_text())
            new_manifest = json.loads((root / "generations/g1/manifest.json").read_text())
            old_parts = {p["year"]: p for p in old_manifest["fact_table"]["partitions"]}
            new_parts = {p["year"]: p for p in new_manifest["fact_table"]["partitions"]}

            self.assertEqual(new_parts[2025], old_parts[2025])
            self.assertNotEqual(new_parts[2026]["sha256"], old_parts[2026]["sha256"])
            self.assertEqual(
                new_manifest["update_mode"],
                "parquet_native_affected_year_replace",
            )
            self.assertEqual(new_manifest["total_rows"], 3)
            self.assertEqual(new_manifest["period_to"], "2026-09-20")


if __name__ == "__main__":
    unittest.main()
