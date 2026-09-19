#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_jrdb_normalized_warehouse import (  # noqa: E402
    ArchiveSpec,
    build_generation,
    storage_runtime_available,
)
from test_jrdb_hjc_common import sample_body  # noqa: E402
from test_jrdb_raw_common import make_ukc  # noqa: E402
from test_jrdb_warehouse_normalize import row  # noqa: E402


@unittest.skipUnless(storage_runtime_available(), "tools/data-storage Parquet runtime is not installed")
class NormalizedWarehouseBuilderTest(unittest.TestCase):
    def _zip(self, path: Path, members: dict[str, bytes]) -> Path:
        with zipfile.ZipFile(path, "w") as zipped:
            for name, body in members.items():
                zipped.writestr(name, body)
        return path

    def test_builds_content_addressed_zstd_assets_and_audited_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bac = self._zip(root / "BAC_2026.zip", {
                "BAC260830.txt": row("BAC", (1, 8, "0526A101"), (9, 8, "20260830"), (21, 4, "1600")) + b"\r\n",
            })
            hjc = self._zip(root / "HJC_2026.zip", {"HJC260830.txt": sample_body() + b"\r\n"})
            result = build_generation(
                [ArchiveSpec("BAC", 2026, bac), ArchiveSpec("HJC", 2026, hjc)],
                root / "warehouse", "warehouse-v1-test", "deadbeef", created_at="2026-09-18T00:00:00+00:00",
            )
            manifest = result["manifest"]
            self.assertEqual(manifest["status"], "PASS")
            self.assertEqual({item["family"] for item in manifest["assets"]}, {"bac", "hjc_race", "hjc_payout"})
            for asset in manifest["assets"]:
                self.assertTrue(asset["relative_path"].endswith(f"{asset['sha256']}.parquet"))
                self.assertGreater(asset["size_bytes"], 0)
                self.assertTrue(asset["schema_hash"])
            payout = next(item for item in manifest["assets"] if item["family"] == "hjc_payout")
            self.assertEqual(payout["row_count"], 36)
            self.assertEqual(payout["canonical_key"], ["race_key_raw", "bet_type", "slot_no"])
            generation_dir = Path(result["generation_dir"])
            self.assertEqual(json.loads((generation_dir / "manifest.json").read_text(encoding="utf-8"))["generation_id"], "warehouse-v1-test")
            self.assertFalse((root / "warehouse" / "current.json").exists())

    def test_fails_closed_on_duplicate_canonical_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            body = row("BAC", (1, 8, "0526A101"), (9, 8, "20260830"))
            archive = self._zip(root / "BAC_2026.zip", {"BAC260830.txt": body + b"\r\n" + body + b"\r\n"})
            with self.assertRaises(ValueError):
                build_generation([ArchiveSpec("BAC", 2026, archive)], root / "warehouse", "duplicate-test", "deadbeef")
            self.assertFalse((root / "warehouse" / "generations" / "duplicate-test").exists())

    def test_ukc_exact_duplicates_are_collapsed_with_complete_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            body = make_ukc()
            archive = self._zip(
                root / "UKC_2026.zip",
                {"UKC260830.txt": body + b"\r\n" + body + b"\r\n"},
            )
            result = build_generation(
                [ArchiveSpec("UKC", 2026, archive)],
                root / "warehouse", "ukc-lineage-test", "deadbeef",
                created_at="2026-09-18T00:00:00+00:00",
            )
            assets = {asset["family"]: asset for asset in result["manifest"]["assets"]}
            self.assertEqual(assets["ukc"]["row_count"], 1)
            self.assertEqual(assets["ukc_source_record_lineage"]["row_count"], 2)
            self.assertEqual(assets["ukc"]["source_record_count"], 2)
            self.assertEqual(assets["ukc"]["exact_source_duplicate_count"], 1)
            lineage_audit = next(
                item for item in result["audit"]["relations"]
                if item["relation"] == "ukc_source_record_lineage"
            )
            self.assertEqual(lineage_audit["duplicate_class_counts"], {
                "CANONICAL": 1,
                "EXACT_SOURCE_DUPLICATE": 1,
            })

    def test_ukc_conflicting_bodies_at_same_business_key_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = make_ukc()
            second = bytearray(first)
            second[44] = ord("2")  # Sex is non-key data; fixed-width remains valid.
            archive = self._zip(
                root / "UKC_2026.zip",
                {"UKC260830.txt": first + b"\r\n" + bytes(second) + b"\r\n"},
            )
            with self.assertRaisesRegex(ValueError, "different Raw bodies"):
                build_generation(
                    [ArchiveSpec("UKC", 2026, archive)],
                    root / "warehouse", "ukc-conflict-test", "deadbeef",
                )
            self.assertFalse((root / "warehouse" / "generations" / "ukc-conflict-test").exists())

    def test_zed_repeated_result_is_preserved_as_delivery_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            body = row(
                "ZED", (1, 8, "0526A101"), (9, 2, "03"),
                (11, 8, "20231001"), (19, 8, "20260830"),
            )
            archive = self._zip(root / "ZED_2026.zip", {
                "ZED260830.txt": body + b"\r\n",
                "ZED260906.txt": body + b"\r\n",
            })
            result = build_generation(
                [ArchiveSpec("ZED", 2026, archive)],
                root / "warehouse", "zed-snapshot-test", "deadbeef",
                created_at="2026-09-18T00:00:00+00:00",
            )
            asset = result["manifest"]["assets"][0]
            self.assertEqual(asset["row_count"], 2)
            self.assertEqual(asset["canonical_key"], ["result_key", "source_member_date"])


if __name__ == "__main__":
    unittest.main()
