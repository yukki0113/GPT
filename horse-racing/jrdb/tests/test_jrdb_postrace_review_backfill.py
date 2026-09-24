#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from audit_jrdb_postrace_review import audit_review_bundle  # noqa: E402
from jrdb_postrace_review_backfill import (  # noqa: E402
    RollingReviewHistory,
    _insert_relation_rows,
    _schema_sql,
    build_descriptive_bias_rows,
    build_review_day_indexed,
)
from jrdb_postrace_review_builder import (  # noqa: E402
    build_historical_race_samples,
    build_review_day,
)
from jrdb_postrace_review_publish import (  # noqa: E402
    publish_database_snapshot,
)

DUCKDB_AVAILABLE = importlib.util.find_spec("duckdb") is not None


def _row(
    race_key: str,
    race_date: str,
    distance_m: int,
    class_group: str,
    time_sec: float,
    *,
    horse_no: int = 1,
    finish: int = 1,
    first3f: float = 35.0,
    last3f: float = 35.0,
    first_gap: float = 0.0,
    last_gap: float = 0.0,
    corner1: int = 1,
    corner2: int = 1,
    corner3: int = 1,
    corner4: int = 1,
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
        "horse_id": f"H{race_key}{horse_no:02d}",
        "horse_name": f"馬{horse_no}",
        "finish": finish,
        "abnormal_code": "0",
        "time_sec": time_sec,
        "first3f_sec": first3f,
        "first3f_leader_diff_sec": first_gap,
        "last3f_sec": last3f,
        "last3f_leader_diff_sec": last_gap,
        "corner1_position": corner1,
        "corner2_position": corner2,
        "corner3_position": corner3,
        "corner4_position": corner4,
        "race_pace_code": "M",
        "race_running_style_code": "1",
        "frame_no": horse_no if horse_no <= 8 else 8,
        "course_lane_code": "2",
        "course_lane_bucket": "INNER",
        "fourth_corner_lane_code": "2",
        "fourth_corner_lane_bucket": "INNER",
    }


def _history_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    specs = [
        ("H001", "2023-03-05", 1600, "MAIDEN", 96.0, 35.5, 35.2),
        ("H002", "2023-03-12", 1600, "MAIDEN", 95.8, 35.4, 35.2),
        ("H003", "2024-03-03", 1600, "MAIDEN", 95.6, 35.2, 35.4),
        ("H004", "2023-03-05", 1600, "CLASS_1", 94.8, 35.2, 35.0),
        ("H005", "2023-03-12", 1600, "CLASS_1", 94.6, 35.1, 35.1),
        ("H006", "2024-03-03", 1600, "CLASS_1", 94.4, 34.9, 35.2),
        ("H007", "2023-03-05", 1200, "MAIDEN", 73.0, 34.6, 35.0),
        ("H008", "2023-03-12", 1200, "MAIDEN", 72.8, 34.5, 35.0),
        ("H009", "2024-03-03", 1200, "MAIDEN", 72.6, 34.4, 35.1),
        ("H010", "2023-03-05", 1400, "MAIDEN", 83.0, 34.8, 35.3),
        ("H011", "2023-03-12", 1400, "MAIDEN", 82.8, 34.7, 35.3),
        ("H012", "2024-03-03", 1400, "MAIDEN", 82.6, 34.6, 35.4),
    ]
    for race_key, date, distance, group, time_sec, first3f, last3f in specs:
        rows.append(
            _row(
                race_key,
                date,
                distance,
                group,
                time_sec,
                first3f=first3f,
                last3f=last3f,
            )
        )
    return rows


def _target_rows() -> list[dict[str, object]]:
    winner = _row(
        "T001",
        "2025-03-15",
        1600,
        "MAIDEN",
        94.2,
        first3f=34.5,
        last3f=35.5,
    )
    horse8 = _row(
        "T001",
        "2025-03-15",
        1600,
        "MAIDEN",
        95.4,
        horse_no=8,
        finish=8,
        first3f=35.3,
        last3f=35.1,
        first_gap=0.8,
        last_gap=1.4,
        corner1=8,
        corner2=2,
        corner3=2,
        corner4=3,
    )
    race2 = _row(
        "T002",
        "2025-03-15",
        1200,
        "MAIDEN",
        72.2,
        first3f=34.1,
        last3f=34.8,
    )
    race3 = _row(
        "T003",
        "2025-03-15",
        1400,
        "MAIDEN",
        82.2,
        first3f=34.4,
        last3f=35.0,
    )
    return [winner, horse8, race2, race3]


