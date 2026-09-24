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
    build_time_standard,
    class_equivalent,
    day_track_adjustment_seconds,
    estimate_day_track_adjustment,
    normalized_time_delta_per_1000m,
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
