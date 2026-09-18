from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "build_jrdb_analysis_post_race_parquet_candidate.py"
SPEC = importlib.util.spec_from_file_location("candidate_module", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)


class CandidateBuildTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.current = self.root / "current.json"
        self.current.write_bytes(b'{"status":"CURRENT","generation_id":"old"}\n')
        MODULE.__dict__.pop("resolve_current", None)
        MODULE.__dict__.pop("validate_generation", None)
        MODULE.__dict__.pop("migrate", None)
        import sys
        import types
        current = types.ModuleType("jrdb_analysis_parquet_current")
        current.resolve_current = lambda root: {"generation_id": "old", "manifest": root / "generations/old/manifest.json"}
        current.validate_generation = lambda root, manifest: {"generation_id": "new", "rows": 17}
        migration = types.ModuleType("migrate_jrdb_analysis_parquet")
        migration.migrate = lambda *args, **kwargs: None
        self.old_modules = {name: sys.modules.get(name) for name in (current.__name__, migration.__name__)}
        sys.modules[current.__name__] = current
        sys.modules[migration.__name__] = migration
        SPEC.loader.exec_module(MODULE)

    def tearDown(self) -> None:
        import sys
        for name, old in self.old_modules.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
        self.temp.cleanup()

    def result(self, audit: dict | None = None) -> dict:
        return {
            "pointer": {"status": "SHADOW_PASS", "generation_id": "new", "manifest": "generations/new/manifest.json"},
            "audit": audit or {"status": "PASS", "row_count_equal": True, "canonical_key_equal": True, "schema_contract_equal": True, "row_level_equivalence": True, "metadata_preserved": True, "duplicate_key_rows": 0},
        }

    def test_builds_shadow_candidate_and_keeps_current_bytes(self) -> None:
        before = self.current.read_bytes()
        with patch.object(MODULE, "migrate", return_value=self.result()) as migration:
            report = MODULE.build_candidate(self.root / "workspace.sqlite", self.root, "new", {2026})
        self.assertEqual(self.current.read_bytes(), before)
        self.assertEqual(report["status"], "CANDIDATE_PASS")
        self.assertEqual(report["previous_generation_id"], "old")
        self.assertEqual(report["affected_years"], [2026])
        self.assertFalse(migration.call_args.kwargs["promote"])

    def test_rejects_candidate_with_duplicate_keys(self) -> None:
        bad = self.result({**self.result()["audit"], "duplicate_key_rows": 1})
        with patch.object(MODULE, "migrate", return_value=bad):
            with self.assertRaisesRegex(MODULE.AnalysisCandidateError, "duplicate_key_rows"):
                MODULE.build_candidate(self.root / "workspace.sqlite", self.root, "new", {2026})

    def test_rejects_current_mutation(self) -> None:
        def mutating_migration(*args, **kwargs):
            self.current.write_bytes(b"changed")
            return self.result()
        with patch.object(MODULE, "migrate", side_effect=mutating_migration):
            with self.assertRaisesRegex(MODULE.AnalysisCandidateError, "changed current.json"):
                MODULE.build_candidate(self.root / "workspace.sqlite", self.root, "new", {2026})
