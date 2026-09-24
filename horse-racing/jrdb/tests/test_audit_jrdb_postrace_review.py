#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import math
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from audit_jrdb_postrace_review import (  # noqa: E402
    audit_review_bundle,
    canonical_bundle_hash,
)


def _bundle() -> dict[str, object]:
    return {
        "fact_race_context": [
            {
                "race_key": "T001",
                "race_date": "2025-03-15",
                "pace_shape": "FRONT_LOADED",
                "review_schema_version": "v0.1",
                "review_logic_version": "v0.1.1",
            }
        ],
        "fact_race_review": [
            {
                "race_key": "T001",
                "race_date": "2025-03-15",
                "historical_standard_time_sec": 95.0,
                "standard_sample_end_date": "2025-03-10",
                "day_adjustment_applied": True,
                "class_curve_monotonic": True,
                "review_schema_version": "v0.1",
                "review_logic_version": "v0.1.1",
            }
        ],
        "fact_horse_performance": [
            {
                "race_key": "T001",
                "race_horse_key": "T00101",
                "horse_no": 1,
                "race_date": "2025-03-15",
                "review_schema_version": "v0.1",
                "review_logic_version": "v0.1.1",
            },
            {
                "race_key": "T001",
                "race_horse_key": "T00102",
                "horse_no": 2,
                "race_date": "2025-03-15",
                "review_schema_version": "v0.1",
                "review_logic_version": "v0.1.1",
            },
        ],
    }


class JrdbPostRaceReviewAuditTest(unittest.TestCase):
    def test_valid_bundle_passes(self) -> None:
        bundle = _bundle()
        result = audit_review_bundle(
            bundle,
            expected_target_date="2025-03-15",
        )

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["hard_error_count"], 0)
        self.assertIsNotNone(result["canonical_bundle_hash"])
        self.assertEqual(
            result["row_counts"]["fact_horse_performance"],
            2,
        )

    def test_bundle_hash_is_stable_under_row_and_key_order(self) -> None:
        first = _bundle()
        second = _bundle()
        horse_rows = second["fact_horse_performance"]
        assert isinstance(horse_rows, list)
        horse_rows.reverse()
        second_context = second["fact_race_context"][0]
        assert isinstance(second_context, dict)
        second["fact_race_context"][0] = {
            key: second_context[key]
            for key in reversed(list(second_context))
        }

        self.assertEqual(
            canonical_bundle_hash(first),
            canonical_bundle_hash(second),
        )

    def test_duplicate_horse_key_fails(self) -> None:
        bundle = _bundle()
        horse_rows = bundle["fact_horse_performance"]
        assert isinstance(horse_rows, list)
        horse_rows.append(copy.deepcopy(horse_rows[0]))

        result = audit_review_bundle(bundle)

        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(
            any(
                error["code"] == "DUPLICATE_KEY"
                and error["relation"] == "fact_horse_performance"
                for error in result["hard_errors"]
            )
        )

    def test_orphan_horse_race_fails(self) -> None:
        bundle = _bundle()
        horse_rows = bundle["fact_horse_performance"]
        assert isinstance(horse_rows, list)
        horse_rows[0]["race_key"] = "T999"

        result = audit_review_bundle(bundle)

        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(
            any(
                error["code"] == "ORPHAN_HORSE_RACE"
                for error in result["hard_errors"]
            )
        )

    def test_standard_future_leakage_fails(self) -> None:
        bundle = _bundle()
        race_rows = bundle["fact_race_review"]
        assert isinstance(race_rows, list)
        race_rows[0]["standard_sample_end_date"] = "2025-03-15"

        result = audit_review_bundle(bundle)

        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(
            any(
                error["code"] == "STANDARD_FUTURE_LEAKAGE"
                for error in result["hard_errors"]
            )
        )

    def test_nonfinite_value_fails(self) -> None:
        bundle = _bundle()
        race_rows = bundle["fact_race_review"]
        assert isinstance(race_rows, list)
        race_rows[0]["historical_standard_time_sec"] = math.nan

        result = audit_review_bundle(bundle)

        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(
            any(
                error["code"] == "NONFINITE_NUMERIC"
                for error in result["hard_errors"]
            )
        )

    def test_missing_optional_evidence_is_warning_not_neutral(self) -> None:
        bundle = _bundle()
        race_rows = bundle["fact_race_review"]
        context_rows = bundle["fact_race_context"]
        assert isinstance(race_rows, list)
        assert isinstance(context_rows, list)
        race_rows[0]["historical_standard_time_sec"] = None
        race_rows[0]["day_adjustment_applied"] = False
        context_rows[0]["pace_shape"] = None

        result = audit_review_bundle(bundle)

        self.assertEqual(result["status"], "PASS")
        codes = {warning["code"] for warning in result["warnings"]}
        self.assertIn("MISSING_TIME_STANDARD", codes)
        self.assertIn("DAY_ADJUSTMENT_NOT_APPLIED", codes)
        self.assertIn("PACE_CLASSIFICATION_UNAVAILABLE", codes)

    def test_multi_day_snapshot_can_be_audited_explicitly(self) -> None:
        bundle = _bundle()
        context_rows = bundle["fact_race_context"]
        race_rows = bundle["fact_race_review"]
        horse_rows = bundle["fact_horse_performance"]
        assert isinstance(context_rows, list)
        assert isinstance(race_rows, list)
        assert isinstance(horse_rows, list)

        second_context = copy.deepcopy(context_rows[0])
        second_context["race_key"] = "T002"
        second_context["race_date"] = "2025-03-16"
        context_rows.append(second_context)

        second_race = copy.deepcopy(race_rows[0])
        second_race["race_key"] = "T002"
        second_race["race_date"] = "2025-03-16"
        race_rows.append(second_race)

        second_horse = copy.deepcopy(horse_rows[0])
        second_horse["race_key"] = "T002"
        second_horse["race_horse_key"] = "T00201"
        second_horse["race_date"] = "2025-03-16"
        horse_rows.append(second_horse)

        daily = audit_review_bundle(bundle)
        snapshot = audit_review_bundle(
            bundle,
            require_single_target_date=False,
        )

        self.assertEqual(daily["status"], "FAIL")
        self.assertTrue(
            any(
                error["code"] == "MULTIPLE_TARGET_DATES"
                for error in daily["hard_errors"]
            )
        )
        self.assertEqual(snapshot["status"], "PASS")

    def test_wrong_review_version_fails(self) -> None:
        bundle = _bundle()
        context_rows = bundle["fact_race_context"]
        assert isinstance(context_rows, list)
        context_rows[0]["review_logic_version"] = "v9"

        result = audit_review_bundle(bundle)

        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(
            any(
                error["code"] == "VERSION_CONTRACT_MISMATCH"
                for error in result["hard_errors"]
            )
        )


if __name__ == "__main__":
    unittest.main()
