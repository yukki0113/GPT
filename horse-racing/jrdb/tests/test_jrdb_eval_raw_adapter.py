from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jrdb_eval_raw_adapter import (  # noqa: E402
    parse_bac_eval,
    parse_sed_horse_eval,
    parse_sed_race_eval,
)
from jrdb_raw import BODY_LENGTHS  # noqa: E402


def put(row: bytearray, offset: int, width: int, value: str) -> None:
    encoded = value.encode("cp932")
    if len(encoded) > width:
        raise ValueError(value)
    row[offset : offset + width] = encoded.ljust(width, b" ")


def text(raw: bytes, offset: int, width: int) -> str:
    return raw[offset : offset + width].decode("cp932", "replace").strip()


def number(raw: bytes, offset: int, width: int) -> int | None:
    value = text(raw, offset, width)
    if not value:
        return None
    return int(value)


class EvalRawAdapterTest(unittest.TestCase):
    def test_bac_projection_matches_legacy_offsets(self) -> None:
        row = bytearray(b" " * BODY_LENGTHS["BAC"])
        put(row, 0, 8, "06245911")
        put(row, 8, 8, "20241228")
        put(row, 20, 4, "2000")
        put(row, 24, 1, "1")
        put(row, 25, 1, "1")
        put(row, 26, 1, "2")
        put(row, 27, 2, "13")
        put(row, 29, 2, "OP")
        put(row, 31, 3, "020")
        put(row, 34, 1, "4")
        put(row, 35, 1, "1")
        put(row, 36, 50, "TEST RACE")
        put(row, 94, 2, "18")
        put(row, 96, 1, "3")
        put(row, 97, 1, "1")
        raw = bytes(row)
        expected = {
            "race_date": "2024-12-28",
            "venue_code": text(raw, 0, 2),
            "race_no": number(raw, 6, 2),
            "race_name": text(raw, 36, 50),
            "race_type_code": text(raw, 27, 2),
            "race_condition_code": text(raw, 29, 2),
            "race_symbol_code": text(raw, 31, 3),
            "weight_condition_code": text(raw, 34, 1),
            "grade_code": text(raw, 35, 1),
            "track_type": text(raw, 24, 1),
            "distance": number(raw, 20, 4),
            "declared_field_size": number(raw, 94, 2),
            "turn_direction_code": text(raw, 25, 1),
            "inner_outer_code": text(raw, 26, 1),
            "course_code": text(raw, 96, 1),
            "event_region_code": text(raw, 97, 1),
        }
        self.assertEqual(expected, parse_bac_eval(raw))

    def test_sed_race_projection_matches_legacy_offsets(self) -> None:
        row = bytearray(b" " * BODY_LENGTHS["SED"])
        put(row, 0, 8, "06245911")
        put(row, 18, 8, "20241228")
        put(row, 62, 4, "2000")
        put(row, 66, 1, "1")
        put(row, 67, 1, "1")
        put(row, 68, 1, "2")
        put(row, 69, 2, "10")
        put(row, 71, 2, "13")
        put(row, 73, 2, "OP")
        put(row, 75, 3, "020")
        put(row, 78, 1, "4")
        put(row, 79, 1, "1")
        put(row, 80, 50, "TEST RACE")
        put(row, 130, 2, "18")
        raw = bytes(row)
        expected = {
            "race_date": "2024-12-28",
            "venue_code": text(raw, 0, 2),
            "race_no": number(raw, 6, 2),
            "race_name": text(raw, 80, 50),
            "race_type_code": text(raw, 71, 2),
            "race_condition_code": text(raw, 73, 2),
            "race_symbol_code": text(raw, 75, 3),
            "weight_condition_code": text(raw, 78, 1),
            "grade_code": text(raw, 79, 1),
            "track_type": text(raw, 66, 1),
            "distance": number(raw, 62, 4),
            "track_condition_code": text(raw, 69, 2),
            "declared_field_size": number(raw, 130, 2),
            "turn_direction_code": text(raw, 67, 1),
            "inner_outer_code": text(raw, 68, 1),
        }
        self.assertEqual(expected, parse_sed_race_eval(raw))

    def test_sed_horse_projection_matches_legacy_offsets(self) -> None:
        row = bytearray(b" " * BODY_LENGTHS["SED"])
        put(row, 0, 8, "06245911")
        put(row, 8, 2, "18")
        put(row, 10, 8, "17104128")
        put(row, 18, 8, "20241228")
        put(row, 26, 36, "TEST HORSE")
        put(row, 140, 2, "03")
        put(row, 142, 1, "0")
        put(row, 290, 6, "001230")
        put(row, 348, 7, "0000450")
        raw = bytes(row)
        actual = parse_sed_horse_eval(raw)
        self.assertEqual("2024-12-28", actual["race_date"])
        self.assertEqual(text(raw, 0, 2), actual["venue_code"])
        self.assertEqual(number(raw, 6, 2), actual["race_no"])
        self.assertEqual(number(raw, 8, 2), actual["horse_no"])
        self.assertEqual(text(raw, 26, 36), actual["horse_name"])
        self.assertEqual(text(raw, 10, 8), actual["blood_registration_no"])
        self.assertEqual(number(raw, 140, 2), actual["finish_position"])
        self.assertEqual(text(raw, 142, 1), actual["abnormality_code"])
        self.assertEqual(format(Decimal(text(raw, 290, 6)), "f"), actual["final_place_odds_lower"])
        self.assertEqual(number(raw, 348, 7), actual["place_payout"])


if __name__ == "__main__":
    unittest.main()
