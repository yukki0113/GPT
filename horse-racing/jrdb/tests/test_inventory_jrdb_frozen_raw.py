from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from inventory_jrdb_frozen_raw import build_inventory


class FrozenRawInventoryTests(unittest.TestCase):
    def sample_snapshot(self) -> dict:
        return {
            "raw_root": {"id": "raw-root", "title": "00_raw"},
            "families": [
                {
                    "id": "bac-folder",
                    "title": "BAC",
                    "files": [
                        {"id": "annual", "title": "BAC_2024.zip", "size": "100"},
                        {"id": "daily", "title": "BAC20250105.zip", "size": "101"},
                        {"id": "odd", "title": "notes.txt", "size": "1"},
                    ],
                },
                {"id": "paci-folder", "title": "PACI", "files": []},
                {"id": "kka-folder", "title": "KKA", "files": []},
            ],
        }

    def test_classifies_present_archives_without_inference(self) -> None:
        result = build_inventory(self.sample_snapshot())
        bac = next(item for item in result["families"] if item["family"] == "BAC")
        self.assertEqual(bac["status"], "TARGET")
        self.assertEqual(bac["annual_archive_count"], 1)
        self.assertEqual(bac["daily_archive_count"], 1)
        self.assertEqual(bac["unclassified_archive_count"], 1)
        annual = next(item for item in bac["archives"] if item["drive_id"] == "annual")
        self.assertEqual(annual["year"], 2024)
        self.assertEqual(annual["archive_checksum_status"], "UNAVAILABLE_FROM_DRIVE_LISTING")
        self.assertIn("KYI", result["missing_target_families"])

    def test_marks_paci_and_unknown_family_without_making_them_targets(self) -> None:
        result = build_inventory(self.sample_snapshot())
        statuses = {item["family"]: item["status"] for item in result["families"]}
        self.assertEqual(statuses["PACI"], "OUT_OF_SCOPE")
        self.assertEqual(statuses["KKA"], "UNSUPPORTED")

    def test_cli_refuses_to_overwrite_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = root / "snapshot.json"
            output = root / "inventory.json"
            snapshot.write_text(json.dumps(self.sample_snapshot()), encoding="utf-8")
            command = [sys.executable, str(ROOT / "src" / "inventory_jrdb_frozen_raw.py"), "--snapshot", str(snapshot), "--output", str(output)]
            first = subprocess.run(command, capture_output=True, text=True)
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertNotEqual(second.returncode, 0)


if __name__ == "__main__":
    unittest.main()
