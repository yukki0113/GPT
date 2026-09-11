#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from training_edge_v0_2_core import (  # noqa: E402
    B_CATEGORICAL,
    B_NUMERIC,
    CAB_CATEGORICAL,
    CAB_NUMERIC,
    C_CATEGORICAL,
    C_NUMERIC,
    EXCLUDED_CORE_FIELDS,
    VERSION,
    load_calibration,
    rest_bucket,
    training_edge_direction,
    training_edge_percentile,
    training_edge_raw,
)


class TrainingEdgeV02CoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calibration_path = ROOT / "config" / "training_edge_v0_2_calibration.json"
        self.calibration = load_calibration(self.calibration_path)

    def test_version_and_calibration_identity(self) -> None:
        self.assertEqual(VERSION, "0.2-dev-20260911")
        self.assertEqual(self.calibration["version"], VERSION)
        self.assertEqual(self.calibration["schema"], "training-edge-v0.2-calibration")

    def test_rest_bucket_boundaries(self) -> None:
        self.assertEqual(rest_bucket(None), "missing")
        self.assertEqual(rest_bucket(20), "<=20")
        self.assertEqual(rest_bucket(21), "21-34")
        self.assertEqual(rest_bucket(34), "21-34")
        self.assertEqual(rest_bucket(35), "35-62")
        self.assertEqual(rest_bucket(62), "35-62")
        self.assertEqual(rest_bucket(63), "63-119")
        self.assertEqual(rest_bucket(119), "63-119")
        self.assertEqual(rest_bucket(120), "120+")

    def test_raw_edge_and_direction(self) -> None:
        self.assertAlmostEqual(training_edge_raw(0.10, 0.12), 0.02)
        self.assertEqual(training_edge_direction(0.02), "positive")
        self.assertEqual(training_edge_direction(-0.02), "negative")
        self.assertEqual(training_edge_direction(0.0), "neutral")

    def test_percentile_knots_and_zero_location(self) -> None:
        median_raw = float(self.calibration["percentile_knots"]["50"])
        p90_raw = float(self.calibration["percentile_knots"]["90"])
        self.assertAlmostEqual(training_edge_percentile(median_raw, self.calibration), 50.0, places=8)
        self.assertAlmostEqual(training_edge_percentile(p90_raw, self.calibration), 90.0, places=8)

        zero_percentile = training_edge_percentile(0.0, self.calibration)
        self.assertGreater(zero_percentile, 53.0)
        self.assertLess(zero_percentile, 54.0)

    def test_percentile_clips_outside_observed_range(self) -> None:
        self.assertEqual(training_edge_percentile(-999.0, self.calibration), 0.0)
        self.assertEqual(training_edge_percentile(999.0, self.calibration), 100.0)

    def test_core_feature_boundary(self) -> None:
        all_core_fields = set(C_NUMERIC)
        all_core_fields.update(C_CATEGORICAL)
        all_core_fields.update(CAB_NUMERIC)
        all_core_fields.update(CAB_CATEGORICAL)

        for excluded in EXCLUDED_CORE_FIELDS:
            self.assertNotIn(excluded, all_core_fields)

        self.assertIn("final_self_pct", CAB_NUMERIC)
        self.assertIn("rest_bucket", CAB_CATEGORICAL)
        self.assertIn("course_x_rest", B_CATEGORICAL)
        self.assertIn("return_after_120d_break", B_NUMERIC)


if __name__ == "__main__":
    unittest.main()
