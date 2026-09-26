#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jrdb_training_research_parquet import TrainingResearchParquetError, resolve_current


class TrainingResearchParquetResolverTest(unittest.TestCase):
    def _write_bundle(self, root: Path) -> tuple[Path, str]:
        try:
            import duckdb
        except ImportError:
            self.skipTest("duckdb is not installed")

        generation = "test-generation"
        generation_root = root / f"build-{generation}"
        generation_root.mkdir(parents=True)
        parquet = generation_root / "training_development.parquet"

        connection = duckdb.connect()
        try:
            target = str(parquet).replace("'", "''")
            connection.execute(
                f"""
                COPY (
                  SELECT * FROM (VALUES
                    ('05000101',1,2010),
                    ('05230101',1,2023)
                  ) AS t(race_key,horse_no,year)
                ) TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )
        finally:
            connection.close()

        digest = hashlib.sha256(parquet.read_bytes()).hexdigest()
        manifest = {
            "artifact_type": "jrdb_training_research",
            "schema_version": "v0.1",
            "storage_format": "parquet",
            "storage_version": "1",
            "canonical_key": ["race_key", "horse_no"],
            "generation_id": generation,
            "assets": {
                "training_development.parquet": {
                    "filename": "training_development.parquet",
                    "size_bytes": parquet.stat().st_size,
                    "sha256": digest,
                    "row_count": 2,
                }
            },
            "logical_uris": {
                "jrdb://training-research/v0.1/development": "training_development.parquet"
            },
        }
        (generation_root / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        (root / "current.json").write_text(
            json.dumps({
                "status": "SUCCESS",
                "build_id": generation,
                "generation_id": generation,
                "manifest": f"build-{generation}/manifest.json",
            }, indent=2) + "\n",
            encoding="utf-8",
        )
        return parquet, digest

    def test_resolve_current_validates_development_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, digest = self._write_bundle(root)
            report = resolve_current(root)
            self.assertEqual(report["generation_id"], "test-generation")
            self.assertEqual(report["rows"], 2)
            self.assertEqual(report["min_year"], 2010)
            self.assertEqual(report["max_year"], 2023)
            self.assertEqual(report["duplicate_keys"], 0)
            self.assertEqual(report["sha256"], digest)

    def test_sha_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parquet, _ = self._write_bundle(root)
            parquet.write_bytes(parquet.read_bytes() + b"tamper")
            with self.assertRaises(TrainingResearchParquetError):
                resolve_current(root)


if __name__ == "__main__":
    unittest.main()
