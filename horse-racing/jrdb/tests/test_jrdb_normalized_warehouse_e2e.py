#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""All-family fixture coverage for the frozen Raw Warehouse boundary."""
from __future__ import annotations

import hashlib
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
from jrdb_warehouse_normalize import normalize_hjc_record, normalize_record  # noqa: E402
from test_jrdb_hjc_common import sample_body  # noqa: E402
from test_jrdb_raw_common import make_bac, make_kyi, make_sed, make_skb, make_ukc  # noqa: E402
from test_jrdb_warehouse_normalize import provenance, row  # noqa: E402


def fixture_records() -> dict[str, bytes]:
    """One valid record for every frozen-Raw target family."""
    sed = make_sed("20231001", "20260830", "0526A101", "02")
    skb = make_skb()
    return {
        "BAC": make_bac(),
        "KYI": make_kyi(),
        "CHA": row("CHA", (1, 8, "0526A101"), (9, 2, "03"), (13, 8, "20260829")),
        "CYB": row("CYB", (1, 8, "0526A101"), (9, 2, "03"), (78, 8, "20260828")),
        "SED": sed,
        "SKB": skb,
        "ZED": sed,
        "ZKB": skb,
        "UKC": make_ukc(),
        "HJC": sample_body(),
    }


class AllFamilyNormalizerContractTest(unittest.TestCase):
    def test_all_families_are_normalized_deterministically_with_provenance(self) -> None:
        records = fixture_records()
        expected_grains = {
            "BAC": ("race_key_raw", "source_member_date"), "KYI": ("race_key_raw", "horse_no"),
            "CHA": ("race_horse_key", "source_member_date"), "CYB": ("race_horse_key",),
            "SED": ("race_key_raw", "horse_no"), "SKB": ("result_key",),
            "ZED": ("result_key", "source_member_date"),
            "ZKB": ("result_key", "source_member_date"),
            "UKC": ("horse_id", "data_date"),
        }
        for family, keys in expected_grains.items():
            first = normalize_record(family, records[family], provenance())
            second = normalize_record(family, records[family], provenance())
            self.assertEqual(first, second, family)
            self.assertEqual(tuple(first[column] for column in keys), tuple(second[column] for column in keys))
            self.assertEqual(first["source_record_sha256"], hashlib.sha256(records[family]).hexdigest())
            self.assertEqual(first["warehouse_schema_version"], "v1")

        race, payouts = normalize_hjc_record(records["HJC"], provenance())
        self.assertEqual(race["source_record_sha256"], hashlib.sha256(records["HJC"]).hexdigest())
        self.assertEqual(len(payouts), 36)
        self.assertEqual({item["bet_type"] for item in payouts}, {
            "win", "place", "frame_quinella", "quinella", "wide", "exacta", "trio", "trifecta",
        })


@unittest.skipUnless(storage_runtime_available(), "tools/data-storage Parquet runtime is not installed")
class AllFamilyWarehouseE2ETest(unittest.TestCase):
    def test_all_families_build_without_raw_mutation_or_current_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            specs: list[ArchiveSpec] = []
            before_hashes: dict[Path, str] = {}
            for family, body in fixture_records().items():
                archive = root / f"{family}_2026.zip"
                with zipfile.ZipFile(archive, "w") as zipped:
                    zipped.writestr(f"{family}260830.txt", body + b"\r\n")
                specs.append(ArchiveSpec(family, 2026, archive))
                before_hashes[archive] = hashlib.sha256(archive.read_bytes()).hexdigest()
            result = build_generation(specs, root / "warehouse", "all-family-e2e", "deadbeef", created_at="2026-09-18T00:00:00+00:00")
            self.assertEqual(result["manifest"]["status"], "PASS")
            self.assertEqual({asset["family"] for asset in result["manifest"]["assets"]}, {
                "bac", "kyi", "cha", "cyb", "sed", "skb", "zed", "zkb", "ukc",
                "ukc_source_record_lineage", "hjc_race", "hjc_payout",
            })
            self.assertEqual(next(asset for asset in result["manifest"]["assets"] if asset["family"] == "hjc_payout")["row_count"], 36)
            cross_family = result["audit"]["cross_family"]
            self.assertEqual(cross_family["status"], "PASS")
            self.assertTrue(all(item["passed"] for item in cross_family["checks"]))
            self.assertTrue(all(item["unmatched_child_key_count"] == 0 for item in cross_family["checks"]))
            self.assertFalse((root / "warehouse" / "current.json").exists())
            self.assertEqual({path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before_hashes}, before_hashes)


if __name__ == "__main__":
    unittest.main()
