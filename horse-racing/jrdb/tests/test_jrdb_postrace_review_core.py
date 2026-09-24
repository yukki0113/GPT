#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from jrdb_postrace_review import (  # noqa: E402
    CLASS_1,
    CLASS_2,
    CLASS_3,
    CLASS_G1,
    CLASS_G2,
    CLASS_G3,
    CLASS_MAIDEN,
    CLASS_NEWCOMER,
    CLASS_OPEN,
    CLASS_OTHER,
    LANE_INNER,
    LANE_MIDDLE,
    LANE_OUTER,
    PACE_BACK_LOADED,
    PACE_BALANCED,
    PACE_FRONT_LOADED,
    PACE_VERY_BACK_LOADED,
    PACE_VERY_FRONT_LOADED,
    classify_pace_percentile,
    closing_gain_seconds,
    corner_frontness,
    finish_gap_seconds,
    frontness,
    lane_bucket,
    normalize_class_group,
    opening_reference_candidate_seconds,
    closing_reference_candidate_seconds,
    pace_balance_seconds,
    parse_sed_time_seconds,
    position_dynamics,
    position_gain,
)


class JrdbPostRaceReviewCoreTest(unittest.TestCase):
    def test_parse_sed_time_seconds(self) -> None:
        self.assertAlmostEqual(parse_sed_time_seconds("1123"), 72.3)
        self.assertAlmostEqual(parse_sed_time_seconds("0599"), 59.9)
        self.assertAlmostEqual(parse_sed_time_seconds("2000"), 120.0)

        self.assertIsNone(parse_sed_time_seconds(None))
        self.assertIsNone(parse_sed_time_seconds(""))
        self.assertIsNone(parse_sed_time_seconds("123"))
        self.assertIsNone(parse_sed_time_seconds("abcd"))
        self.assertIsNone(parse_sed_time_seconds("1600"))

    def test_normalize_class_group(self) -> None:
        self.assertEqual(normalize_class_group("A1"), CLASS_NEWCOMER)
        self.assertEqual(normalize_class_group("A2"), CLASS_NEWCOMER)
        self.assertEqual(normalize_class_group("A3"), CLASS_MAIDEN)
        self.assertEqual(normalize_class_group("04"), CLASS_1)
        self.assertEqual(normalize_class_group(5), CLASS_1)
        self.assertEqual(normalize_class_group("08"), CLASS_2)
        self.assertEqual(normalize_class_group("10"), CLASS_2)
        self.assertEqual(normalize_class_group("15"), CLASS_3)
        self.assertEqual(normalize_class_group("16"), CLASS_3)
        self.assertEqual(normalize_class_group("OP"), CLASS_OPEN)
        self.assertEqual(normalize_class_group("OP", "1"), CLASS_G1)
        self.assertEqual(normalize_class_group("OP", "2"), CLASS_G2)
        self.assertEqual(normalize_class_group("OP", "3"), CLASS_G3)
        self.assertEqual(normalize_class_group("XX"), CLASS_OTHER)

    def test_frontness_and_position_gain(self) -> None:
        self.assertAlmostEqual(frontness(1, 18), 1.0)
        self.assertAlmostEqual(frontness(18, 18), 0.0)
        self.assertAlmostEqual(frontness(9, 17), 0.5)
        self.assertIsNone(frontness(0, 18))
        self.assertIsNone(frontness(19, 18))
        self.assertIsNone(frontness(1, 1))

        gain = position_gain(8, 2, 10)
        self.assertIsNotNone(gain)
        self.assertAlmostEqual(float(gain), 6.0 / 9.0)

    def test_pace_balance_sign_and_percentile_labels(self) -> None:
        self.assertAlmostEqual(pace_balance_seconds(34.5, 35.8), 1.3)
        self.assertAlmostEqual(pace_balance_seconds(36.2, 34.9), -1.3)
        self.assertIsNone(pace_balance_seconds(None, 35.0))
        self.assertIsNone(pace_balance_seconds(0.0, 35.0))

        self.assertEqual(classify_pace_percentile(5), PACE_VERY_BACK_LOADED)
        self.assertEqual(classify_pace_percentile(20), PACE_BACK_LOADED)
        self.assertEqual(classify_pace_percentile(50), PACE_BALANCED)
        self.assertEqual(classify_pace_percentile(75), PACE_FRONT_LOADED)
        self.assertEqual(classify_pace_percentile(95), PACE_VERY_FRONT_LOADED)
        self.assertIsNone(classify_pace_percentile(-1))
        self.assertIsNone(classify_pace_percentile(101))

    def test_lane_bucket(self) -> None:
        self.assertEqual(lane_bucket(1), LANE_INNER)
        self.assertEqual(lane_bucket("2"), LANE_INNER)
        self.assertEqual(lane_bucket(3), LANE_MIDDLE)
        self.assertEqual(lane_bucket(4), LANE_OUTER)
        self.assertEqual(lane_bucket(5), LANE_OUTER)
        self.assertIsNone(lane_bucket(0))
        self.assertIsNone(lane_bucket(None))

    def test_finish_gap_and_closing_gain(self) -> None:
        self.assertAlmostEqual(finish_gap_seconds(95.3, 95.0), 0.3)
        self.assertAlmostEqual(finish_gap_seconds(95.0, 95.0), 0.0)
        self.assertIsNone(finish_gap_seconds(94.9, 95.0))

        self.assertAlmostEqual(closing_gain_seconds(1.2, 0.3), 0.9)
        self.assertAlmostEqual(closing_gain_seconds(0.3, 0.8), -0.5)
        self.assertIsNone(closing_gain_seconds(None, 0.3))
        self.assertIsNone(closing_gain_seconds(-0.1, 0.3))

    def test_race_sectional_reference_candidates(self) -> None:
        self.assertAlmostEqual(
            float(opening_reference_candidate_seconds(35.4, 0.8)),
            34.6,
        )
        self.assertAlmostEqual(
            float(closing_reference_candidate_seconds(34.2, 1.2, 0.3)),
            35.1,
        )
        self.assertIsNone(
            opening_reference_candidate_seconds(0.5, 0.8)
        )
        self.assertIsNone(
            closing_reference_candidate_seconds(34.2, -0.1, 0.3)
        )

    def test_corner_frontness_preserves_missing_values(self) -> None:
        values = corner_frontness([8, 2, None, 3], 10)
        self.assertAlmostEqual(float(values[0]), 2.0 / 9.0)
        self.assertAlmostEqual(float(values[1]), 8.0 / 9.0)
        self.assertIsNone(values[2])
        self.assertAlmostEqual(float(values[3]), 7.0 / 9.0)

    def test_position_dynamics_detects_early_recovery_and_late_fade(self) -> None:
        dynamics = position_dynamics([8, 2, 2, 3], 9, 10)

        self.assertAlmostEqual(
            float(dynamics["early_position_gain"]),
            6.0 / 9.0,
        )
        self.assertAlmostEqual(
            float(dynamics["middle_position_gain"]),
            -1.0 / 9.0,
        )
        self.assertAlmostEqual(
            float(dynamics["late_position_gain"]),
            -6.0 / 9.0,
        )
        self.assertAlmostEqual(
            float(dynamics["overall_position_gain"]),
            -1.0 / 9.0,
        )

    def test_position_dynamics_falls_back_to_third_corner(self) -> None:
        dynamics = position_dynamics([10, 9, 3, None], 2, 12)

        self.assertAlmostEqual(
            float(dynamics["middle_position_gain"]),
            6.0 / 11.0,
        )
        self.assertIsNone(dynamics["late_position_gain"])


if __name__ == "__main__":
    unittest.main()
