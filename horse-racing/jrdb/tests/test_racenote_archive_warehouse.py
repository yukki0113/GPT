#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_racenote_archive as archive_builder  # noqa: E402
import build_racenote_archive_month_from_warehouse as warehouse_builder  # noqa: E402
from test_jrdb_raw_common import make_sed  # noqa: E402


class WarehouseArchiveBuilderTest(unittest.TestCase):
    def test_archive_accepts_explicit_warehouse_source_mode(self) -> None:
        self.assertIn("warehouse", archive_builder.SOURCE_MODES)

    def test_asset_roots_require_the_six_racenote_relations(self) -> None:
        with self.assertRaises(warehouse_builder.WarehouseMonthBuildError):
            warehouse_builder.parse_asset_roots(["BAC=/tmp/bac"])
        roots = warehouse_builder.parse_asset_roots([
            "BAC=/tmp/bac", "KYI=/tmp/kyi", "CHA=/tmp/cha", "CYB=/tmp/cyb",
            "ZED=/tmp/zed", "ZKB=/tmp/zkb",
        ])
        self.assertEqual(set(roots), {"BAC", "KYI", "CHA", "CYB", "ZED", "ZKB"})

    def test_2026_fails_before_any_warehouse_or_raw_read(self) -> None:
        args = argparse.Namespace(
            target_month="202601", analysis=Path("not-used.sqlite"), warehouse_current=Path("not-used.json"),
            warehouse_asset_root=[], work_dir=Path("not-used"), archive_output=Path("not-used.sqlite"),
            converter_git_sha="abcdef0", source_ref=None, boundary_raw_dir=None, validation_report=None, summary=None,
        )
        with self.assertRaises(warehouse_builder.WarehouseMonthBuildError):
            warehouse_builder.build(args)

    def test_boundary_loader_reads_only_requested_zed_records(self) -> None:
        key = "2023100120091227"
        record = make_sed("20231001", "20091227", "0526A101", "01")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for family in ("ZED", "ZKB"):
                path = root / family / f"{family}_2009.zip"
                path.parent.mkdir(parents=True)
                with zipfile.ZipFile(path, "w") as output:
                    output.writestr(f"{family}091227.txt", record + b"\r\n")
            rows, sources = warehouse_builder.load_boundary_history(root, {key})
        self.assertIn("ZED", rows)
        self.assertEqual(len(sources), 2)
        self.assertTrue(all("sha256" in source for source in sources))


if __name__ == "__main__":
    unittest.main()
