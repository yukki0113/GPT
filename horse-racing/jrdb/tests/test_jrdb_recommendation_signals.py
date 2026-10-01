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
    PERFORMANCE_Q80,
    VERSION,
    matched_signals,
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
        self.assertEqual(VERSION, "rrdb-recommendation-signals-v0.2")
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

    def test_hv01_and_hv02_are_nested_but_do_not_create_grade(self) -> None:
        row = base_row()
        row.update({
            "finish": 7,
            "horse_adjusted_delta_per_1000m": -PERFORMANCE_Q80,
        })
        payload = recommendation_payload(row)
        self.assertEqual(payload["matched_signal_ids"], ["HV01", "HV02"])
        self.assertEqual(payload["grade_status"], "DISABLED")
        self.assertIsNone(payload["grade"])

    def test_multiple_current_signals_do_not_create_grade(self) -> None:
        row = base_row()
        row.update({
            "finish": 6,
            "time_class_equivalent_numeric": 3.0,
            "time_class_equivalent": "CLASS_2",
            "horse_adjusted_delta_per_1000m": 0.05,
            "pace_balance_percentile": 90.0,
            "corner4_frontness": 0.90,
            "winner_gap_sec": 0.20,
        })
        # Make performance_signal = -delta >= Q80.
        row["horse_adjusted_delta_per_1000m"] = 0.05
        payload = recommendation_payload(row)
        self.assertIn("TIME_CLASS_PLUS1", payload["matched_signal_ids"])
        self.assertIn("FRONT_SURVIVE_GAP05", payload["matched_signal_ids"])
        self.assertIsNone(payload["grade"])
        self.assertEqual(payload["grade_status"], "DISABLED")

    def test_below_threshold_is_no_match(self) -> None:
        row = base_row()
        payload = recommendation_payload(row)
        self.assertEqual(payload["status"], "NO_MATCH")
        self.assertEqual(payload["matched_signal_ids"], [])


if __name__ == "__main__":
    unittest.main()
