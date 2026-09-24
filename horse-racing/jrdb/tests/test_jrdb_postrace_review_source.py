#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from jrdb_postrace_review_source import (  # noqa: E402
    PostRaceReviewSourceError,
    build_review_input_rows,
    project_sed_result,
)


class JrdbPostRaceReviewSourceTest(unittest.TestCase):
    def test_project_flattened_warehouse_sed(self) -> None:
        row = {
            "race_key_raw": "0526a101",
            "horse_no": 8,
            "blood_registration_no": "12345678",
            "horse_name": "テストホース",
            "race_date": "2025-10-11",
            "distance_m": 1600,
            "surface_code": "1",
            "track_condition_code": "10",
            "race_type_code": "12",
            "race_class_code": "A3",
            "grade_code": "",
            "field_size": 10,
            "finish": 9,
            "abnormal_code": "0",
            "time_raw": "1345",
            "carried_weight_tenths": 560,
            "first3f_sec": 34.8,
            "last3f_sec": 37.1,
            "first3f_leader_diff_sec": 0.8,
            "last3f_leader_diff_sec": 0.2,
            "corner_1": 8,
            "corner_2": 2,
            "corner_3": 2,
            "corner_4": 3,
            "race_pace_code": "H",
            "horse_pace_code": "H",
            "course_lane_code": "2",
            "fourth_corner_lane_code": "1",
            "metric_track_diff": -3,
            "metric_pace_score": 7,
            "metric_late_break_score": 4,
            "metric_position_score": 6,
            "metric_trouble_score": 1,
        }

        result = project_sed_result(row)

        self.assertEqual(result["race_key"], "0526a101")
        self.assertEqual(result["race_horse_key"], "0526a10108")
        self.assertEqual(result["race_date"], "2025-10-11")
        self.assertEqual(result["venue_code"], "05")
        self.assertEqual(result["race_no"], 1)
        self.assertEqual(result["declared_class_group"], "MAIDEN")
        self.assertAlmostEqual(float(result["time_sec"]), 94.5)
        self.assertAlmostEqual(float(result["carried_weight_kg"]), 56.0)
        self.assertEqual(result["corner1_position"], 8)
        self.assertEqual(result["corner4_position"], 3)
        self.assertEqual(result["course_lane_bucket"], "INNER")
        self.assertEqual(result["fourth_corner_lane_bucket"], "INNER")
        self.assertEqual(result["jrdb_track_diff"], -3)
        self.assertEqual(result["jrdb_late_break_score"], 4)

    def test_project_nested_current_parsed_sed(self) -> None:
        row = {
            "race_key_raw": "0526a101",
            "horse_no": 3,
            "date_raw": "20251011",
            "race_class_code": "04",
            "grade_code": "",
            "time_raw": "1339",
            "corners": [4, 4, 3, 2],
            "metrics": {
                "track_diff": -2,
                "pace_score": 5,
                "late_break_score": 0,
            },
        }

        result = project_sed_result(row)

        self.assertEqual(result["race_date"], "2025-10-11")
        self.assertEqual(result["declared_class_group"], "CLASS_1")
        self.assertEqual(result["corner3_position"], 3)
        self.assertEqual(result["jrdb_track_diff"], -2)
        self.assertEqual(result["jrdb_pace_score"], 5)

    def test_build_rows_joins_kyi_and_latest_bac_context(self) -> None:
        sed = [
            {
                "race_key_raw": "0526a101",
                "horse_no": 8,
                "date_raw": "20251011",
                "race_class_code": "A3",
                "time_raw": "1345",
            }
        ]
        kyi = [
            {
                "race_key_raw": "0526a101",
                "horse_no": 8,
                "frame_no": 7,
                "running_style_code": "2",
                "start_index": 44,
                "late_break_rate": 12,
            }
        ]
        bac = [
            {
                "race_key_raw": "0526a101",
                "source_member_date": "2025-10-10",
                "source_record_ordinal": 1,
                "meeting": "旧",
            },
            {
                "race_key_raw": "0526a101",
                "source_member_date": "2025-10-11",
                "source_record_ordinal": 1,
                "meeting": "最新",
            },
        ]

        rows = build_review_input_rows(sed, kyi, bac)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["frame_no"], 7)
        self.assertEqual(rows[0]["declared_running_style_code"], "2")
        self.assertEqual(rows[0]["start_index"], 44)
        self.assertEqual(rows[0]["late_break_rate"], 12)
        self.assertEqual(rows[0]["meeting"], "最新")

    def test_duplicate_sed_key_fails_closed(self) -> None:
        sed = [
            {
                "race_key_raw": "0526a101",
                "horse_no": 8,
                "date_raw": "20251011",
            },
            {
                "race_key_raw": "0526a101",
                "horse_no": 8,
                "date_raw": "20251011",
            },
        ]

        with self.assertRaises(PostRaceReviewSourceError):
            build_review_input_rows(sed)


if __name__ == "__main__":
    unittest.main()
