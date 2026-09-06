from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jrdb_eval_horse_result_adapter import project_eval_horse_result  # noqa: E402
from jrdb_raw import BODY_LENGTHS  # noqa: E402

VENUES = {"06": "中山"}
ABNORMAL = {"0": "異常なし", "1": "取消", "2": "除外", "3": "中止", "4": "失格", "5": "降着", "6": "再騎乗"}


def put(row: bytearray, offset: int, width: int, value: str) -> None:
    encoded = value.encode("cp932")
    row[offset : offset + width] = encoded.ljust(width, b" ")


def sed_row(finish: str, abnormal: str) -> bytes:
    row = bytearray(b" " * BODY_LENGTHS["SED"])
    put(row, 0, 8, "06245911")
    put(row, 8, 2, "18")
    put(row, 10, 8, "17104128")
    put(row, 18, 8, "20241228")
    put(row, 26, 36, "TEST HORSE")
    put(row, 140, 2, finish)
    put(row, 142, 1, abnormal)
    put(row, 290, 6, "001230")
    put(row, 348, 7, "0000450")
    return bytes(row)


class EvalHorseResultAdapterTest(unittest.TestCase):
    def test_normal_top3_preserves_eval_policy(self) -> None:
        row = project_eval_horse_result(sed_row("03", "0"), VENUES, ABNORMAL)
        self.assertEqual("2024-12-28", row["race_date"])
        self.assertEqual("中山", row["venue_name"])
        self.assertEqual(3, row["finish_position_raw"])
        self.assertEqual(3, row["finish_position_eval"])
        self.assertEqual("○", row["in_top3"])
        self.assertEqual(0, row["review_required"])
        self.assertEqual(450, row["place_payout"])
        self.assertEqual("1230", row["final_place_odds_lower"])

    def test_abnormal_row_requires_review_and_does_not_autofill_finish(self) -> None:
        row = project_eval_horse_result(sed_row("00", "3"), VENUES, ABNORMAL)
        self.assertEqual(0, row["finish_position_raw"])
        self.assertEqual("", row["finish_position_eval"])
        self.assertEqual("", row["in_top3"])
        self.assertEqual(1, row["review_required"])
        self.assertIn("中止", row["review_reason"])


if __name__ == "__main__":
    unittest.main()
