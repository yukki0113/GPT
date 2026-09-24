#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from jrdb_postrace_review_context import (  # noqa: E402
    PostRaceReviewContextError,
    build_horse_context_rows,
    build_race_context,
    reconstruct_race_sectionals,
    winner_time_seconds,
)


def _race_rows() -> list[dict[str, object]]:
    return [
        {
            "race_key": "0526a101",
            "race_horse_key": "0526a10101",
            "race_date": "2025-10-11",
            "venue_code": "05",
            "surface_code": "1",
            "distance_m": 1600,
            "field_size": 10,
            "horse_no": 1,
            "finish": 1,
            "abnormal_code": "0",
            "time_sec": 94.0,
            "first3f_sec": 34.6,
            "first3f_leader_diff_sec": 0.0,
            "last3f_sec": 35.1,
            "last3f_leader_diff_sec": 0.0,
            "corner1_position": 1,
            "corner2_position": 1,
            "corner3_position": 1,
            "corner4_position": 1,
            "race_pace_code": "H",
        },
        {
            "race_key": "0526a101",
            "race_horse_key": "0526a10108",
            "race_date": "2025-10-11",
            "venue_code": "05",
            "surface_code": "1",
            "distance_m": 1600,
            "field_size": 10,
            "horse_no": 8,
            "finish": 9,
            "abnormal_code": "0",
            "time_sec": 95.4,
            "first3f_sec": 35.4,
            "first3f_leader_diff_sec": 0.8,
            "last3f_sec": 35.3,
            "last3f_leader_diff_sec": 1.2,
            "corner1_position": 8,
            "corner2_position": 2,
            "corner3_position": 2,
            "corner4_position": 3,
            "race_pace_code": "H",
        },
        {
            "race_key": "0526a101",
            "race_horse_key": "0526a10103",
            "race_date": "2025-10-11",
            "venue_code": "05",
            "surface_code": "1",
            "distance_m": 1600,
            "field_size": 10,
            "horse_no": 3,
            "finish": 2,
            "abnormal_code": "0",
            "time_sec": 94.3,
            "first3f_sec": 35.6,
            "first3f_leader_diff_sec": 1.0,
            "last3f_sec": 34.2,
            "last3f_leader_diff_sec": 1.2,
            "corner1_position": 7,
            "corner2_position": 7,
            "corner3_position": 5,
            "corner4_position": 4,
            "race_pace_code": "H",
        },
    ]


class JrdbPostRaceReviewContextTest(unittest.TestCase):
    def test_reconstruct_race_sectionals_from_multiple_horses(self) -> None:
        context = reconstruct_race_sectionals(_race_rows())

        self.assertAlmostEqual(float(context["winner_time_sec"]), 94.0)
        self.assertAlmostEqual(float(context["first3f_reference_sec"]), 34.6)
        self.assertEqual(context["first3f_candidate_count"], 3)
        self.assertAlmostEqual(float(context["last3f_reference_sec"]), 35.1)
        self.assertEqual(context["last3f_candidate_count"], 3)
        self.assertAlmostEqual(float(context["pace_balance_sec"]), 0.5)
        self.assertAlmostEqual(float(context["first3f_candidate_mad_sec"]), 0.0)
        self.assertAlmostEqual(float(context["last3f_candidate_mad_sec"]), 0.0)

    def test_build_horse_context_captures_recovery_and_fade(self) -> None:
        rows = build_horse_context_rows(_race_rows())
        horse = next(row for row in rows if row["horse_no"] == 8)

        self.assertAlmostEqual(float(horse["winner_gap_sec"]), 1.4)
        self.assertAlmostEqual(float(horse["early_position_gain"]), 6.0 / 9.0)
        self.assertAlmostEqual(float(horse["late_position_gain"]), -6.0 / 9.0)
        self.assertAlmostEqual(float(horse["closing_gain_sec"]), -0.2)

    def test_last3f_rank_is_high_is_better_percentile(self) -> None:
        rows = build_horse_context_rows(_race_rows())
        fastest = next(row for row in rows if row["horse_no"] == 3)
        slowest = next(row for row in rows if row["horse_no"] == 8)

        self.assertEqual(fastest["last3f_rank"], 1)
        self.assertAlmostEqual(float(fastest["last3f_speed_percentile"]), 100.0)
        self.assertEqual(slowest["last3f_rank"], 3)
        self.assertAlmostEqual(float(slowest["last3f_speed_percentile"]), 0.0)

    def test_build_race_context_preserves_jrdb_pace_consensus(self) -> None:
        context = build_race_context(_race_rows())

        self.assertEqual(context["race_key"], "0526a101")
        self.assertEqual(context["race_pace_code"], "H")
        self.assertFalse(context["race_pace_code_conflict"])

    def test_dead_heat_same_time_is_accepted(self) -> None:
        rows = _race_rows()
        rows[2]["finish"] = 1
        rows[2]["time_sec"] = 94.0

        self.assertAlmostEqual(float(winner_time_seconds(rows)), 94.0)

    def test_conflicting_dead_heat_time_fails_closed(self) -> None:
        rows = _race_rows()
        rows[2]["finish"] = 1
        rows[2]["time_sec"] = 94.2

        with self.assertRaises(PostRaceReviewContextError):
            winner_time_seconds(rows)

    def test_multiple_races_fail_context_contract(self) -> None:
        rows = _race_rows()
        rows[2]["race_key"] = "0526a102"

        with self.assertRaises(PostRaceReviewContextError):
            build_race_context(rows)


if __name__ == "__main__":
    unittest.main()
