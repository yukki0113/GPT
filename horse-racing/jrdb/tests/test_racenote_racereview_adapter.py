#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from racenote_racereview_adapter import (  # noqa: E402
    RaceReviewAdapterError,
    build_racereview_evidence,
)


class FakeRaceReviewReader:
    def __init__(self, histories: dict[str, list[dict[str, object]]]) -> None:
        self.histories = histories
        self.calls: list[dict[str, object]] = []

    def metadata(self) -> dict[str, object]:
        return {
            "generation_id": "review-test",
            "period_from": "2010-01-01",
            "period_to": "2026-09-24",
            "review_schema_version": "v0.1",
            "review_logic_version": "review-test-v1",
            "baseline_version": "baseline-test-v1",
            "row_counts": {
                "fact_horse_performance": 3,
            },
        }

    def histories_for_horses(
        self,
        horse_ids: list[str],
        *,
        before_date: object,
        per_horse_limit: int,
    ) -> dict[str, list[dict[str, object]]]:
        self.calls.append(
            {
                "horse_ids": list(horse_ids),
                "before_date": before_date,
                "per_horse_limit": per_horse_limit,
            }
        )
        return {
            horse_id: list(self.histories.get(horse_id, []))[
                :per_horse_limit
            ]
            for horse_id in horse_ids
        }


def _independent_view() -> dict[str, object]:
    return {
        "view_kind": "INDEPENDENT",
        "race": {
            "date": "2026-09-25",
            "venue": "中山",
            "race_no": 11,
            "race_name": "テストステークス",
        },
        "horses": [
            {
                "basic": {
                    "horse_no": 1,
                    "horse_name": "レビューエース",
                    "horse_id": "12345678",
                }
            },
            {
                "basic": {
                    "horse_no": 2,
                    "horse_name": "IDナシ",
                }
            },
        ],
    }


def _history_row(
    race_key: str,
    race_date: str,
    *,
    finish: int,
    declared_class_group: str,
    time_class_equivalent: str,
    early_position_gain: float,
    middle_position_gain: float,
    late_position_gain: float,
    closing_gain_sec: float,
    last3f_rank: int,
) -> dict[str, object]:
    return {
        "race_key": race_key,
        "race_date": race_date,
        "venue_code": "06",
        "surface_code": "1",
        "distance_m": 1600,
        "field_size": 12,
        "declared_class_group": declared_class_group,
        "finish": finish,
        "winner_gap_sec": 0.4,
        "horse_adjusted_delta_sec": -0.3,
        "horse_adjusted_delta_per_1000m": -0.1875,
        "time_class_equivalent": time_class_equivalent,
        "time_class_equivalent_numeric": 3.0,
        "pace_shape": "FRONT_LOADED",
        "last3f_rank": last3f_rank,
        "last3f_speed_percentile": 100.0 if last3f_rank == 1 else 50.0,
        "closing_gain_sec": closing_gain_sec,
        "corner1_frontness": 0.3,
        "corner2_frontness": 0.7,
        "corner3_frontness": 0.7,
        "corner4_frontness": 0.6,
        "early_position_gain": early_position_gain,
        "middle_position_gain": middle_position_gain,
        "late_position_gain": late_position_gain,
        "overall_position_gain": 0.1,
        "jrdb_track_diff": 0.0,
        "jrdb_pace_score": 1.0,
        "jrdb_late_break_score": 0.0,
        "jrdb_position_score": 2.0,
        "jrdb_trouble_score": 0.0,
        "jrdb_prev_trouble_score": 0.0,
        "jrdb_mid_trouble_score": 0.0,
        "jrdb_late_trouble_score": 0.0,
        "performance_label": "SHOULD_NOT_BE_CONSUMED",
        "reason_codes_json": "[\"SHOULD_NOT_BE_CONSUMED\"]",
    }


class RaceNoteRaceReviewAdapterTest(unittest.TestCase):
    def test_builds_asof_sidecar_with_stable_identity(self) -> None:
        histories = {
            "12345678": [
                _history_row(
                    "0626a101",
                    "2026-09-20",
                    finish=5,
                    declared_class_group="CLASS_1",
                    time_class_equivalent="CLASS_2",
                    early_position_gain=0.4,
                    middle_position_gain=0.0,
                    late_position_gain=-0.3,
                    closing_gain_sec=0.2,
                    last3f_rank=1,
                ),
                _history_row(
                    "0626a090",
                    "2026-09-13",
                    finish=3,
                    declared_class_group="CLASS_1",
                    time_class_equivalent="CLASS_2",
                    early_position_gain=0.2,
                    middle_position_gain=0.1,
                    late_position_gain=-0.1,
                    closing_gain_sec=0.1,
                    last3f_rank=2,
                ),
            ]
        }
        reader = FakeRaceReviewReader(histories)

        sidecar = build_racereview_evidence(
            _independent_view(),
            reader,  # type: ignore[arg-type]
            per_horse_limit=5,
        )

        self.assertEqual(sidecar["adapter_version"], "0.1")
        self.assertTrue(sidecar["policy"]["as_of_exclusive"])
        self.assertFalse(sidecar["policy"]["name_fallback"])

        first = sidecar["horses"][0]
        self.assertEqual(first["horse_id"], "12345678")
        self.assertEqual(first["history_status"], "AVAILABLE")
        self.assertEqual(first["profile"]["coverage_status"], "PARTIAL")
        self.assertIn(
            {
                "tag": "TIME_ABOVE_DECLARED_CLASS",
                "count": 2,
            },
            first["profile"]["repeated_patterns"],
        )

        run = first["runs"][0]
        self.assertIn("MOVE_THEN_FADE", run["review_tags"])
        self.assertIn("FASTEST_LAST3F", run["review_tags"])
        self.assertIn("PACE_FRONT_LOADED", run["review_tags"])
        self.assertEqual(
            run["families"]["trouble"]["calibration_status"],
            "RAW_ONLY_UNCALIBRATED",
        )
        self.assertNotIn("performance_label", run)
        self.assertNotIn("reason_codes_json", run)

        second = sidecar["horses"][1]
        self.assertEqual(second["history_status"], "NO_HORSE_ID")
        self.assertEqual(second["runs"], [])

        self.assertEqual(
            reader.calls[0]["horse_ids"],
            ["12345678"],
        )
        self.assertEqual(
            reader.calls[0]["before_date"],
            "2026-09-25",
        )

    def test_future_history_fails_closed(self) -> None:
        histories = {
            "12345678": [
                _history_row(
                    "0626a111",
                    "2026-09-25",
                    finish=1,
                    declared_class_group="CLASS_1",
                    time_class_equivalent="CLASS_2",
                    early_position_gain=0.0,
                    middle_position_gain=0.0,
                    late_position_gain=0.0,
                    closing_gain_sec=0.0,
                    last3f_rank=1,
                )
            ]
        }
        reader = FakeRaceReviewReader(histories)

        with self.assertRaises(RaceReviewAdapterError):
            build_racereview_evidence(
                _independent_view(),
                reader,  # type: ignore[arg-type]
            )

    def test_non_independent_view_is_rejected(self) -> None:
        view = _independent_view()
        view["view_kind"] = "JRDB_CONSENSUS"
        reader = FakeRaceReviewReader({})

        with self.assertRaises(RaceReviewAdapterError):
            build_racereview_evidence(
                view,
                reader,  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
