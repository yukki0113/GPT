#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jrdb_raw import (  # noqa: E402
    BODY_LENGTHS,
    Parser,
    ReaderAudit,
    race_horse_key,
    race_key,
    race_key_parts,
    result_key,
    split_fixed_records,
)
from jrdb_raw_history import get_horse_runs, history_dates  # noqa: E402


def put(row: bytearray, start: int, width: int, value: str) -> None:
    encoded = str(value).encode("cp932")
    if len(encoded) > width:
        raise ValueError(value)
    offset = start - 1
    row[offset : offset + width] = encoded.ljust(width, b" ")


def blank(kind: str) -> bytearray:
    return bytearray(b" " * BODY_LENGTHS[kind])


def make_bac() -> bytes:
    row = blank("BAC")
    for start, width, value in (
        (1, 8, "0526A101"),
        (9, 8, "20260830"),
        (17, 4, "1540"),
        (21, 4, "1600"),
        (25, 1, "1"),
        (26, 1, "2"),
        (27, 1, "1"),
        (28, 2, "13"),
        (30, 2, "OP"),
        (32, 3, "500"),
        (35, 1, "4"),
        (36, 1, "3"),
        (37, 50, "テストレース"),
        (87, 8, "第2回"),
        (95, 2, "16"),
        (97, 1, "1"),
    ):
        put(row, start, width, value)
    return bytes(row)


def make_kyi() -> bytes:
    row = blank("KYI")
    for start, width, value in (
        (1, 8, "0526A101"),
        (9, 2, "03"),
        (11, 8, "20231001"),
        (19, 36, "テストホース"),
        (55, 5, "72.5"),
        (60, 5, "61.0"),
        (65, 5, "55.5"),
        (85, 5, "69.5"),
        (90, 1, "2"),
        (91, 1, "3"),
        (92, 1, "1"),
        (93, 3, "  2"),
        (145, 5, "12.3"),
        (150, 5, " 5.4"),
        (155, 1, "2"),
        (156, 1, "1"),
        (157, 4, "33.3"),
        (161, 3, "123"),
        (164, 2, "09"),
        (166, 1, "2"),
        (167, 2, "07"),
        (171, 1, "1"),
        (172, 12, "騎手名"),
        (184, 3, "570"),
        (188, 12, "調教師"),
        (200, 4, "美浦"),
        (204, 16, "2023100120260810"),
        (220, 16, "2023100120260801"),
        (284, 8, "0526A001"),
        (292, 8, "05269012"),
        (324, 1, "2"),
        (336, 5, "01234"),
        (341, 5, "54321"),
        (359, 5, "10.5"),
        (364, 5, "11.5"),
        (369, 5, "12.5"),
        (374, 5, "13.5"),
        (379, 1, "H"),
        (453, 2, "04"),
        (455, 2, "03"),
        (457, 2, "02"),
        (459, 2, "01"),
        (502, 3, "033"),
        (505, 3, "038"),
        (508, 3, "039"),
        (511, 3, "040"),
        (514, 3, "041"),
        (517, 3, "042"),
        (520, 4, "12.3"),
        (524, 4, " 5.5"),
        (542, 2, "01"),
        (573, 50, "テスト牧場"),
        (623, 1, "A"),
        (624, 1, "2"),
    ):
        put(row, start, width, value)
    return bytes(row)


def make_sed(horse_id: str, date: str, race_key_value: str, finish: str) -> bytes:
    row = blank("SED")
    for start, width, value in (
        (1, 8, race_key_value),
        (9, 2, "03"),
        (11, 8, horse_id),
        (19, 8, date),
        (27, 36, "テストホース"),
        (63, 4, "1600"),
        (67, 1, "1"),
        (68, 1, "2"),
        (69, 1, "1"),
        (70, 2, "10"),
        (72, 2, "13"),
        (74, 2, "OP"),
        (80, 1, "3"),
        (81, 50, "テストレース"),
        (131, 2, "16"),
        (141, 2, finish),
        (143, 1, "0"),
        (144, 4, "1325"),
        (148, 3, "570"),
        (151, 12, "騎手名"),
        (175, 6, "  3.5"),
        (181, 2, "02"),
        (183, 3, " 72"),
        (186, 3, " 68"),
        (189, 3, "-10"),
        (192, 3, "  5"),
        (195, 3, " -2"),
        (198, 3, "  1"),
        (201, 3, "  0"),
        (204, 3, "  1"),
        (207, 3, "  0"),
        (210, 3, " -1"),
        (213, 3, "  3"),
        (216, 1, "3"),
        (220, 1, "3"),
        (222, 1, "H"),
        (223, 1, "M"),
        (224, 5, "10.5"),
        (229, 5, "20.5"),
        (234, 5, "30.5"),
        (239, 5, "40.5"),
        (259, 3, "358"),
        (262, 3, "342"),
        (309, 2, "03"),
        (311, 2, "03"),
        (313, 2, "02"),
        (315, 2, "01"),
        (333, 3, "480"),
        (336, 3, "+04"),
        (339, 1, "1"),
    ):
        put(row, start, width, value)
    return bytes(row)


