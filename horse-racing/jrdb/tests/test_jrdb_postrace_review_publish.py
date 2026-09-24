#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from jrdb_postrace_review_publish import (  # noqa: E402
    PostRaceReviewPublishError,
    publish_snapshot,
)

DUCKDB_AVAILABLE = importlib.util.find_spec("duckdb") is not None


def _bundle() -> dict[str, object]:
    return {
        "fact_race_context": [
            {
                "race_key": "T001",
                "race_date": "2025-03-15",
                "venue_code": "05",
                "surface_code": "1",
                "distance_m": 1600,
                "field_size": 10,
                "pace_shape": "FRONT_LOADED",
                "review_schema_version": "v0.1",
                "review_logic_version": "v0.1.0",
            }
        ],
        "fact_race_review": [
            {
                "race_key": "T001",
                "race_date": "2025-03-15",
                "venue_code": "05",
                "surface_code": "1",
                "distance_m": 1600,
                "declared_class_group": "MAIDEN",
                "historical_standard_time_sec": 95.0,
                "standard_sample_end_date": "2025-03-10",
                "day_adjustment_applied": False,
                "class_curve_monotonic": True,
                "baseline_version": "asof-median-loo-v0.1",
                "review_schema_version": "v0.1",
                "review_logic_version": "v0.1.0",
            }
        ],
        "fact_horse_performance": [
            {
                "race_key": "T001",
                "race_horse_key": "T00101",
                "horse_no": 1,
                "race_date": "2025-03-15",
                "venue_code": "05",
                "surface_code": "1",
                "distance_m": 1600,
                "field_size": 10,
                "finish": 1,
                "baseline_version": "asof-median-loo-v0.1",
                "review_schema_version": "v0.1",
                "review_logic_version": "v0.1.0",
            }
        ],
    }


@unittest.skipUnless(
    DUCKDB_AVAILABLE,
    "Review Parquet publisher requires project DuckDB dependency",
)
class JrdbPostRaceReviewPublishTest(unittest.TestCase):
    def test_shadow_snapshot_writes_content_addressed_parquet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = publish_snapshot(
                _bundle(),
                root,
                "review-test-01",
                source_provenance={
                    "warehouse_generation_id": "warehouse-test",
                },
            )

            self.assertEqual(result["pointer"]["status"], "SHADOW_PASS")
            self.assertFalse((root / "current.json").exists())
            self.assertTrue((root / "shadow_current.json").is_file())

            manifest = result["manifest"]
            self.assertEqual(manifest["validation_status"], "PASS")
            for relation in (
                "fact_race_context",
                "fact_race_review",
                "fact_horse_performance",
            ):
                partitions = manifest["relations"][relation]["partitions"]
                self.assertEqual(len(partitions), 1)
                self.assertEqual(partitions[0]["year"], 2025)
                object_path = root / partitions[0]["relative_path"]
                self.assertTrue(object_path.is_file())

    def test_incomplete_snapshot_cannot_promote(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(PostRaceReviewPublishError):
                publish_snapshot(
                    _bundle(),
                    root,
                    "review-test-02",
                    source_provenance={},
                    promote=True,
                    complete_snapshot=False,
                )

            self.assertFalse((root / "current.json").exists())

    def test_complete_snapshot_promotes_only_after_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = publish_snapshot(
                _bundle(),
                root,
                "review-test-03",
                source_provenance={
                    "warehouse_generation_id": "warehouse-test",
                },
                promote=True,
                complete_snapshot=True,
            )

            self.assertEqual(result["pointer"]["status"], "CURRENT")
            self.assertTrue((root / "current.json").is_file())
            self.assertEqual(
                result["pointer"]["generation_id"],
                "review-test-03",
            )

    def test_multi_day_snapshot_partitions_by_year(self) -> None:
        bundle = _bundle()
        context_rows = bundle["fact_race_context"]
        race_rows = bundle["fact_race_review"]
        horse_rows = bundle["fact_horse_performance"]
        assert isinstance(context_rows, list)
        assert isinstance(race_rows, list)
        assert isinstance(horse_rows, list)

        context_2026 = copy.deepcopy(context_rows[0])
        context_2026["race_key"] = "T002"
        context_2026["race_date"] = "2026-01-05"
        context_rows.append(context_2026)

        race_2026 = copy.deepcopy(race_rows[0])
        race_2026["race_key"] = "T002"
        race_2026["race_date"] = "2026-01-05"
        race_rows.append(race_2026)

        horse_2026 = copy.deepcopy(horse_rows[0])
        horse_2026["race_key"] = "T002"
        horse_2026["race_horse_key"] = "T00201"
        horse_2026["race_date"] = "2026-01-05"
        horse_rows.append(horse_2026)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = publish_snapshot(
                bundle,
                root,
                "review-test-04",
                source_provenance={},
            )

            partitions = result["manifest"]["relations"][
                "fact_race_review"
            ]["partitions"]
            self.assertEqual(
                [part["year"] for part in partitions],
                [2025, 2026],
            )

    def test_failed_prepublication_audit_leaves_no_generation(self) -> None:
        bundle = _bundle()
        horse_rows = bundle["fact_horse_performance"]
        assert isinstance(horse_rows, list)
        horse_rows.append(copy.deepcopy(horse_rows[0]))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(PostRaceReviewPublishError):
                publish_snapshot(
                    bundle,
                    root,
                    "review-test-05",
                    source_provenance={},
                )

            self.assertFalse(
                (root / "generations" / "review-test-05").exists()
            )


if __name__ == "__main__":
    unittest.main()
