from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


sys.modules.setdefault("data_storage", types.ModuleType("data_storage"))
query = types.ModuleType("data_storage.query")
query.connect_parquet = lambda _: None
sys.modules.setdefault("data_storage.query", query)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "no1"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import materialize_jrdb_analysis_sqlite as target  # noqa: E402


SCHEMA = """
CREATE TABLE fact_entry_result_lite(race_key TEXT, horse_no INTEGER, value TEXT);
CREATE TABLE meta_analysis_build(build_id INTEGER);
CREATE TABLE meta_analysis_ingest_batch(batch_id INTEGER);
"""


class MaterializeAnalysisTest(unittest.TestCase):
    def make_generation(self, root: Path) -> tuple[Path, dict]:
        manifest_path = root / "generations/g1/manifest.json"
        manifest_path.parent.mkdir(parents=True)
        manifest = {
            "generation_id": "g1",
            "fact_table": {"partitions": [{"relative_path": "fact.parquet", "rows": 2}]},
            "metadata_tables": {
                "meta_analysis_build": {"relative_path": "build.parquet", "rows": 1},
                "meta_analysis_ingest_batch": {"relative_path": "ingest.parquet", "rows": 1},
            },
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest_path, manifest

    def loader(self, duplicate: bool = False):
        def load(connection: sqlite3.Connection, table: str, _: Path) -> None:
            if table == target.FACT_TABLE:
                rows = [("r1", 1, "a"), ("r2" if not duplicate else "r1", 2 if not duplicate else 1, "b")]
                connection.executemany("INSERT INTO fact_entry_result_lite VALUES(?,?,?)", rows)
            elif table == "meta_analysis_build":
                connection.execute("INSERT INTO meta_analysis_build VALUES(1)")
            else:
                connection.execute("INSERT INTO meta_analysis_ingest_batch VALUES(1)")
        return load

    def test_materializes_verified_generation_and_audits_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, manifest = self.make_generation(root)
            schema = root / "schema.sql"; schema.write_text(SCHEMA, encoding="utf-8")
            output = root / "work.sqlite"
            report = {"generation_id": "g1", "manifest": manifest_path, "rows": 2}
            with patch.object(target, "validate_generation", return_value=report), patch.object(target, "load_parquet", self.loader()):
                result = target.materialize_generation(root, manifest_path, output, schema)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["rows"], 2)
            self.assertTrue(output.is_file())

    def test_failure_removes_incoming_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, _ = self.make_generation(root)
            schema = root / "schema.sql"; schema.write_text(SCHEMA, encoding="utf-8")
            output = root / "work.sqlite"
            report = {"generation_id": "g1", "manifest": manifest_path, "rows": 2}
            with patch.object(target, "validate_generation", return_value=report), patch.object(target, "load_parquet", self.loader(duplicate=True)):
                with self.assertRaisesRegex(RuntimeError, "duplicate canonical keys"):
                    target.materialize_generation(root, manifest_path, output, schema)
            self.assertFalse(output.exists())

    def test_current_resolution_happens_before_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, _ = self.make_generation(root)
            schema = root / "schema.sql"; schema.write_text(SCHEMA, encoding="utf-8")
            output = root / "work.sqlite"
            current = {"generation_id": "g1", "manifest": manifest_path, "rows": 2}
            with patch.object(target, "resolve_current", return_value=current), patch.object(target, "validate_generation", side_effect=RuntimeError("bad manifest")):
                with self.assertRaisesRegex(RuntimeError, "bad manifest"):
                    target.materialize_current(root, output, schema)
            self.assertFalse(output.exists())
