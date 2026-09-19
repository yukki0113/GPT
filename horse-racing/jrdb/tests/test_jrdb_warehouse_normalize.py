#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jrdb_raw import BODY_LENGTHS  # noqa: E402
from jrdb_warehouse_normalize import (  # noqa: E402
    CANONICAL_KEYS,
    PROVENANCE_COLUMNS,
    RawProvenance,
    canonical_key_columns,
    normalize_hjc_record,
    normalize_record,
)
from test_jrdb_hjc_common import sample_body  # noqa: E402


def put(row: bytearray, start: int, width: int, value: str) -> None:
    encoded = value.encode("cp932")
    if len(encoded) > width:
        raise ValueError(value)
    row[start - 1 : start - 1 + width] = encoded.ljust(width, b" ")


def row(kind: str, *fields: tuple[int, int, str]) -> bytes:
    value = bytearray(b" " * BODY_LENGTHS[kind])
    for field in fields:
        put(value, *field)
    return bytes(value)


def provenance() -> RawProvenance:
    return RawProvenance(
        source_archive_name="BAC_2026.zip",
        source_archive_sha256="a" * 64,
        source_member="BAC260830.txt",
        source_member_date="2026-08-30",
        source_record_ordinal=7,
        source_member_sha256="b" * 64,
        warehouse_ingested_at="2026-09-18T00:00:00+00:00",
    )


