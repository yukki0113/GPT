#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from jrdb_postrace_review_builder import (  # noqa: E402
    PostRaceReviewBuildError,
    build_review_day,
)


def _winner_row(
    race_key: str,
    race_date: str,
    distance_m: int,
    class_group: str,
    winner_time: float,
    *,
    first3f: float = 35.0,
    last3f: float = 35.0,
    horse_no: int = 1,
    finish: int = 1,
) -> dict[str, object]:
    return {
        "race_key": race_key,
        "race_horse_key": f"{race_key}{horse_no:02d}",
        "race_date": race_date,
        "venue_code": "05",
        "surface_code": "1",
        "distance_m": distance_m,
        "course_code": "1",
        "race_type_code": "12",
        "declared_class_group": class_group,
        "field_size": 10,
        "horse_no": horse_no,
        "finish": finish,
        "abnormal_code": "0",
        "time_sec": winner_time,
        "first3f_sec": first3f,
        "first3f_leader_diff_sec": 0.0,
        "last3f_sec": last3f,
        "last3f_leader_diff_sec": 0.0,
        "corner1_position": 1,
        "corner2_position": 1,
        "corner3_position": 1,
        "corner4_position": 1,
        "race_pace_code": "M",
        "course_lane_code": "2",
        "course_lane_bucket": "INNER",
        "fourth_corner_lane_code": "2",
        "fourth_corner_lane_bucket": "INNER",
    }


def _history() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    specs = [
        ("H001", "2023-03-05", 1600, "MAIDEN", 96.0),
        ("H002", "2024-03-03", 1600, "MAIDEN", 95.8),
        ("H003", "2023-03-12", 1600, "CLASS_1", 94.8),
        ("H004", "2024-03-10", 1600, "CLASS_1", 94.6),
        ("H005", "2023-03-05", 1200, "MAIDEN", 73.0),
        ("H006", "2024-03-03", 1200, "MAIDEN", 72.8),
        ("H007", "2023-03-12", 1200, "CLASS_1", 72.0),
        ("H008", "2024-03-10", 1200, "CLASS_1", 71.8),
        ("H009", "2023-03-05", 1400, "MAIDEN", 83.0),
        ("H010", "2024-03-03", 1400, "MAIDEN", 82.8),
        ("H011", "2023-03-12", 1400, "CLASS_1", 81.8),
        ("H012", "2024-03-10", 1400, "CLASS_1", 81.6),
    ]
    for race_key, race_date, distance, class_group, time_sec in specs:
        rows.append(
            _winner_row(
                race_key,
                race_date,
                distance,
                class_group,
                time_sec,
            )
        )
    return rows


def _target_day() -> list[dict[str, object]]:
    race1 = _winner_row(
        "T001",
        "2025-03-15",
        1600,
        "MAIDEN",
        94.0,
        first3f=34.5,
        last3f=35.5,
    )
    race1["race_pace_code"] = "H"

    horse8 = dict(race1)
    horse8.update(
        {
            "race_horse_key": "T00108",
            "horse_no": 8,
            "finish": 9,
            "time_sec": 95.4,
            "first3f_sec": 35.3,
            "first3f_leader_diff_sec": 0.8,
            "last3f_sec": 35.3,
            "last3f_leader_diff_sec": 1.6,
            "corner1_position": 8,
            "corner2_position": 2,
            "corner3_position": 2,
            "corner4_position": 3,
            "jrdb_late_break_score": 5,
        }
    )

    race2 = _winner_row(
        "T002",
        "2025-03-15",
        1200,
        "CLASS_1",
        71.5,
        first3f=34.0,
        last3f=34.5,
    )
    race3 = _winner_row(
        "T003",
        "2025-03-15",
        1400,
        "MAIDEN",
        82.6,
        first3f=34.7,
        last3f=35.0,
    )
    return [race1, horse8, race2, race3]


class JrdbPostRaceReviewBuilderTest(unittest.TestCase):
    def test_build_review_day_connects_time_pace_and_position(self) -> None:
        result = build_review_day(
            _target_day(),
            _history(),
            minimum_standard_sample_count=2,
            minimum_pace_sample_count=2,
        )

        self.assertEqual(result["audit"]["race_count"], 3)
        self.assertEqual(result["audit"]["horse_count"], 4)

        race1 = next(
            row
            for row in result["fact_race_review"]
            if row["race_key"] == "T001"
        )
        self.assertTrue(race1["day_adjustment_applied"])
        self.assertEqual(race1["day_adjustment_race_count"], 2)
        self.assertEqual(race1["time_delta_basis"], "LOO_DAY_ADJUSTED")
        self.assertEqual(race1["equivalent_class_group"], "CLASS_1")
        self.assertLess(
            float(race1["standard_sample_end_date"].replace("-", "")),
            20250315,
        )

        context1 = next(
            row
            for row in result["fact_race_context"]
            if row["race_key"] == "T001"
        )
        self.assertAlmostEqual(float(context1["first3f_reference_sec"]), 34.5)
        self.assertAlmostEqual(float(context1["last3f_reference_sec"]), 35.5)
        self.assertEqual(context1["pace_shape"], "VERY_FRONT_LOADED")

        horse8 = next(
            row
            for row in result["fact_horse_performance"]
            if row["race_horse_key"] == "T00108"
        )
        self.assertAlmostEqual(
            float(horse8["early_position_gain"]),
            6.0 / 9.0,
        )
        self.assertAlmostEqual(
            float(horse8["late_position_gain"]),
            -6.0 / 9.0,
        )
        self.assertEqual(horse8["start_delay_confidence"], "UNKNOWN")
        self.assertEqual(horse8["jrdb_late_break_score"], 5)

    def test_sparse_day_keeps_candidate_but_does_not_apply_it(self) -> None:
        result = build_review_day(
            [_target_day()[0]],
            _history(),
            minimum_standard_sample_count=2,
            minimum_pace_sample_count=2,
        )
        race = result["fact_race_review"][0]

        self.assertFalse(race["day_adjustment_applied"])
        self.assertIsNone(race["day_track_adjustment_sec"])
        self.assertEqual(race["time_delta_basis"], "HISTORICAL_ONLY")

    def test_builder_rejects_non_prior_history(self) -> None:
        history = _history()
        history.append(
            _winner_row(
                "F001",
                "2025-03-15",
                1600,
                "MAIDEN",
                90.0,
            )
        )

        with self.assertRaises(PostRaceReviewBuildError):
            build_review_day(
                _target_day(),
                history,
                minimum_standard_sample_count=2,
                minimum_pace_sample_count=2,
            )


if __name__ == "__main__":
    unittest.main()
