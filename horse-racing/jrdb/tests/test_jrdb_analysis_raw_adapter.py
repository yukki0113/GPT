from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jrdb_analysis_raw_adapter import (  # noqa: E402
    parse_bac,
    parse_cyb,
    parse_kyi,
    parse_sed,
    parse_ukc,
)
from jrdb_raw import BODY_LENGTHS  # noqa: E402


def put(row: bytearray, offset: int, width: int, value: str) -> None:
    encoded = value.encode("cp932")
    if len(encoded) > width:
        raise ValueError(value)
    row[offset : offset + width] = encoded.ljust(width, b" ")


def legacy_text(raw: bytes, offset: int, width: int) -> str:
    return raw[offset : offset + width].decode("cp932", "replace").strip()


def legacy_num(raw: bytes, offset: int, width: int) -> int | None:
    try:
        return int(legacy_text(raw, offset, width).replace(",", ""))
    except (TypeError, ValueError):
        return None


class AnalysisRawAdapterTest(unittest.TestCase):
    def test_bac_matches_legacy_projection(self) -> None:
        row = bytearray(b" " * BODY_LENGTHS["BAC"])
        put(row, 0, 8, "06245911")
        put(row, 20, 4, "2000")
        put(row, 24, 1, "1")
        put(row, 29, 2, "OP")
        put(row, 35, 1, "1")
        raw = bytes(row)
        expected = {
            "race_date": "2024-12-28",
            "year": 2024,
            "venue_code": legacy_text(raw, 0, 2),
            "race_no": legacy_num(raw, 6, 2),
            "distance": legacy_num(raw, 20, 4),
            "track_type": legacy_text(raw, 24, 1),
            "race_condition_code": legacy_text(raw, 29, 2),
            "track_condition_code": None,
            "grade_code": legacy_text(raw, 35, 1),
        }
        self.assertEqual(expected, parse_bac(raw, "2024-12-28", 2024))

    def test_kyi_matches_legacy_projection(self) -> None:
        row = bytearray(b" " * BODY_LENGTHS["KYI"])
        put(row, 0, 8, "06245911")
        put(row, 8, 2, "18")
        put(row, 10, 8, "17104128")
        put(row, 18, 36, "TEST HORSE")
        put(row, 89, 1, "3")
        put(row, 90, 1, "2")
        put(row, 91, 1, "1")
        put(row, 171, 12, "TEST JOCKEY")
        put(row, 203, 16, "1710412820241221")
        put(row, 283, 8, "06245810")
        put(row, 323, 1, "8")
        raw = bytes(row)
        key, actual = parse_kyi(raw)
        expected_key = (legacy_text(raw, 0, 8), legacy_num(raw, 8, 2))
        expected = {
            "frame_no": legacy_num(raw, 323, 1),
            "horse_id": legacy_text(raw, 10, 8),
            "horse_name": legacy_text(raw, 18, 36),
            "jockey_name": legacy_text(raw, 171, 12),
            "running_style": legacy_text(raw, 89, 1),
            "distance_aptitude": legacy_text(raw, 90, 1),
            "uptrend": legacy_text(raw, 91, 1),
            "prev_result_key_1": legacy_text(raw, 203, 16) or None,
            "prev_race_key_1": legacy_text(raw, 283, 8) or None,
        }
        self.assertEqual(expected_key, key)
        self.assertEqual(expected, actual)

    def test_sed_matches_legacy_projection(self) -> None:
        row = bytearray(b" " * BODY_LENGTHS["SED"])
        put(row, 0, 8, "06245911")
        put(row, 8, 2, "18")
        put(row, 62, 4, "2000")
        put(row, 66, 1, "1")
        put(row, 69, 2, "10")
        put(row, 140, 2, "03")
        put(row, 142, 1, "0")
        put(row, 174, 6, "012340")
        put(row, 180, 2, "05")
        put(row, 341, 7, "0012300")
        put(row, 348, 7, "0000450")
        raw = bytes(row)
        key, result, fallback = parse_sed(raw, "2024-12-28", 2024)
        self.assertEqual((legacy_text(raw, 0, 8), legacy_num(raw, 8, 2)), key)
        self.assertEqual(
            {
                "finish": legacy_num(raw, 140, 2),
                "abnormal_code": legacy_text(raw, 142, 1),
                "final_win_odds": legacy_num(raw, 174, 6),
                "final_win_popularity": legacy_num(raw, 180, 2),
                "win_payout": legacy_num(raw, 341, 7),
                "place_payout": legacy_num(raw, 348, 7),
            },
            result,
        )
        self.assertEqual(
            {
                "race_date": "2024-12-28",
                "year": 2024,
                "venue_code": legacy_text(raw, 0, 2),
                "race_no": legacy_num(raw, 6, 2),
                "distance": legacy_num(raw, 62, 4),
                "track_type": legacy_text(raw, 66, 1),
                "race_condition_code": None,
                "track_condition_code": legacy_text(raw, 69, 2),
                "grade_code": None,
            },
            fallback,
        )

    def test_cyb_matches_legacy_projection(self) -> None:
        row = bytearray(b" " * BODY_LENGTHS["CYB"])
        put(row, 0, 8, "06245911")
        put(row, 8, 2, "18")
        put(row, 29, 3, "123")
        raw = bytes(row)
        key, value = parse_cyb(raw)
        self.assertEqual((legacy_text(raw, 0, 8), legacy_num(raw, 8, 2)), key)
        self.assertEqual(legacy_num(raw, 29, 3), value)

    def test_ukc_matches_legacy_projection(self) -> None:
        row = bytearray(b" " * BODY_LENGTHS["UKC"])
        put(row, 0, 8, "17104128")
        put(row, 8, 36, "TEST HORSE")
        put(row, 44, 1, "1")
        put(row, 49, 36, "TEST SIRE")
        put(row, 121, 36, "TEST BMS")
        put(row, 157, 8, "20170101")
        put(row, 268, 8, "20241228")
        put(row, 276, 4, "1234")
        put(row, 280, 4, "5678")
        raw = bytes(row)
        horse_id, profile = parse_ukc(raw)
        self.assertEqual(legacy_text(raw, 0, 8), horse_id)
        self.assertEqual(
            {
                "sex_code": legacy_text(raw, 44, 1),
                "birth_year": 2017,
                "sire_name": legacy_text(raw, 49, 36),
                "broodmare_sire_name": legacy_text(raw, 121, 36),
                "sire_line_code": legacy_text(raw, 276, 4),
                "broodmare_sire_line_code": legacy_text(raw, 280, 4),
                "data_date": legacy_text(raw, 268, 8),
            },
            profile,
        )


if __name__ == "__main__":
    unittest.main()