class JrdbPostRaceReviewBackfillTest(unittest.TestCase):
    def _history_index(self) -> RollingReviewHistory:
        history = RollingReviewHistory()
        history.add_race_samples(
            build_historical_race_samples(_history_rows())
        )
        return history

    def test_rolling_standard_matches_day_builder_baseline(self) -> None:
        history = self._history_index()
        target = _target_rows()[0]

        standard = history.lookup_standard(
            target,
            minimum_sample_count=3,
        )

        self.assertEqual(standard["sample_count"], 3)
        self.assertEqual(standard["scope_level"], 1)
        self.assertAlmostEqual(
            float(standard["standard_time_sec"]),
            95.8,
        )
        self.assertEqual(
            standard["sample_end_date"],
            "2024-03-03",
        )

    def test_indexed_builder_matches_scanning_builder_on_core_outputs(self) -> None:
        scanning = build_review_day(
            _target_rows(),
            _history_rows(),
            minimum_standard_sample_count=3,
            minimum_pace_sample_count=3,
            minimum_day_adjustment_race_count=2,
        )
        indexed = build_review_day_indexed(
            _target_rows(),
            self._history_index(),
            minimum_standard_sample_count=3,
            minimum_pace_sample_count=3,
            minimum_day_adjustment_race_count=2,
        )

        scan_race = {
            row["race_key"]: row
            for row in scanning["fact_race_review"]
        }
        indexed_race = {
            row["race_key"]: row
            for row in indexed["fact_race_review"]
        }
        self.assertEqual(set(scan_race), set(indexed_race))

        for race_key in scan_race:
            for field_name in (
                "historical_standard_time_sec",
                "standard_sample_count",
                "standard_scope_level",
                "standard_sample_end_date",
                "day_track_adjustment_sec",
                "day_adjustment_applied",
                "adjusted_standard_time_sec",
                "time_delta_sec",
                "equivalent_class_group",
                "class_equivalent_numeric",
                "pace_shape",
            ):
                self.assertEqual(
                    scan_race[race_key][field_name],
                    indexed_race[race_key][field_name],
                    f"{race_key}/{field_name}",
                )

        scan_context = {
            row["race_key"]: row
            for row in scanning["fact_race_context"]
        }
        indexed_context = {
            row["race_key"]: row
            for row in indexed["fact_race_context"]
        }
        for race_key in scan_context:
            for field_name in (
                "first3f_reference_sec",
                "last3f_reference_sec",
                "pace_balance_sec",
                "pace_balance_percentile",
                "pace_shape",
                "pace_sample_count",
                "pace_scope_level",
            ):
                self.assertEqual(
                    scan_context[race_key][field_name],
                    indexed_context[race_key][field_name],
                    f"{race_key}/{field_name}",
                )

        scan_horse = {
            row["race_horse_key"]: row
            for row in scanning["fact_horse_performance"]
        }
        indexed_horse = {
            row["race_horse_key"]: row
            for row in indexed["fact_horse_performance"]
        }
        for horse_key in scan_horse:
            for field_name in (
                "winner_gap_sec",
                "early_position_gain",
                "middle_position_gain",
                "late_position_gain",
                "horse_adjusted_delta_sec",
                "time_class_equivalent",
            ):
                self.assertEqual(
                    scan_horse[horse_key][field_name],
                    indexed_horse[horse_key][field_name],
                    f"{horse_key}/{field_name}",
                )

    def test_same_day_samples_are_not_visible_until_explicit_add(self) -> None:
        history = self._history_index()
        before = history.race_sample_count
        day = build_review_day_indexed(
            _target_rows(),
            history,
            minimum_standard_sample_count=3,
            minimum_pace_sample_count=3,
        )

        self.assertEqual(history.race_sample_count, before)
        samples = day["history_samples"]
        self.assertIsInstance(samples, list)
        history.add_race_samples(samples)
        self.assertEqual(
            history.race_sample_count,
            before + len(samples),
        )

    def test_descriptive_bias_is_shadow_only(self) -> None:
        day = build_review_day_indexed(
            _target_rows(),
            self._history_index(),
            minimum_standard_sample_count=3,
            minimum_pace_sample_count=3,
        )
        bias = build_descriptive_bias_rows(
            day["fact_horse_performance"]
        )

        self.assertTrue(bias)
        for row in bias:
            self.assertIsNone(row["shrunk_bias_score"])
            self.assertIsNone(row["bias_direction"])
            self.assertIn(
                row["confidence"],
                {"DESCRIPTIVE_ONLY", "LOW_SAMPLE"},
            )

        day["fact_track_bias"] = bias
        audit = audit_review_bundle(
            day,
            expected_target_date="2025-03-15",
        )
        self.assertEqual(audit["status"], "PASS")


@unittest.skipUnless(
    DUCKDB_AVAILABLE,
    "Review streaming publication requires project DuckDB dependency",
)
class JrdbPostRaceReviewBackfillDatabaseTest(unittest.TestCase):
    def test_staged_database_publishes_without_full_bundle_memory(self) -> None:
        import duckdb

        history = RollingReviewHistory()
        history.add_race_samples(
            build_historical_race_samples(_history_rows())
        )
        day = build_review_day_indexed(
            _target_rows(),
            history,
            minimum_standard_sample_count=3,
            minimum_pace_sample_count=3,
        )
        day["fact_track_bias"] = build_descriptive_bias_rows(
            day["fact_horse_performance"]
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "stage.duckdb"
            output_root = root / "review"

            connection = duckdb.connect(str(database_path))
            try:
                connection.execute(_schema_sql())
                for relation in (
                    "fact_race_context",
                    "fact_race_review",
                    "fact_horse_performance",
                    "fact_track_bias",
                ):
                    _insert_relation_rows(
                        connection,
                        relation,
                        day[relation],
                    )
                connection.commit()
            finally:
                connection.close()

            result = publish_database_snapshot(
                database_path,
                output_root,
                "review-db-test-01",
                source_provenance={
                    "warehouse_generation_id": "warehouse-test",
                },
                promote=False,
                complete_snapshot=False,
            )

            self.assertEqual(
                result["pointer"]["status"],
                "SHADOW_PASS",
            )
            self.assertEqual(
                result["audit"]["database_audit"]["status"],
                "PASS",
            )
            self.assertGreater(
                result["manifest"]["relations"][
                    "fact_horse_performance"
                ]["total_rows"],
                0,
            )


if __name__ == "__main__":
    unittest.main()
