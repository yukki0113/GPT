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
    _distance_bucket,
    _load_rear_srb_contract,
    _rear_srb_evidence,
    _target_course_profile,
)


class FakeRaceLapReader:
    def __init__(self, context):
        self.context = context

    def get_race_context(self, race_key: str):
        if self.context is None:
            return None
        return self.context if self.context["race"]["race_key"] == race_key else None


class RecommendationReverseV05Test(unittest.TestCase):
    def test_contract_version_and_course_profile_thresholds(self) -> None:
        self.assertEqual(VERSION, "rrdb-recommendation-reverse-v0.5")
        self.assertEqual(COURSE_PROFILE_MIN_SAMPLE, 4)
        self.assertEqual(COURSE_PROFILE_MIN_SHRUNK_DELTA, 0.10)
        self.assertEqual(COURSE_PROFILE_MIN_CONFIDENCE, 0.50)

    def test_rear_srb_contract_is_frozen_and_excludes_dirt_staying(self) -> None:
        contract = _load_rear_srb_contract()
        self.assertEqual(contract["version"], "rrdb-rear-srb-q20-v0.1")
        thresholds = {
            (row["surface_code"], row["distance_bucket"]): row
            for row in contract["thresholds"]
        }
        self.assertEqual(thresholds[("1", "MILE")]["early_late_delta_q20_sec"], -2.1)
        self.assertEqual(thresholds[("2", "SPRINT")]["early_late_delta_q20_sec"], 1.2)
        self.assertNotIn(("2", "STAYING"), thresholds)

    def test_distance_bucket_contract(self) -> None:
        self.assertEqual(_distance_bucket(1400), "SPRINT")
        self.assertEqual(_distance_bucket(1600), "MILE")
        self.assertEqual(_distance_bucket(2000), "MIDDLE")
        self.assertEqual(_distance_bucket(2400), "STAYING")

    def test_rear_srb_evidence_matches_at_q20_boundary(self) -> None:
        contract = _load_rear_srb_contract()
        reader = FakeRaceLapReader({
            "schema_version": "x",
            "logic_version": "y",
            "race": {
                "race_key": "0526A101",
                "race_date": "2026-09-01",
                "surface_code": "1",
                "distance_m": 1600,
            },
            "coverage": {"status": "AVAILABLE"},
            "shape": {"early_late_delta_sec": -2.1},
        })
        result = _rear_srb_evidence(
            reader,
            contract,
            {
                "race_key": "0526A101",
                "race_date": "2026-09-01",
                "surface_code": "1",
                "distance_m": 1600,
            },
        )
        self.assertTrue(result["match"])
        self.assertEqual(result["q20_sec"], -2.1)
        self.assertEqual(result["distance_bucket"], "MILE")

    def test_rear_srb_evidence_fails_closed_above_q20_or_missing_lap(self) -> None:
        contract = _load_rear_srb_contract()
        reader = FakeRaceLapReader({
            "schema_version": "x",
            "logic_version": "y",
            "race": {
                "race_key": "0526A101",
                "race_date": "2026-09-01",
                "surface_code": "1",
                "distance_m": 1600,
            },
            "coverage": {"status": "AVAILABLE"},
            "shape": {"early_late_delta_sec": -2.0},
        })
        result = _rear_srb_evidence(
            reader,
            contract,
            {
                "race_key": "0526A101",
                "race_date": "2026-09-01",
                "surface_code": "1",
                "distance_m": 1600,
            },
        )
        self.assertFalse(result["match"])
        self.assertEqual(result["reason"], "ABOVE_Q20_THRESHOLD")

        missing = _rear_srb_evidence(
            FakeRaceLapReader(None),
            contract,
            {
                "race_key": "0526A101",
                "race_date": "2026-09-01",
                "surface_code": "1",
                "distance_m": 1600,
            },
        )
        self.assertFalse(missing["match"])
        self.assertEqual(missing["reason"], "RACE_LAP_NOT_FOUND")

    def test_rear_srb_evidence_fails_closed_for_dirt_staying(self) -> None:
        contract = _load_rear_srb_contract()
        reader = FakeRaceLapReader({
            "schema_version": "x",
            "logic_version": "y",
            "race": {
                "race_key": "0526A101",
                "race_date": "2026-09-01",
                "surface_code": "2",
                "distance_m": 2400,
            },
            "coverage": {"status": "AVAILABLE"},
            "shape": {"early_late_delta_sec": -10.0},
        })
        result = _rear_srb_evidence(
            reader,
            contract,
            {
                "race_key": "0526A101",
                "race_date": "2026-09-01",
                "surface_code": "2",
                "distance_m": 2400,
            },
        )
        self.assertFalse(result["match"])
        self.assertEqual(result["reason"], "NO_FROZEN_Q20_THRESHOLD")

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


if __name__ == "__main__":
    unittest.main()
