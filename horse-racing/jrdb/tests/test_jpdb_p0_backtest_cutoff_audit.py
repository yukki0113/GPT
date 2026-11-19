"""Synthetic anti-leakage checks for P0 retro-only cutoff audit."""
import importlib.util
import sys
import unittest
from pathlib import Path

import duckdb

FILE=Path(__file__).resolve().parents[1]/"tools"/"jpdb_p0_backtest_cutoff_audit.py"
spec=importlib.util.spec_from_file_location("jpdb_cutoff",FILE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class CutoffTests(unittest.TestCase):
    def setUp(self):
        self.db=duckdb.connect(":memory:")
        self.db.execute("""CREATE TABLE sed_all(
            race_date VARCHAR, surface_code VARCHAR, jockey_code VARCHAR,
            abnormal_code VARCHAR, finish INTEGER, race_key_raw VARCHAR,
            horse_no INTEGER)""")
        self.db.executemany("INSERT INTO sed_all VALUES(?,?,?,?,?,?,?)",[
            ("2024-11-14","1","11111","0",1,"A",1),
            ("2024-11-15","1","11111","0",1,"B",1),
            ("2024-11-16","1","11111","0",1,"C",1),
            ("2024-11-14","2","22222","3",None,"D",1),
            ("2024-11-14","3","33333","0",1,"E",1),
            ("2024-11-14","1","22222","1",None,"F",1),
        ])

    def tearDown(self):
        self.db.close()

    def test_strict_target_day_exclusion_and_obstacle_exclusion(self):
        r=mod.audit_cutoff(self.db,mod.parse_target("2024-11-15"))
        self.assertEqual(r["historic_flat_race_entries"],3)
        self.assertEqual(r["historic_normal_finishes"],1)
        self.assertEqual(r["historic_nonstarters_codes_1_2"],1)
        self.assertEqual(r["historic_dnf_code_3"],1)
        self.assertEqual(r["historic_wins_normal_only"],1)
        self.assertEqual(r["flat_future_or_same_day_entries_excluded"],2)
        self.assertEqual(r["observed_max_history_date"],"2024-11-14")
        self.assertFalse(r["prediction_safe"])
        self.assertTrue(r["assumption_based_backtest_eligible"])
        self.assertEqual(r["sed_availability_policy_id"],"JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1")

    def test_empty_boundary_is_safe(self):
        r=mod.audit_cutoff(self.db,mod.parse_target("2023-01-01"))
        self.assertEqual(r["historic_flat_race_entries"],0)
        self.assertTrue(r["window_clamped_to_2023"])

    def test_date_rejects_outside_cohort(self):
        for x in ("2022-12-31","2026-01-01","2025-02-30","2025-1-1"):
            with self.subTest(x=x),self.assertRaises(ValueError):
                mod.parse_target(x)


if __name__=="__main__":
    unittest.main()
