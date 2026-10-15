#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import duckdb

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import racenote_rrdb_enrichment as rrdb  # noqa: E402


class FakeReader:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.generation_id = "rrdb-test"
        self.manifest = {
            "relations": {
                "fact_horse_performance": {
                    "partitions": [{"relative_path": "hp.parquet"}]
                },
                "fact_race_context": {
                    "partitions": [{"relative_path": "rc.parquet"}]
                },
            }
        }


class RaceNoteRRDBV05Test(unittest.TestCase):
    def test_missing_course_fit_root_fails_closed(self) -> None:
        bundle = {
            "schema_version": "1.0",
            "race": {"date": "2026-10-18", "venue": "東京", "race_no": 1},
            "horses": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            paci = Path(tmp) / "paci.zip"
            paci.write_bytes(b"x")
            with self.assertRaises(rrdb.RRDBEnrichmentError):
                rrdb._course_profile_context(
                    [bundle],
                    paci,
                    Path(tmp) / "missing-course-fit",
                )

    def test_course_profile_context_filters_bac_to_target_date(self) -> None:
        bundle = {
            "schema_version": "1.0",
            "race": {"date": "2026-10-18", "venue": "東京", "race_no": 1},
            "horses": [
                {"basic": {"horse_no": 1, "horse_id": "H1", "horse_name": "A"}}
            ],
        }
        rows = {
            "0526A101": {
                "date_raw": "20261017",
                "race_key_raw": "0526A101",
                "surface_code": "1",
            },
            "0526B101": {
                "date_raw": "20261018",
                "race_key_raw": "0526B101",
                "surface_code": "1",
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paci = root / "paci.zip"
            paci.write_bytes(b"x")
            fit = root / "fit"
            fit.mkdir()
            candidate = fit / "candidate_fit_view.parquet"
            candidate.write_bytes(b"x")
            with (
                mock.patch.object(rrdb, "_parse_target_races", return_value=rows),
                mock.patch.object(
                    rrdb,
                    "_load_course_profile_sources",
                    return_value=(candidate, [], []),
                ),
                mock.patch.object(
                    rrdb,
                    "_target_course_profile",
                    return_value={
                        "eligible": True,
                        "surface_code": "1",
                        "course_size_class": "LARGE",
                        "final_straight_bucket": "LONG",
                    },
                ) as target_profile,
            ):
                got_candidate, profiles = rrdb._course_profile_context(
                    [bundle], paci, fit
                )
            self.assertEqual(got_candidate, candidate)
            self.assertEqual(profiles["H1"]["course_size_class"], "LARGE")
            target_profile.assert_called_once()
            self.assertEqual(
                target_profile.call_args.args[0]["date_raw"],
                "20261018",
            )

    def test_course_profile_fit_can_match_without_prior_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            con = duckdb.connect(":memory:")
            try:
                con.execute("""
                    CREATE TABLE hp(
                        horse_id VARCHAR,
                        race_key VARCHAR,
                        race_date DATE,
                        horse_no INTEGER,
                        finish INTEGER,
                        time_sec DOUBLE,
                        surface_code VARCHAR,
                        horse_adjusted_delta_per_1000m DOUBLE,
                        winner_gap_sec DOUBLE,
                        corner4_frontness DOUBLE,
                        last3f_speed_percentile DOUBLE,
                        time_class_equivalent VARCHAR,
                        time_class_equivalent_numeric DOUBLE
                    )
                """)
                con.execute("""
                    INSERT INTO hp VALUES
                    ('OTHER','X','2026-01-01',1,1,100.0,'1',0.0,0.0,0.5,0.5,NULL,NULL)
                """)
                con.execute("""
                    CREATE TABLE rc(
                        race_key VARCHAR,
                        pace_balance_percentile DOUBLE
                    )
                """)
                con.execute("INSERT INTO rc VALUES ('X',0.5)")
                hp_path = str(root / "hp.parquet").replace("'", "''")
                rc_path = str(root / "rc.parquet").replace("'", "''")
                con.execute(f"COPY hp TO '{hp_path}' (FORMAT PARQUET)")
                con.execute(f"COPY rc TO '{rc_path}' (FORMAT PARQUET)")
                con.execute("""
                    CREATE TABLE fit(
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
                    "INSERT INTO fit VALUES (?,?,?,?,?,?,?,?,?)",
                    [
                        ("H1","1","2026-01-01","ABSOLUTE","COURSE_SIZE","LARGE",4,0.10,0.50),
                        ("H1","1","2026-01-01","ABSOLUTE","FINAL_STRAIGHT_BUCKET","LONG",5,0.12,0.60),
                    ],
                )
                fit_path = str(root / "fit.parquet").replace("'", "''")
                con.execute(f"COPY fit TO '{fit_path}' (FORMAT PARQUET)")
            finally:
                con.close()

            got = rrdb._latest_recommendation(
                FakeReader(root),
                ["H1"],
                "2026-10-18",
                candidate_fit_path=root / "fit.parquet",
                target_profiles={
                    "H1": {
                        "eligible": True,
                        "surface_code": "1",
                        "course_size_class": "LARGE",
                        "final_straight_bucket": "LONG",
                    }
                },
            )
            item = got["H1"]
            self.assertEqual(item["status"], "MATCH")
            self.assertIsNone(item["source_run"])
            self.assertEqual(item["matched_signal_ids"], ["COURSE_PROFILE_FIT"])
            self.assertEqual(item["contract_version"], "rrdb-recommendation-signals-v0.5")
            self.assertEqual(item["human_summary"], "大箱コースで好走傾向")
            self.assertEqual(item["course_profile_fit"]["as_of_date"], "2026-01-01")


if __name__ == "__main__":
    unittest.main()
