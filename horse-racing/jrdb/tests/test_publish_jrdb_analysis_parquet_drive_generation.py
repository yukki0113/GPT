from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
import shutil
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("publish_jrdb_analysis_parquet_drive_generation.py")
SPEC = importlib.util.spec_from_file_location("drive_publish_module", MODULE_PATH)
assert SPEC and SPEC.loader


class DrivePublishTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.candidate = Path(self.temp.name) / "candidate"
        self.drive = Path(self.temp.name) / "drive"
        self.roundtrip = Path(self.temp.name) / "roundtrip"
        self.candidate.mkdir(); self.drive.mkdir()
        self.current = self.drive / "current.json"
        self.current.write_bytes(b'{"status":"CURRENT","generation_id":"old"}\n')
        self._install_module_stubs()
        self._write_candidate()
        shutil.copytree(self.candidate, self.roundtrip)
        (self.roundtrip / "current.json").write_bytes(b'{"status":"CURRENT","generation_id":"old"}\n')

    def _install_module_stubs(self) -> None:
        current = types.ModuleType("jrdb_analysis_parquet_current")
        current.resolve_current = lambda root: {"generation_id": "old"}
        current.validate_generation = lambda root, manifest: {"generation_id": "new", "rows": 9}
        self.old = sys.modules.get(current.__name__)
        sys.modules[current.__name__] = current
        self.module = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(self.module)

    def _write_candidate(self) -> None:
        (self.candidate / "generations/new").mkdir(parents=True)
        (self.candidate / "objects/fact/year=2026").mkdir(parents=True)
        (self.candidate / "metadata").mkdir(parents=True)
        (self.candidate / "objects/fact/year=2026/a.parquet").write_bytes(b"fact")
        (self.candidate / "metadata/build.parquet").write_bytes(b"build")
        (self.candidate / "metadata/batch.parquet").write_bytes(b"batch")
        manifest = {"generation_id": "new", "fact_table": {"partitions": [{"relative_path": "objects/fact/year=2026/a.parquet"}]}, "metadata_tables": {"meta_analysis_build": {"relative_path": "metadata/build.parquet"}, "meta_analysis_ingest_batch": {"relative_path": "metadata/batch.parquet"}}}
        (self.candidate / "generations/new/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        audit = {"status": "PASS", "row_count_equal": True, "canonical_key_equal": True, "schema_contract_equal": True, "row_level_equivalence": True, "metadata_preserved": True, "duplicate_key_rows": 0}
        (self.candidate / "generations/new/audit.json").write_text(json.dumps(audit), encoding="utf-8")

    def tearDown(self) -> None:
        if self.old is None:
            sys.modules.pop("jrdb_analysis_parquet_current", None)
        else:
            sys.modules["jrdb_analysis_parquet_current"] = self.old
        self.temp.cleanup()

    def test_promotes_only_after_copy_and_round_trip_gates(self) -> None:
        result = self.module.publish_and_promote(self.candidate, self.drive, self.roundtrip, "new")
        pointer = json.loads(self.current.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "PROMOTED")
        self.assertEqual(pointer["generation_id"], "new")
        self.assertEqual(pointer["previous_generation_id"], "old")
        self.assertEqual((self.drive / "objects/fact/year=2026/a.parquet").read_bytes(), b"fact")

    def test_collision_keeps_current_unchanged(self) -> None:
        target = self.drive / "objects/fact/year=2026/a.parquet"
        target.parent.mkdir(parents=True); target.write_bytes(b"other")
        before = self.current.read_bytes()
        with self.assertRaisesRegex(self.module.AnalysisDrivePublishError, "collision"):
            self.module.publish_and_promote(self.candidate, self.drive, self.roundtrip, "new")
        self.assertEqual(self.current.read_bytes(), before)

    def test_bad_remote_audit_keeps_current_unchanged(self) -> None:
        audit = self.roundtrip / "generations/new/audit.json"
        audit.write_text(json.dumps({"status": "FAIL"}), encoding="utf-8")
        before = self.current.read_bytes()
        with self.assertRaisesRegex(self.module.AnalysisDrivePublishError, "audit gate"):
            self.module.publish_and_promote(self.candidate, self.drive, self.roundtrip, "new")
        self.assertEqual(self.current.read_bytes(), before)
