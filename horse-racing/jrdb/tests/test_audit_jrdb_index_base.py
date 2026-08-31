#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Synthetic audit test for JRDB Index Base."""

from __future__ import annotations

import sqlite3
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from audit_jrdb_index_base import audit  # noqa: E402


class IndexBaseAuditTest(unittest.TestCase):
    """Verify the audit tool on a minimal valid database."""

    def test_minimal_valid_database_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            db = temp / "index.sqlite"
            schema = (PROJECT_ROOT / "schema" / "jrdb_index_base_schema_v0_1.sql").read_text(
                encoding="utf-8"
            )
            connection = sqlite3.connect(db)
            try:
                connection.executescript(schema)
                connection.execute(
                    """
                    INSERT INTO meta_index_base_build(
                      builder_version,schema_version,started_at,finished_at,status,years_json,
                      race_count,race_result_context_count,runner_pre_count,runner_result_count,
                      workout_count,training_count,profile_observation_count,anomaly_count
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        "test",
                        "v0.1",
                        "2026-08-31T00:00:00",
                        "2026-08-31T00:01:00",
                        "SUCCESS",
                        "[2020]",
                        1,
                        1,
                        1,
                        1,
                        0,
                        0,
                        1,
                        0,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO race_context(
                      race_key,race_date,year,venue_code,race_no,availability_class,
                      source_kind,record_hash
                    ) VALUES(?,?,?,?,?,?,?,?)
                    """,
                    ("0520A101", "2020-08-30", 2020, "05", 1, "PRE_RACE", "BAC", "r"),
                )
                connection.execute(
                    "INSERT INTO race_result_context(race_key,track_condition_code,semantic_hash) VALUES(?,?,?)",
                    ("0520A101", "10", "c"),
                )
                connection.execute(
                    """
                    INSERT INTO runner_pre(
                      race_key,horse_no,horse_id,horse_name,record_hash
                    ) VALUES(?,?,?,?,?)
                    """,
                    ("0520A101", 1, "20170001", "テスト", "p"),
                )
                connection.execute(
                    """
                    INSERT INTO runner_previous_link(
                      race_key,horse_no,sequence,prev_result_key,prev_race_key
                    ) VALUES(?,?,?,?,?)
                    """,
                    ("0520A101", 1, 1, None, None),
                )
                connection.execute(
                    """
                    INSERT INTO runner_result(
                      race_key,horse_no,result_key,horse_id,horse_name,finish,time_sec,
                      carried_weight_kg,first3f_sec,last3f_sec,body_weight_kg,corner4,
                      record_hash
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        "0520A101",
                        1,
                        "2017000120200830",
                        "20170001",
                        "テスト",
                        1,
                        94.2,
                        57.0,
                        35.0,
                        34.5,
                        480,
                        1,
                        "x",
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO horse_profile_observation(
                      horse_id,data_date,horse_name,semantic_hash,record_hash
                    ) VALUES(?,?,?,?,?)
                    """,
                    ("20170001", "2020-08-01", "テスト", "h", "hr"),
                )
                connection.commit()
            finally:
                connection.close()

            report = audit(db, include_db_sha256=False)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["coverage"]["runner_pre_to_result_match_rate"], 1.0)
            self.assertEqual(report["coverage"]["horse_id_match_rate"], 1.0)
            self.assertEqual(report["coverage"]["profile_asof_rate"], 1.0)
            self.assertTrue(report["checks"]["no_duplicate_business_keys"])


if __name__ == "__main__":
    unittest.main()
