#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from jrdb_postrace_review_bias import (  # noqa: E402
    bias_corrected_performance,
    bias_direction,
    build_descriptive_track_bias,
    frame_bucket,
    leave_one_race_out_bias_estimate,
    performance_residual,
    preferred_lane_bucket,
    shrink_estimate,
    style_bucket,
    summarize_residuals,
    time_performance_signal,
)


class JrdbPostRaceReviewBiasTest(unittest.TestCase):
    def test_performance_residual_uses_high_is_better_sign(self) -> None:
        self.assertAlmostEqual(
            float(performance_residual(72.0, 70.5)),
            1.5,
        )
        self.assertAlmostEqual(
            float(performance_residual(68.0, 70.5)),
            -2.5,
        )
        self.assertIsNone(performance_residual(None, 70.5))

    def test_summarize_residuals(self) -> None:
        result = summarize_residuals([-0.4, -0.2, 0.1, None])

        self.assertEqual(result["sample_count"], 3)
        self.assertAlmostEqual(float(result["median_residual"]), -0.2)
        self.assertAlmostEqual(
            float(result["mean_residual"]),
            -0.5 / 3.0,
        )

    def test_shrink_estimate_requires_explicit_prior_strength(self) -> None:
        result = shrink_estimate(
            same_day_estimate=-0.6,
            same_day_sample_count=3,
            prior_estimate=-0.1,
            prior_strength=7,
        )

        self.assertAlmostEqual(float(result["same_day_weight"]), 0.3)
        self.assertAlmostEqual(float(result["prior_weight"]), 0.7)
        self.assertAlmostEqual(float(result["shrunk_estimate"]), -0.25)

    def test_shrink_estimate_handles_missing_day(self) -> None:
        result = shrink_estimate(
            same_day_estimate=None,
            same_day_sample_count=0,
            prior_estimate=0.2,
            prior_strength=5,
        )

        self.assertAlmostEqual(float(result["shrunk_estimate"]), 0.2)
        self.assertAlmostEqual(float(result["same_day_weight"]), 0.0)
        self.assertAlmostEqual(float(result["prior_weight"]), 1.0)

    def test_bias_direction_needs_caller_neutral_band(self) -> None:
        self.assertEqual(bias_direction(-0.31, 0.10), "AGAINST")
        self.assertEqual(bias_direction(0.22, 0.10), "ASSISTED")
        self.assertEqual(bias_direction(0.05, 0.10), "NEUTRAL")
        self.assertIsNone(bias_direction(None, 0.10))

    def test_bias_correction_removes_bucket_effect(self) -> None:
        self.assertAlmostEqual(
            float(bias_corrected_performance(69.7, -0.3)),
            70.0,
        )
        self.assertAlmostEqual(
            float(bias_corrected_performance(70.4, 0.4)),
            70.0,
        )

    def test_descriptive_track_bias_keeps_raw_and_adjusted_layers(self) -> None:
        rows = [
            {
                "race_date": "2025-03-15",
                "venue_code": "05",
                "surface_code": "1",
                "race_key": "R1",
                "race_horse_key": "R101",
                "horse_adjusted_delta_per_1000m": 0.5,
                "last3f_sec": 35.5,
                "fourth_corner_lane_bucket": "INNER",
                "course_lane_bucket": "INNER",
                "race_running_style_code": "3",
                "frame_no": 1,
            },
            {
                "race_date": "2025-03-15",
                "venue_code": "05",
                "surface_code": "1",
                "race_key": "R2",
                "race_horse_key": "R201",
                "horse_adjusted_delta_per_1000m": 0.2,
                "last3f_sec": 35.2,
                "fourth_corner_lane_bucket": "INNER",
                "course_lane_bucket": "INNER",
                "race_running_style_code": "3",
                "frame_no": 1,
            },
            {
                "race_date": "2025-03-15",
                "venue_code": "05",
                "surface_code": "1",
                "race_key": "R2",
                "race_horse_key": "R202",
                "horse_adjusted_delta_per_1000m": -0.4,
                "last3f_sec": 34.8,
                "fourth_corner_lane_bucket": "OUTER",
                "course_lane_bucket": "OUTER",
                "race_running_style_code": "1",
                "frame_no": 8,
            },
        ]
        expected = {
            "R101": -0.4,
            "R201": -0.1,
            "R202": 0.2,
        }

        table = build_descriptive_track_bias(rows, expected)
        inner = next(
            row
            for row in table
            if row["bias_dimension"] == "lane"
            and row["bias_bucket"] == "INNER"
        )
        outer = next(
            row
            for row in table
            if row["bias_dimension"] == "lane"
            and row["bias_bucket"] == "OUTER"
        )

        self.assertEqual(inner["same_day_sample_count"], 2)
        self.assertAlmostEqual(
            float(inner["raw_time_performance_median"]),
            -0.35,
        )
        self.assertAlmostEqual(
            float(inner["adjusted_performance_residual"]),
            -0.1,
        )
        self.assertAlmostEqual(
            float(outer["adjusted_performance_residual"]),
            0.2,
        )

        loo = leave_one_race_out_bias_estimate(
            rows,
            target_race_key="R1",
            dimension="lane",
            bucket="INNER",
            expected_performance_by_horse=expected,
            prior_estimate=-0.05,
            prior_strength=3,
        )
        self.assertEqual(loo["loo_sample_count"], 1)
        self.assertAlmostEqual(
            float(loo["shrunk_bias_score"]),
            -0.0625,
        )

    def test_style_and_time_signal_keep_explicit_sign(self) -> None:
        self.assertEqual(style_bucket("1"), "STYLE_1")
        self.assertEqual(style_bucket(6), "STYLE_6")
        self.assertIsNone(style_bucket(7))
        self.assertAlmostEqual(float(time_performance_signal(-0.4)), 0.4)
        self.assertAlmostEqual(float(time_performance_signal(0.4)), -0.4)

    def test_frame_and_lane_buckets_preserve_observed_categories(self) -> None:
        self.assertEqual(frame_bucket(1), "FRAME_1")
        self.assertEqual(frame_bucket(8), "FRAME_8")
        self.assertIsNone(frame_bucket(9))

        self.assertEqual(
            preferred_lane_bucket("INNER", "OUTER"),
            "INNER",
        )
        self.assertEqual(
            preferred_lane_bucket(None, "OUTER"),
            "OUTER",
        )
        self.assertIsNone(preferred_lane_bucket(None, None))


if __name__ == "__main__":
    unittest.main()