class WarehouseNormalizeTest(unittest.TestCase):
    def test_bac_preserves_raw_codes_and_adds_only_safe_normalizations(self) -> None:
        source = row(
            "BAC", (1, 8, "0526A101"), (9, 8, "20260830"), (17, 4, "1540"),
            (21, 4, "1600"), (25, 1, "1"), (30, 2, "OP"),
        )
        actual = normalize_record("bac", source, provenance())
        self.assertEqual(actual["race_key_raw"], "0526A101")
        self.assertEqual(actual["day_raw"], "1")
        self.assertEqual(actual["race_class_code"], "OP")
        self.assertEqual(actual["race_date"], "2026-08-30")
        self.assertEqual(actual["post_time"], "15:40")
        self.assertEqual(actual["source_record_sha256"], hashlib.sha256(source).hexdigest())
        self.assertTrue(all(column in actual for column in PROVENANCE_COLUMNS))

    def test_kyi_flattens_parser_nested_fields_without_offset_logic(self) -> None:
        source = row(
            "KYI", (1, 8, "0526A101"), (9, 2, "03"), (204, 16, "2023100120260810"),
            (284, 8, "0526A001"), (327, 1, "A"), (359, 5, "10.5"),
            (453, 2, "04"), (502, 3, "033"), (562, 8, "20260801"),
        )
        actual = normalize_record("KYI", source, provenance())
        self.assertEqual(actual["horse_no"], 3)
        self.assertEqual(actual["prev_result_key_1"], "2023100120260810")
        self.assertEqual(actual["prev_race_key_1"], "0526A001")
        self.assertEqual(actual["mark_total"], "A")
        self.assertEqual(actual["pace_index_front"], 10.5)
        self.assertEqual(actual["pace_rank_front"], 4)
        self.assertEqual(actual["trait_code_1"], "033")
        self.assertEqual(actual["stable_entry_date"], "2026-08-01")
        self.assertNotIn("previous", actual)

    def test_cha_and_cyb_flatten_nested_parser_shapes(self) -> None:
        cha = normalize_record(
            "CHA",
            row("CHA", (1, 8, "0526A101"), (9, 2, "03"), (13, 8, "20260829"), (29, 3, "123"), (47, 3, "321"), (50, 1, "A")),
            provenance(),
        )
        cyb = normalize_record(
            "CYB",
            row("CYB", (1, 8, "0526A101"), (9, 2, "03"), (14, 2, "02"), (16, 2, "03"), (78, 8, "20260828")),
            provenance(),
        )
        self.assertEqual(cha["race_horse_key"], "0526A10103")
        self.assertEqual(cha["clock_front"], 12.3)
        self.assertEqual(cha["clock_index_total"], 321)
        self.assertEqual(cha["pair_result_code"], "A")
        self.assertEqual(cha["workout_date"], "2026-08-29")
        self.assertEqual(cyb["course_count_slope"], 2)
        self.assertEqual(cyb["course_count_wood"], 3)
        self.assertEqual(cyb["comment_date"], "2026-08-28")

    def test_sed_and_zed_keep_alias_semantics_but_their_own_grains(self) -> None:
        source = row(
            "SED", (1, 8, "0526A101"), (9, 2, "03"), (11, 8, "20231001"),
            (19, 8, "20260830"), (141, 2, "02"), (186, 3, " 68"),
            (309, 2, "03"), (371, 4, "1540"),
        )
        sed = normalize_record("SED", source, provenance())
        zed = normalize_record("ZED", source, provenance())
        self.assertEqual(sed["result_key"], "2023100120260830")
        self.assertEqual(sed["metric_raw_score"], 68)
        self.assertEqual(sed["corner_1"], 3)
        self.assertEqual(sed["race_date"], "2026-08-30")
        self.assertEqual(sed["start_time"], "15:40")
        self.assertEqual(sed["metric_raw_score"], zed["metric_raw_score"])
        self.assertEqual(canonical_key_columns("SED"), ("race_key_raw", "horse_no"))
        self.assertEqual(canonical_key_columns("ZED"), ("result_key", "source_member_date"))

    def test_skb_and_zkb_flatten_codes_and_preserve_blank_slots(self) -> None:
        source = row(
            "SKB", (11, 8, "20231001"), (19, 8, "20260830"), (27, 3, "033"),
            (45, 3, "001"), (69, 3, "101"), (78, 3, "102"),
        )
        skb = normalize_record("SKB", source, provenance())
        zkb = normalize_record("ZKB", source, provenance())
        self.assertEqual(skb["result_key"], "2023100120260830")
        self.assertEqual(skb["tokki_code_1"], "033")
        self.assertEqual(skb["tokki_code_2"], "")
        self.assertEqual(skb["equipment_code_1"], "001")
        self.assertEqual(skb["leg_code_overall"], "101")
        self.assertEqual(skb["leg_code_left_front"], "102")
        self.assertEqual(skb["result_date"], "2026-08-30")
        self.assertEqual(skb["tokki_code_1"], zkb["tokki_code_1"])
        self.assertEqual(canonical_key_columns("ZKB"), ("result_key", "source_member_date"))

    def test_ukc_preserves_each_snapshot_key_without_latest_only_collapse(self) -> None:
        source = row(
            "UKC", (1, 8, "20231001"), (9, 36, "テストホース"), (45, 1, "1"),
            (158, 8, "20230301"), (166, 4, "2010"), (269, 8, "20260829"),
        )
        actual = normalize_record("UKC", source, provenance())
        self.assertEqual(actual["horse_id"], "20231001")
        self.assertEqual(actual["data_date"], "20260829")
        self.assertEqual(actual["data_date_iso"], "2026-08-29")
        self.assertEqual(actual["birth_date_iso"], "2023-03-01")
        self.assertIn("semantic_hash", actual)
        self.assertEqual(canonical_key_columns("UKC"), ("horse_id", "data_date"))

    def test_hjc_emits_race_and_all_payout_slots_with_shared_provenance(self) -> None:
        source = sample_body()
        race, payouts = normalize_hjc_record(source, provenance())
        self.assertEqual(race["race_key_raw"], "06244901")
        self.assertEqual(race["source_record_sha256"], hashlib.sha256(source).hexdigest())
        self.assertEqual(len(payouts), 36)
        self.assertEqual(payouts[0]["bet_type"], "win")
        self.assertEqual(payouts[0]["slot_no"], 1)
        self.assertEqual(payouts[0]["combination_raw"], "04")
        self.assertEqual(payouts[0]["horse_no_1"], 4)
        self.assertEqual(payouts[0]["payout"], 750)
        blank_win = payouts[1]
        self.assertEqual(blank_win["slot_no"], 2)
        self.assertEqual(blank_win["combination_raw"], "00")
        self.assertEqual(blank_win["payout"], 0)
        trifecta = next(item for item in payouts if item["bet_type"] == "trifecta" and item["slot_no"] == 1)
        self.assertEqual((trifecta["horse_no_1"], trifecta["horse_no_2"], trifecta["horse_no_3"]), (4, 12, 15))
        self.assertEqual(trifecta["source_record_sha256"], race["source_record_sha256"])
        self.assertEqual(canonical_key_columns("HJC_RACE"), ("race_key_raw",))
        self.assertEqual(canonical_key_columns("HJC_PAYOUT"), ("race_key_raw", "bet_type", "slot_no"))

    def test_contract_rejects_unimplemented_family_and_invalid_ordinal(self) -> None:
        self.assertEqual(canonical_key_columns("BAC"), ("race_key_raw", "source_member_date"))
        self.assertEqual(canonical_key_columns("CHA"), ("race_horse_key", "source_member_date"))
        self.assertEqual(CANONICAL_KEYS["CYB"], ("race_horse_key",))
        with self.assertRaises(ValueError):
            canonical_key_columns("HJC")
        with self.assertRaises(ValueError):
            normalize_record("BAC", b"record", RawProvenance("x.zip", "x.txt", 0))


if __name__ == "__main__":
    unittest.main()
