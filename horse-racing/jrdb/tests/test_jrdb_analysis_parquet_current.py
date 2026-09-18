from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from jrdb_analysis_parquet_current import AnalysisParquetCurrentError, resolve_current


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AnalysisParquetCurrentTest(unittest.TestCase):
    def make_root(self) -> Path:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        files = {
            "objects/fact_entry_result_lite/year=2026/a.parquet": b"fact",
            "metadata/meta_analysis_build-a.parquet": b"build",
            "metadata/meta_analysis_ingest_batch-a.parquet": b"batch",
        }
        entries = {}
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            entries[relative] = {"relative_path": relative, "sha256": digest(path), "size_bytes": len(content)}
        manifest = {
            "artifact_type": "jrdb_analysis", "schema_version": "v1.3", "storage_format": "parquet", "validation_status": "PASS", "generation_id": "g1", "total_rows": 2,
            "fact_table": {"name": "fact_entry_result_lite", "canonical_key": ["race_key", "horse_no"], "partitions": [{"year": 2026, "rows": 2, **entries["objects/fact_entry_result_lite/year=2026/a.parquet"]}]},
            "metadata_tables": {"meta_analysis_build": {"rows": 1, **entries["metadata/meta_analysis_build-a.parquet"]}, "meta_analysis_ingest_batch": {"rows": 1, **entries["metadata/meta_analysis_ingest_batch-a.parquet"]}},
        }
        target = root / "generations/g1"
        target.mkdir(parents=True)
        (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (root / "current.json").write_text(json.dumps({"status": "CURRENT", "generation_id": "g1", "manifest": "generations/g1/manifest.json"}), encoding="utf-8")
        return root

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_resolves_valid_current(self) -> None:
        report = resolve_current(self.make_root())
        self.assertEqual(report["generation_id"], "g1")
        self.assertEqual(report["rows"], 2)

    def test_rejects_asset_sha_mismatch(self) -> None:
        root = self.make_root()
        (root / "objects/fact_entry_result_lite/year=2026/a.parquet").write_bytes(b"evil")
        with self.assertRaisesRegex(AnalysisParquetCurrentError, "SHA-256 mismatch"):
            resolve_current(root)

    def test_rejects_pointer_manifest_mismatch(self) -> None:
        root = self.make_root()
        (root / "current.json").write_text(json.dumps({"status": "CURRENT", "generation_id": "g1", "manifest": "generations/other/manifest.json"}), encoding="utf-8")
        with self.assertRaisesRegex(AnalysisParquetCurrentError, "does not match generation"):
            resolve_current(root)

    def test_rejects_total_rows_mismatch(self) -> None:
        root = self.make_root()
        manifest_path = root / "generations/g1/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")); manifest["total_rows"] = 3
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(AnalysisParquetCurrentError, "total row count"):
            resolve_current(root)

    def test_accepts_only_v1_missing_metadata_size_when_sha_matches(self) -> None:
        root = self.make_root()
        manifest_path = root / "generations/g1/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["storage_version"] = "1"
        del manifest["metadata_tables"]["meta_analysis_build"]["size_bytes"]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(resolve_current(root)["generation_id"], "g1")

        manifest["storage_version"] = "2"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(AnalysisParquetCurrentError, "Size mismatch"):
            resolve_current(root)
