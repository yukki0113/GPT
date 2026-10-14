#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import duckdb

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from jrdb_recommendation_reverse import (  # noqa: E402
    COURSE_PROFILE_MIN_CONFIDENCE,
    COURSE_PROFILE_MIN_SAMPLE,
    COURSE_PROFILE_MIN_SHRUNK_DELTA,
    VERSION,
    _course_profile_fit,
    _target_course_profile,
)


class RecommendationReverseV04Test(unittest.TestCase):
    def test_contract_version_and_thresholds(self) -> None:
        self.assertEqual(VERSION, "rrdb-recommendation-reverse-v0.4")
        self.assertEqual(COURSE_PROFILE_MIN_SAMPLE, 4)
        self.assertEqual(COURSE_PROFILE_MIN_SHRUNK_DELTA, 0.10)
        self.assertEqual(COURSE_PROFILE_MIN_CONFIDENCE, 0.50)

    def test_paired_large_long_fit_matches_at_fixed_threshold(self) -> None:
        con = duckdb.connect(":memory:")
        try:
            con.execute("""
                CREATE TABLE course_fit(
                    horse_id VARCHAR,
                    surface_code VARCHAR,
                    as_of_date DATE,
                    fit_family VARCHAR,
                    feature_type VARCHAR,
                    feature_value VARCHAR,
                    sample_count INTEGER,
                    shrunk_delta DOUBLE,
                    confidence DOUBLE
                )
            """)
            con.executemany(
                "INSERT INTO course_fit VALUES (?,?,?,?,?,?,?,?,?)",
                [
                    ("H1", "1", "2026-01-01", "ABSOLUTE", "COURSE_SIZE", "LARGE", 4, 0.10, 0.50),
                    ("H1", "1", "2026-01-01", "ABSOLUTE", "FINAL_STRAIGHT_BUCKET", "LONG", 5, 0.12, 0.60),
                ],
            )
            result = _course_profile_fit(
                con,
                horse_id="H1",
                surface_code="1",
                target_date="2026-10-18",
            )
            self.assertTrue(result["match"])
            self.assertEqual(result["large_sample_count"], 4)
            self.assertEqual(result["long_sample_count"], 5)
        finally:
            con.close()

    def test_paired_fit_fails_if_one_axis_is_below_threshold(self) -> None:
        con = duckdb.connect(":memory:")
        try:
            con.execute("""
                CREATE TABLE course_fit(
                    horse_id VARCHAR,
                    surface_code VARCHAR,
                    as_of_date DATE,
                    fit_family VARCHAR,
                    feature_type VARCHAR,
                    feature_value VARCHAR,
                    sample_count INTEGER,
                    shrunk_delta DOUBLE,
                    confidence DOUBLE
                )
            """)
            con.executemany(
                "INSERT INTO course_fit VALUES (?,?,?,?,?,?,?,?,?)",
                [
                    ("H1", "1", "2026-01-01", "ABSOLUTE", "COURSE_SIZE", "LARGE", 4, 0.10, 0.50),
                    ("H1", "1", "2026-01-01", "ABSOLUTE", "FINAL_STRAIGHT_BUCKET", "LONG", 4, 0.09, 0.90),
                ],
            )
            result = _course_profile_fit(
                con,
                horse_id="H1",
                surface_code="1",
                target_date="2026-10-18",
            )
            self.assertFalse(result["match"])
        finally:
            con.close()

    def test_target_course_must_be_large_and_long(self) -> None:
        race = {
            "race_key_raw": "0526A101",
            "surface_code": "1",
            "distance_raw": "1600",
            "turn_code": "1",
            "layout_code": "1",
            "course_code": "1",
        }
        # The exact course_key is intentionally taken from the canonical identity
        # function in the production helper.
        from jrdb_course_profile_identity import course_key_from_observation
        key = course_key_from_observation("05", "1", 1600, "1", "1")
        masters = [{
            "course_key": key,
            "layout_variant": "main",
            "course_size_class": "LARGE",
            "final_straight_m": 525.9,
            "physical_valid_from": "2023-01-01",
            "physical_valid_to_exclusive": None,
        }]
        geometry = [{
            "venue_code": "05",
            "surface_code": "1",
            "layout_variant": "main",
            "jrdb_course_code": "1",
            "course_size_class": "LARGE",
            "final_straight_m": 525.9,
            "physical_valid_from": "2023-01-01",
            "physical_valid_to_exclusive": None,
        }]
        result = _target_course_profile(
            race,
            "2026-10-18",
            masters,
            geometry,
        )
        self.assertTrue(result["eligible"])
        self.assertEqual(result["course_size_class"], "LARGE")
        self.assertEqual(result["final_straight_bucket"], "LONG")


if __name__ == "__main__":
    unittest.main()
