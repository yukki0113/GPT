#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from jrdb_recommendation_signals import (  # noqa: E402
    OPERATIONAL_LOOKBACK_DAYS,
    PERFORMANCE_Q85,
    PERFORMANCE_Q90,
    VERSION,
    matched_signals,
    newspaper_comment,
    recommendation_payload,
)


def base_row() -> dict[str, object]:
    return {
        "finish": 3,
        "declared_class_group": "CLASS_1",
        "time_class_equivalent_numeric": 2.0,
        "time_class_equivalent": "CLASS_1",
        "horse_adjusted_delta_per_1000m": 0.5,
        "pace_balance_percentile": 50.0,
        "corner4_frontness": 0.5,
        "winner_gap_sec": 1.0,
        "last3f_speed_percentile": 50.0,
    }


class RecommendationSignalsTest(unittest.TestCase):
    def test_contract_has_two_year_operational_lookback(self) -> None:
        self.assertEqual(VERSION, "rrdb-recommendation-signals-v0.3")
        self.assertEqual(OPERATIONAL_LOOKBACK_DAYS, 730)

    def test_time_class_plus1(self) -> None:
        row = base_row()
        row["time_class_equivalent_numeric"] = 3.0
        self.assertEqual(matched_signals(row), ["TIME_CLASS_PLUS1"])

    def test_front_survive_gap05(self) -> None:
        row = base_row()
        row.update({
            "pace_balance_percentile": 82.0,
            "corner4_frontness": 0.75,
            "winner_gap_sec": 0.30,
        })
        self.assertEqual(matched_signals(row), ["FRONT_SURVIVE_GAP05"])

    def test_rear_high_last3f90(self) -> None:
        row = base_row()
        row.update({
            "pace_balance_percentile": 18.0,
            "corner4_frontness": 0.25,
            "last3f_speed_percentile": 98.0,
        })
        self.assertEqual(matched_signals(row), ["REAR_HIGH_LAST3F90"])

    def test_hv02_q85_q90_matches_only_narrow_band(self) -> None:
        row = base_row()
        row.update({
            "finish": 7,
            "horse_adjusted_delta_per_1000m": -0.10,
        })
        payload = recommendation_payload(row)
        self.assertEqual(payload["matched_signal_ids"], ["HV02_Q85_Q90"])
        self.assertEqual(payload["grade_status"], "DISABLED")
        self.assertIsNone(payload["grade"])

    def test_hv02_q85_q90_boundaries_and_finish_gate(self) -> None:
        row = base_row()
        row.update({"finish": 6, "performance_signal": PERFORMANCE_Q85})
        self.assertEqual(matched_signals(row), ["HV02_Q85_Q90"])

        row["performance_signal"] = PERFORMANCE_Q90
        self.assertEqual(matched_signals(row), [])

        row["performance_signal"] = (PERFORMANCE_Q85 + PERFORMANCE_Q90) / 2
        row["finish"] = 5
        self.assertEqual(matched_signals(row), [])

    def test_multiple_current_signals_do_not_create_grade(self) -> None:
        row = base_row()
        row.update({
            "finish": 6,
            "time_class_equivalent_numeric": 3.0,
            "time_class_equivalent": "CLASS_2",
            "horse_adjusted_delta_per_1000m": -0.10,
            "pace_balance_percentile": 90.0,
            "corner4_frontness": 0.90,
            "winner_gap_sec": 0.20,
        })
        payload = recommendation_payload(row)
        self.assertIn("TIME_CLASS_PLUS1", payload["matched_signal_ids"])
        self.assertIn("FRONT_SURVIVE_GAP05", payload["matched_signal_ids"])
        self.assertIsNone(payload["grade"])
        self.assertEqual(payload["grade_status"], "DISABLED")

    def test_newspaper_comment_hides_hv_code_and_avoids_duplicate_time_phrase(self) -> None:
        row = base_row()
        row.update({
            "finish": 7,
            "time_class_equivalent_numeric": 3.2,
            "time_class_equivalent": "CLASS_2",
            "horse_adjusted_delta_per_1000m": -0.10,
            "pace_balance_percentile": 85.0,
            "corner4_frontness": 0.75,
            "winner_gap_sec": 0.22,
        })
        comment = newspaper_comment(row)
        self.assertIsNotNone(comment)
        self.assertIn("前走時計はクラス水準より上。", comment)
        self.assertIn("前傾ラップ戦を前で受け、勝ち馬と僅差まで踏ん張った。", comment)
        self.assertNotIn("敗戦でもタイムは水準以上。", comment)
        self.assertNotIn("HV02_Q85_Q90", comment)

    def test_newspaper_hv02_q85_q90_comment(self) -> None:
        row = base_row()
        row.update({
            "finish": 10,
            "performance_signal": 0.11,
        })
        self.assertEqual(
            newspaper_comment(row),
            "敗戦でもタイムは水準以上。",
        )

    def test_newspaper_rear_comment_translates_percentile(self) -> None:
        row = base_row()
        row.update({
            "finish": 3,
            "pace_balance_percentile": 12.0,
            "corner4_frontness": 0.20,
            "winner_gap_sec": 0.31,
            "last3f_speed_percentile": 98.0,
        })
        self.assertEqual(
            newspaper_comment(row),
            "後傾ラップ戦も後方から上位の上がりは使った。",
        )

    def test_below_threshold_is_no_match(self) -> None:
        row = base_row()
        payload = recommendation_payload(row)
        self.assertEqual(payload["status"], "NO_MATCH")
        self.assertEqual(payload["matched_signal_ids"], [])


if __name__ == "__main__":
    unittest.main()
