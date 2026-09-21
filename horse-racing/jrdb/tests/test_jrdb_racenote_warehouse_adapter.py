#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jrdb_raw import Parser  # noqa: E402
from jrdb_racenote_warehouse_adapter import (  # noqa: E402
    RaceNoteWarehouseError,
    out_of_warehouse_previous_keys,
    require_historical_year,
    select_raw_compatible_rows,
    unflatten_parser_row,
)
from jrdb_warehouse_normalize import normalize_record  # noqa: E402
from test_jrdb_raw_common import make_bac, make_kyi, make_sed, make_skb  # noqa: E402
from test_jrdb_warehouse_normalize import provenance, row  # noqa: E402


class RaceNoteWarehouseAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = Parser()

    def assert_roundtrip(self, family: str, record: bytes, parser_method: str | None = None) -> None:
        parser_method = parser_method or family.lower()
        expected = getattr(self.parser, parser_method)(record)
        normalized = normalize_record(family, record, provenance())
        actual = unflatten_parser_row(family, normalized)
        self.assertEqual(actual, expected)

    def test_bac_roundtrip(self) -> None:
        self.assert_roundtrip("BAC", make_bac())

    def test_kyi_roundtrip_restores_nested_parser_shape(self) -> None:
        self.assert_roundtrip("KYI", make_kyi())

    def test_cha_roundtrip_restores_clock_and_pair(self) -> None:
        record = row(
            "CHA",
            (1, 8, "0526A101"), (9, 2, "03"), (13, 8, "20260829"),
            (29, 3, "123"), (47, 3, "321"), (50, 1, "A"),
        )
        self.assert_roundtrip("CHA", record)

    def test_cyb_roundtrip_restores_course_counts(self) -> None:
        record = row(
            "CYB",
            (1, 8, "0526A101"), (9, 2, "03"), (14, 2, "02"),
            (16, 2, "03"), (78, 8, "20260828"),
        )
        self.assert_roundtrip("CYB", record)

    def test_sed_and_zed_roundtrip(self) -> None:
        record = make_sed("20231001", "20260830", "0526A101", "01")
        self.assert_roundtrip("SED", record)
        self.assert_roundtrip("ZED", record, parser_method="zed")

    def test_skb_and_zkb_roundtrip(self) -> None:
        record = make_skb()
        self.assert_roundtrip("SKB", record)
        self.assert_roundtrip("ZKB", record, parser_method="zkb")

    def test_bac_effective_snapshot_is_last_source_order(self) -> None:
        older = normalize_record("BAC", make_bac(), provenance())
        newer = dict(older)
        older["source_member"] = "BAC260101.txt"
        newer["source_member"] = "BAC260102.txt"
        newer["race_name"] = "訂正版"
        selected = select_raw_compatible_rows("BAC", [newer, older])
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["race_name"], "訂正版")

    def test_cha_effective_snapshot_is_first_source_order(self) -> None:
        record = row("CHA", (1, 8, "0526A101"), (9, 2, "03"), (13, 8, "20260829"))
        older = normalize_record("CHA", record, provenance())
        newer = dict(older)
        older["source_member"] = "CHA260101.txt"
        newer["source_member"] = "CHA260102.txt"
        newer["weekday"] = "X"
        selected = select_raw_compatible_rows("CHA", [newer, older])
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["weekday"], older["weekday"])

    def test_2010_previous_year_boundary_is_explicit(self) -> None:
        row_value = normalize_record("KYI", make_kyi(), provenance())
        row_value["prev_result_key_1"] = "2023100120091227"
        self.assertEqual(out_of_warehouse_previous_keys([row_value]), ["2023100120091227"])

    def test_historical_coverage_guard_rejects_2026(self) -> None:
        self.assertEqual(require_historical_year(2010), 2010)
        self.assertEqual(require_historical_year(2025), 2025)
        with self.assertRaises(RaceNoteWarehouseError):
            require_historical_year(2026)


if __name__ == "__main__":
    unittest.main()
