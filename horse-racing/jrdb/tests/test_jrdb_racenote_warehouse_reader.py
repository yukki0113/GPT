#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import materialize_racenote_warehouse_assets as materializer  # noqa: E402
from jrdb_racenote_warehouse_reader import (  # noqa: E402
    WarehouseRaceNoteReader,
    WarehouseRaceNoteReaderError,
)
from jrdb_warehouse_normalize import normalize_record  # noqa: E402
from test_jrdb_raw_common import make_bac, make_kyi  # noqa: E402
from test_jrdb_warehouse_normalize import provenance, row  # noqa: E402


FAMILIES = ("BAC", "KYI", "CHA", "CYB", "ZED", "ZKB")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _warehouse(root: Path, *, assets: list[dict] | None = None) -> Path:
    generation = "jrdb_normalized_warehouse_v1_2010_2025_gtest"
    manifest_ref = f"generations/{generation}/manifest.json"
    manifest = {
        "status": "PASS",
        "generation_id": generation,
        "assets": assets or [],
    }
    manifest_path = root / manifest_ref
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    current = {
        "artifact_type": "jrdb_normalized_warehouse_current",
        "status": "accepted",
        "generation_id": generation,
        "manifest": manifest_ref,
        "manifest_sha256": _sha(manifest_path.read_bytes()),
    }
    current_path = root / "current.json"
    current_path.write_text(json.dumps(current), encoding="utf-8")
    return current_path


def _asset(family: str, year: int, relative: str, payload: bytes = b"parquet") -> dict:
    return {
        "family": family,
        "year": year,
        "relative_path": relative,
        "size_bytes": len(payload),
        "sha256": _sha(payload),
    }


class WarehouseRaceNoteReaderTest(unittest.TestCase):
    def test_accepted_current_and_missing_asset_fail_fast(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            item = _asset("BAC", 2018, "objects/bac_2018.parquet")
            current = _warehouse(root, assets=[item])
            asset_root = root / "BAC"
            target = asset_root / item["relative_path"]
            target.parent.mkdir(parents=True)
            target.write_bytes(b"parquet")
            reader = WarehouseRaceNoteReader(current, asset_roots={"BAC": asset_root})
            self.assertEqual(reader.manifest["status"], "PASS")
            self.assertEqual(reader._paths("bac", 2018), [target])
            target.unlink()
            with self.assertRaises(WarehouseRaceNoteReaderError):
                reader._paths("bac", 2018)

    def test_boundary_detection_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            current = _warehouse(Path(temp))
            reader = WarehouseRaceNoteReader(current, asset_roots={})
            kyi = normalize_record("KYI", make_kyi(), provenance())
            kyi["prev_result_key_1"] = "2023100120091227"
            with patch.object(reader, "_rows", return_value=[kyi]):
                self.assertEqual(reader.boundary_previous_keys(2010), ["2023100120091227"])

    def test_reader_reconstructs_semantics_and_previous_join(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            current = _warehouse(Path(temp), assets=[
                _asset("ZED", 2023, "objects/zed_2023.parquet"),
                _asset("ZKB", 2023, "objects/zkb_2023.parquet"),
            ])
            reader = WarehouseRaceNoteReader(current, asset_roots={})
            bac = normalize_record("BAC", make_bac(), provenance())
            bac["race_date"] = "2025-08-30"
            bac["field_size"] = 1
            kyi = normalize_record("KYI", make_kyi(), provenance())
            kyi["prev_result_key_1"] = "2023100120230810"
            kyi["prev_result_key_2"] = "2023100120230801"
            cha = normalize_record("CHA", row("CHA", (1, 8, "0526A101"), (9, 2, "03"), (13, 8, "20260829")), provenance())
            cyb = normalize_record("CYB", row("CYB", (1, 8, "0526A101"), (9, 2, "03"), (14, 2, "02"), (16, 2, "03")), provenance())

            def rows(relation: str, year: int):
                return {"bac": [bac], "kyi": [kyi], "cha": [cha], "cyb": [cyb], "zed": [], "zkb": []}[relation]

            with patch.object(reader, "_rows", side_effect=rows):
                bundles, audit = reader.build(__import__("datetime").date(2025, 8, 30))
            self.assertEqual(len(bundles), 1)
            self.assertEqual(audit["joins"]["cha_matched"], 1)
            self.assertEqual(audit["joins"]["cyb_matched"], 1)
            self.assertEqual(audit["previous_result_years"], [2023])


class WarehouseMaterializerTest(unittest.TestCase):
    def test_materializer_verifies_manifest_and_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            payload = b"immutable parquet payload"
            item = _asset("BAC", 2018, "objects/bac_2018.parquet", payload)
            current = _warehouse(source, assets=[item])
            manifest = source / json.loads(current.read_text())["manifest"]
            asset = source / "asset.parquet"
            asset.write_bytes(payload)
            destinations = {"current": current, "manifest": manifest, "asset": asset}

            def download(url: str, target: Path) -> None:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(destinations[url].read_bytes())

            argv = [
                "materialize", "--current-url", "current", "--manifest-url", "manifest",
                "--asset-url", "objects/bac_2018.parquet=asset", "--required-asset", "BAC=2018",
                "--output-root", str(root / "output"),
            ]
            with patch.object(sys, "argv", argv), patch.object(materializer, "drive_download", side_effect=download):
                self.assertEqual(materializer.main(), 0)
            report = json.loads((root / "output" / "materialization_report.json").read_text())
            self.assertEqual(report["status"], "PASS")
            self.assertEqual((root / "output" / "assets" / "BAC" / item["relative_path"]).read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()
