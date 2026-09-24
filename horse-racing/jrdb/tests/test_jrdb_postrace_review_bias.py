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
    frame_bucket,
    performance_residual,
    preferred_lane_bucket,
    shrink_estimate,
    summarize_residuals,
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
