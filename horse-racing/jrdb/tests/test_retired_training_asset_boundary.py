"""Assert that the retired archive contains only preserved non-EdgeDB assets."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / "horse-racing/jrdb/archive/retired-edge-training"


class RetiredTrainingAssetBoundaryTest(unittest.TestCase):
    def test_manifest_and_archived_assets(self):
        entries = json.loads((ARCHIVE / "ASSET_MAP.json").read_text())
        self.assertEqual(len(entries), 35)
        for entry in entries:
            with self.subTest(entry=entry["original"]):
                name = entry["original"].lower()
                self.assertFalse("edge" in name and "training_edge" not in name)
                self.assertFalse((ROOT / entry["original"]).exists())
                import hashlib
                self.assertEqual(
                    hashlib.sha256((ROOT / entry["archive"]).read_bytes()).hexdigest(),
                    entry["sha256"],
                )

    def test_shared_assets_retained(self):
        src = ROOT / "horse-racing/jrdb/src"
        for name in ("jrdb_canonical_codes.py", "jrdb_previous_start_research_ledger.py",
                     "jrdb_newspaper_retired_sources.py"):
            self.assertTrue((src / name).is_file())
        self.assertFalse((src / "jrdb_edge_v02_canonical.py").exists())

    def test_no_decommissioned_edge_archive_files(self):
        retired = ARCHIVE / "horse-racing/jrdb/src"
        self.assertFalse(any(p.name.startswith("jrdb_edge_") for p in retired.glob("*")))
