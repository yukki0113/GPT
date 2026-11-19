"""JPDB read-only Reader candidate: synthetic deterministic cutoff tests."""
import importlib.util
import unittest
from pathlib import Path

import duckdb

FILE = Path(__file__).resolve().parents[1] / "src" / "jpdb_history_reader.py"
spec = importlib.util.spec_from_file_location("jpdb_history_reader", FILE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class JPDBHistoryReaderTests(unittest.TestCase):
    def setUp(self):
        self.db = duckdb.connect(":memory:")
        self.db.execute("""CREATE TABLE sed_all(
          race_date VARCHAR, surface_code VARCHAR, jockey_code VARCHAR,
          abnormal_code VARCHAR, finish INTEGER, race_key_raw VARCHAR, horse_no INTEGER)""")
        self.db.executemany("INSERT INTO sed_all VALUES (?, ?, ?, ?, ?, ?, ?)", [
          ("2023-01-01","1","12345","0",1,"old",1),
          ("2024-11-14","1","12345","0",1,"a",1),
          ("2024-11-14","1","12345","0",2,"b",1),
          ("2024-11-14","2","12345","3",None,"c",1),
          ("2024-11-14","2","12345","1",None,"d",1),
          ("2024-11-14","1","12345","5",3,"e",1),
          ("2024-11-14","3","12345","0",1,"obstacle",1),
          ("2024-11-15","1","12345","0",1,"same-day",1),
          ("2024-11-16","1","12345","0",1,"future",1),
          ("2024-11-14","1","98765","0",1,"other",1),
        ])

    def tearDown(self):
        self.db.close()

    def test_d_exclusive_and_categories(self):
        r = mod._query(self.db,"2024-11-15","12345")
        self.assertEqual(r["all_flat"]["entries"],6)
        self.assertEqual(r["all_flat"]["normal_finishes"],3)
        self.assertEqual(r["all_flat"]["wins"],2)
        self.assertEqual(r["all_flat"]["top3"],3)
        self.assertEqual(r["all_flat"]["nonstarters"],1)
        self.assertEqual(r["all_flat"]["dnf"],1)
        self.assertEqual(r["all_flat"]["demoted"],1)
        self.assertEqual(r["by_surface"]["turf"]["entries"],4)
        self.assertEqual(r["by_surface"]["dirt"]["entries"],2)
        self.assertEqual(r["all_flat"]["latest_date"],"2024-11-14")
        self.assertEqual(r["all_flat"]["normal_win_rate"],2/3)
        self.assertEqual(r["asof_policy"],mod.POLICY)
        self.assertEqual(r["availability_basis"],"ASSUMED_PREVIOUS_DAY")
        self.assertFalse(r["prediction_safe_strict_asof"])
        self.assertTrue(r["assumption_based_backtest_eligible"])

    def test_zero_history(self):
        r = mod._query(self.db,"2024-11-15","54321")
        self.assertEqual(r["sample_status"],"NO_HISTORY")
        self.assertEqual(r["all_flat"]["entries"],0)
        self.assertIsNone(r["all_flat"]["normal_win_rate"])

    def test_early_boundary(self):
        r=mod._query(self.db,"2023-01-01","12345")
        self.assertEqual(r["all_flat"]["entries"],0)
        self.assertEqual(r["history_from_inclusive"],"2023-01-01")

    def test_future_and_input_validation(self):
        for dt in ("2022-12-31","2026-01-01","2025-02-30","2025-1-1"):
            with self.subTest(dt=dt),self.assertRaises(mod.JPDBHistoryReaderError):
                mod._query(self.db,dt,"12345")
        for code in ("00000","12","123456","A1234","' OR 1=1 --",None):
            with self.subTest(code=code),self.assertRaises(mod.JPDBHistoryReaderError):
                mod._query(self.db,"2024-11-15",code)


if __name__ == "__main__":
    unittest.main()
