#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from jrdb_postrace_review_standard import (  # noqa: E402
    adjusted_standard_time_seconds,
    build_asof_class_standard_curve,
    build_time_standard,
    class_equivalent,
    day_track_adjustment_seconds,
    estimate_day_track_adjustment,
    leave_one_out_day_track_adjustments,
    normalized_time_delta_per_1000m,
    percentile_rank,
    select_asof_time_standard,
    standard_confidence,
)


class JrdbPostRaceReviewStandardTest(unittest.TestCase):
    def test_build_time_standard_uses_median(self) -> None:
        result = build_time_standard([95.0, 96.0, 94.0, 150.0, None])

        self.assertEqual(result["sample_count"], 4)
        self.assertAlmostEqual(float(result["median_winner_time_sec"]), 95.5)
        self.assertAlmostEqual(float(result["standard_time_sec"]), 95.5)
        self.assertEqual(result["standard_method"], "median")
        self.assertEqual(result["confidence"], "FALLBACK")

    def test_confidence_boundaries(self) -> None:
        self.assertEqual(standard_confidence(9), "FALLBACK")
        self.assertEqual(standard_confidence(10), "LOW")
        self.assertEqual(standard_confidence(30), "MEDIUM")
        self.assertEqual(standard_confidence(100), "HIGH")

    def test_select_asof_standard_excludes_future_and_keeps_class(self) -> None:
        samples = [
            {
                "race_date": "2023-03-05",
                "venue_code": "05",
                "surface_code": "1",
                "distance_m": 1600,
                "course_code": "1",
                "race_type_code": "12",
                "declared_class_group": "MAIDEN",
                "winner_time_sec": 95.8,
            },
            {
                "race_date": "2024-03-03",
                "venue_code": "05",
                "surface_code": "1",
                "distance_m": 1600,
                "course_code": "1",
                "race_type_code": "12",
                "declared_class_group": "MAIDEN",
                "winner_time_sec": 95.4,
            },
            {
                "race_date": "2024-03-24",
                "venue_code": "05",
                "surface_code": "1",
                "distance_m": 1600,
                "course_code": "1",
                "race_type_code": "12",
                "declared_class_group": "MAIDEN",
                "winner_time_sec": 95.2,
            },
            {
                "race_date": "2026-03-01",
                "venue_code": "05",
                "surface_code": "1",
                "distance_m": 1600,
                "course_code": "1",
                "race_type_code": "12",
                "declared_class_group": "MAIDEN",
                "winner_time_sec": 90.0,
            },
            {
                "race_date": "2024-03-10",
                "venue_code": "05",
                "surface_code": "1",
                "distance_m": 1600,
                "course_code": "1",
                "race_type_code": "12",
                "declared_class_group": "CLASS_1",
                "winner_time_sec": 94.0,
            },
        ]
        target = {
            "race_date": "2025-03-15",
            "venue_code": "05",
            "surface_code": "1",
            "distance_m": 1600,
            "course_code": "1",
            "race_type_code": "12",
            "declared_class_group": "MAIDEN",
        }

        result = select_asof_time_standard(
            samples,
            target,
            minimum_sample_count=3,
        )

        self.assertEqual(result["sample_count"], 3)
        self.assertEqual(result["scope_level"], 1)
        self.assertEqual(result["sample_end_date"], "2024-03-24")
        self.assertAlmostEqual(float(result["standard_time_sec"]), 95.4)

    def test_standard_falls_back_by_scope_not_adjacent_class(self) -> None:
        samples = [
            {
                "race_date": "2023-03-05",
                "venue_code": "05",
                "surface_code": "1",
                "distance_m": 1600,
                "course_code": "1",
                "race_type_code": "12",
                "declared_class_group": "MAIDEN",
                "winner_time_sec": 95.8,
            },
            {
                "race_date": "2024-03-03",
                "venue_code": "05",
                "surface_code": "1",
                "distance_m": 1600,
                "course_code": "1",
                "race_type_code": "12",
                "declared_class_group": "MAIDEN",
                "winner_time_sec": 95.4,
            },
            {
                "race_date": "2024-03-24",
                "venue_code": "05",
                "surface_code": "1",
                "distance_m": 1600,
                "course_code": "1",
                "race_type_code": "12",
                "declared_class_group": "MAIDEN",
                "winner_time_sec": 95.2,
            },
            {
                "race_date": "2024-03-10",
                "venue_code": "05",
                "surface_code": "1",
                "distance_m": 1600,
                "course_code": "1",
                "race_type_code": "12",
                "declared_class_group": "CLASS_1",
                "winner_time_sec": 94.0,
            },
        ]
        target = {
            "race_date": "2025-03-15",
            "venue_code": "05",
            "surface_code": "1",
            "distance_m": 1600,
            "course_code": "2",
            "race_type_code": "12",
            "declared_class_group": "MAIDEN",
        }

        result = select_asof_time_standard(
            samples,
            target,
            minimum_sample_count=3,
        )
        curve = build_asof_class_standard_curve(
            samples,
            target,
            minimum_sample_count=3,
        )

        self.assertEqual(result["scope_level"], 2)
        self.assertEqual(result["sample_count"], 3)
        self.assertEqual(curve["CLASS_1"]["sample_count"], 1)
        self.assertNotEqual(
            curve["CLASS_1"]["standard_time_sec"],
            curve["MAIDEN"]["standard_time_sec"],
        )

    def test_percentile_rank_is_high_for_larger_front_loaded_balance(self) -> None:
        self.assertAlmostEqual(percentile_rank([-1.0, 0.0, 1.0, 2.0], 1.5), 75.0)

    def test_normalized_day_adjustment(self) -> None:
        self.assertAlmostEqual(
            float(normalized_time_delta_per_1000m(95.0, 96.0, 1600)),
            -0.625,
        )

        result = estimate_day_track_adjustment(
            [
                {
                    "actual_time_sec": 95.0,
                    "standard_time_sec": 96.0,
                    "distance_m": 1600,
                },
                {
                    "actual_time_sec": 71.4,
                    "standard_time_sec": 72.0,
                    "distance_m": 1200,
                },
                {
                    "actual_time_sec": None,
                    "standard_time_sec": 120.0,
                    "distance_m": 2000,
                },
            ]
        )

        self.assertEqual(result["race_count"], 2)
        self.assertEqual(result["distance_count"], 2)
        self.assertAlmostEqual(
            float(result["adjustment_per_1000m_sec"]),
            -0.5625,
        )

    def test_leave_one_out_day_adjustment_excludes_target_race(self) -> None:
        races = [
            {
                "race_key": "R1",
                "actual_time_sec": 95.0,
                "standard_time_sec": 96.0,
                "distance_m": 1600,
            },
            {
                "race_key": "R2",
                "actual_time_sec": 71.4,
                "standard_time_sec": 72.0,
                "distance_m": 1200,
            },
            {
                "race_key": "R3",
                "actual_time_sec": 119.2,
                "standard_time_sec": 120.0,
                "distance_m": 2000,
            },
        ]

        result = leave_one_out_day_track_adjustments(races)

        self.assertEqual(result["R1"]["race_count"], 2)
        self.assertAlmostEqual(
            float(result["R1"]["adjustment_per_1000m_sec"]),
            -0.45,
        )
        self.assertAlmostEqual(
            float(result["R2"]["adjustment_per_1000m_sec"]),
            -0.5125,
        )
        self.assertAlmostEqual(
            float(result["R3"]["adjustment_per_1000m_sec"]),
            -0.5625,
        )

    def test_adjustment_scales_back_to_distance(self) -> None:
        day_sec = day_track_adjustment_seconds(-0.5, 1800)
        self.assertAlmostEqual(float(day_sec), -0.9)

        adjusted = adjusted_standard_time_seconds(108.0, day_sec)
        self.assertAlmostEqual(float(adjusted), 107.1)

    def test_class_equivalent_interpolates_monotonic_curve(self) -> None:
        result = class_equivalent(
            94.5,
            {
                "MAIDEN": 96.0,
                "CLASS_1": 95.0,
                "CLASS_2": 94.0,
                "CLASS_3": 93.0,
            },
        )

        self.assertEqual(result["equivalent_class_group"], "CLASS_1")
        self.assertTrue(result["curve_monotonic"])
        self.assertAlmostEqual(
            float(result["class_equivalent_numeric"]),
            2.5,
        )

    def test_class_equivalent_refuses_continuous_non_monotonic_curve(self) -> None:
        result = class_equivalent(
            94.5,
            {
                "MAIDEN": 96.0,
                "CLASS_1": 94.0,
                "CLASS_2": 94.2,
            },
        )

        self.assertFalse(result["curve_monotonic"])
        self.assertIsNone(result["class_equivalent_numeric"])
        self.assertEqual(result["equivalent_class_group"], "CLASS_2")


if __name__ == "__main__":
    unittest.main()