def make_skb() -> bytes:
    row = blank("SKB")
    put(row, 11, 8, "20231001")
    put(row, 19, 8, "20260830")
    put(row, 27, 3, "033")
    put(row, 45, 3, "001")
    put(row, 69, 3, "101")
    put(row, 114, 40, "パドックコメント")
    put(row, 234, 40, "レースコメント")
    return bytes(row)


def make_ukc() -> bytes:
    row = blank("UKC")
    for start, width, value in (
        (1, 8, "20231001"),
        (9, 36, "テストホース"),
        (45, 1, "1"),
        (50, 36, "テスト父"),
        (86, 36, "テスト母"),
        (122, 36, "テスト母父"),
        (158, 8, "20230301"),
        (166, 4, "2010"),
        (170, 4, "2012"),
        (174, 4, "2008"),
        (220, 40, "生産者"),
        (260, 8, "北海道"),
        (269, 8, "20260829"),
        (277, 4, "1001"),
        (281, 4, "2001"),
    ):
        put(row, start, width, value)
    return bytes(row)


class CommonRawReaderTest(unittest.TestCase):
    def test_keys_preserve_hex_capable_day(self) -> None:
        record = make_kyi()
        self.assertEqual(race_key(record), "0526A101")
        self.assertEqual(race_horse_key(record), "0526A10103")
        self.assertEqual(race_key_parts("0526AA01")["day_raw"], "A")

    def test_bac_and_kyi_offsets_follow_published_spec(self) -> None:
        parser = Parser()
        bac = parser.bac(make_bac())
        kyi = parser.kyi(make_kyi())
        self.assertEqual(bac["date_raw"], "20260830")
        self.assertEqual(bac["race_name"], "テストレース")
        self.assertEqual(bac["field_size"], 16)
        self.assertEqual(kyi["horse_name"], "テストホース")
        self.assertEqual(kyi["previous"][0]["result_key"], "2023100120260810")
        self.assertEqual(kyi["previous"][1]["race_key_raw"], "05269012")
        self.assertEqual(kyi["pace_indices"]["late"], 12.5)
        self.assertEqual(kyi["pace_ranks"]["position"], 1)
        self.assertEqual(kyi["trait_codes"][0], "033")

    def test_sed_zed_and_skb_zkb_aliases_are_exact(self) -> None:
        parser = Parser()
        sed_record = make_sed("20231001", "20260830", "0526A101", "01")
        skb_record = make_skb()
        self.assertEqual(parser.sed(sed_record), parser.zed(sed_record))
        self.assertEqual(parser.skb(skb_record), parser.zkb(skb_record))
        self.assertEqual(result_key(sed_record), "2023100120260830")
        self.assertEqual(parser.sed(sed_record)["metrics"]["track_diff"], -10)
        self.assertEqual(parser.sed(sed_record)["body_weight_change_kg"], 4)

    def test_ukc_uses_validated_common_profile_parser(self) -> None:
        parsed = Parser().ukc(make_ukc())
        self.assertEqual(parsed["horse_id"], "20231001")
        self.assertEqual(parsed["horse_name"], "テストホース")
        self.assertEqual(parsed["sire_name"], "テスト父")
        self.assertEqual(parsed["sire_birth_year"], 2010)

    def test_split_accepts_paci_and_annual_shapes(self) -> None:
        body = make_bac()
        paci_blob = body + b"\r\n" + body + b"\r\n"
        annual_blob = body + b"\n" + body + b"\n"
        self.assertEqual(len(split_fixed_records(paci_blob, "BAC")), 2)
        self.assertEqual(len(split_fixed_records(annual_blob, "BAC")), 2)

    def test_malformed_record_length_is_audited(self) -> None:
        audit = ReaderAudit()
        self.assertEqual(split_fixed_records(b"broken", "BAC", audit), [])
        self.assertEqual(audit.record_length_errors["BAC"], 1)

    def test_cross_year_history_is_before_exclusive_and_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sed_dir = root / "SED"
            sed_dir.mkdir()
            horse_id = "20231001"
            rows = {
                2024: [
                    ("20241201", "05248001", "03"),
                    ("20240601", "05244001", "02"),
                ],
                2023: [("20231201", "05238001", "01")],
            }
            for year, items in rows.items():
                archive = sed_dir / f"SED_{year}.zip"
                with zipfile.ZipFile(archive, "w") as zf:
                    for date, key, finish in items:
                        zf.writestr(
                            f"SED{date[2:]}.txt",
                            make_sed(horse_id, date, key, finish) + b"\r\n",
                        )

            runs = get_horse_runs(
                root,
                horse_id,
                before="2024-12-01",
                limit=2,
                start_year=2023,
                end_year=2024,
            )
            self.assertEqual(history_dates(runs), ["2024-06-01", "2023-12-01"])
            self.assertEqual(runs[0].source.year, 2024)


if __name__ == "__main__":
    unittest.main()
