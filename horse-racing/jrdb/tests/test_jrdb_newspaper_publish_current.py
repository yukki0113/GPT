#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jrdb_newspaper_publish_current import publish  # noqa: E402


def race_bundle(key: str = "01262501") -> dict:
    return {
        "schema_version": "0.1",
        "race": {
            "date": "2026-09-05",
            "race_key": key,
            "venue_code": "01",
            "venue": "札幌",
            "race_no": 1,
        },
        "horses": [{"horse_no": 1, "horse_name": "TEST"}],
        "metadata": {},
    }


def day_package() -> dict:
    return {
        "schema_version": "0.1",
        "bundle_kind": "jrdb_pwa_newspaper_day_package",
        "manifest": {
            "schema_version": "0.1",
            "manifest_kind": "jrdb_pwa_newspaper_daily_manifest",
            "date": "2026-09-05",
            "revision": 4,
            "completeness": {"expected_races": 1},
            "races": [{
                "race_key": "01262501",
                "venue_code": "01",
                "venue": "札幌",
                "race_no": 1,
                "path": "races/01_01_01262501.json",
                "sha256": "0" * 64,
                "size_bytes": 0,
                "horse_count": 1,
            }],
        },
        "races": [race_bundle()],
    }


class NewspaperPublishCurrentTest(unittest.TestCase):
    def test_publish_refreshes_hash_and_writes_complete_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_path = root / "day.json"
            package_path.write_text(json.dumps(day_package(), ensure_ascii=False), encoding="utf-8")
            output = root / "current"
            result = publish(package_path, output)
            manifest_path = output / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            race_path = output / manifest["races"][0]["path"]
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(race_path.is_file())
            import hashlib
            self.assertEqual(
                hashlib.sha256(race_path.read_bytes()).hexdigest(),
                manifest["races"][0]["sha256"],
            )
            self.assertEqual(race_path.stat().st_size, manifest["races"][0]["size_bytes"])

            race_value = json.loads(race_path.read_text(encoding="utf-8"))
            expected_race_bytes = (
                json.dumps(race_value, ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            expected_manifest_bytes = (
                json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            self.assertEqual(race_path.read_bytes(), expected_race_bytes)
            self.assertEqual(manifest_path.read_bytes(), expected_manifest_bytes)

    def test_identity_mismatch_fails_before_replacing_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "current"
            output.mkdir()
            (output / "sentinel.txt").write_text("keep", encoding="utf-8")
            package = day_package()
            package["races"][0]["race"]["race_no"] = 2
            package_path = root / "bad.json"
            package_path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                publish(package_path, output)
            self.assertEqual((output / "sentinel.txt").read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
