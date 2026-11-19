"""P1.1 synthetic evidence for batched population, time windows and v0.1 parity."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
import duckdb

SRC=Path(__file__).resolve().parents[1]/"src"
sys.path.insert(0,str(SRC))
from jpdb_performance_reader_v11 import _grouped, JPDBHistoryReaderError, POPULATION
from jpdb_history_reader import _query


class TestJPDBP11(unittest.TestCase):
    def setUp(self):
        self.db=duckdb.connect(":memory:")
        self.db.execute("""CREATE TABLE sed_all(
          race_date VARCHAR,surface_code VARCHAR,jockey_code VARCHAR,
          abnormal_code VARCHAR,finish INTEGER,field_size INTEGER,
          race_key_raw VARCHAR,horse_no INTEGER)""")
        self.db.executemany("INSERT INTO sed_all VALUES (?,?,?,?,?,?,?,?)",[
            ("2024-11-14","1","01234","0",1,16,"a",1),
            ("2024-11-14","1","01234","0",2,16,"b",1),
            ("2024-11-14","2","01234","3",None,16,"c",1),
            ("2024-11-14","2","01234","1",None,16,"d",1),
            ("2024-11-14","1","01234","5",3,16,"e",1),
            ("2024-11-14","2","01234","0",None,16,"f",1),
            ("2024-11-14","2","01234","X",None,16,"g",1),
            ("2024-11-14","1","22222","0",1,16,"h",1),
            ("2024-11-15","1","01234","0",1,16,"same",1),
            ("2024-11-16","1","01234","0",1,16,"future",1),
            ("2024-11-14","3","01234","0",1,16,"obstacle",1),
            ("2023-01-01","1","01234","0",1,16,"early",1),
            ("2024-01-01","1","01234","0",1,16,"past_365",1),
        ])

    def tearDown(self):
        self.db.close()

    def test_batch_and_complete_classification(self):
        b=_grouped(self.db,"2024-11-15",["01234","22222","33333"])
        self.assertEqual(b["population_filter_id"],POPULATION)
        a=b["jockey_histories"]["01234"]["windows"]["ROLLING_3Y"]["all_flat"]
        self.assertEqual(a["entries"],9)
        self.assertEqual(a["normal_finishers"],4)
        self.assertEqual(a["wins"],3) # 2024-11-14 + 2023 + 2024-01-01
        self.assertEqual(a["top2"],4)
        self.assertEqual(a["cancellations"],1)
        self.assertEqual(a["dnf"],1)
        self.assertEqual(a["demotion_review"],1)
        self.assertEqual(a["invalid_normal_finish"],1)
        self.assertEqual(a["unknown_codes"],1)
        self.assertEqual(a["unresolved_count"],3)
        self.assertIsNone(a["start_basis_win_rate_candidate"])
        self.assertEqual(a["start_rate_status"],"REVIEW_REQUIRED")
        self.assertEqual(a["last_observed"],"2024-11-14")
        self.assertEqual(b["jockey_histories"]["33333"]["sample_status"],"NO_HISTORY")

    def test_shorter_windows_and_no_leakage(self):
        r=_grouped(self.db,"2024-11-15",["01234"])["jockey_histories"]["01234"]
        self.assertEqual(r["windows"]["RECENT_90D"]["all_flat"]["entries"],7)
        self.assertEqual(r["windows"]["RECENT_365D"]["all_flat"]["entries"],8)
        self.assertEqual(r["windows"]["ROLLING_3Y"]["all_flat"]["entries"],9)
        self.assertTrue(r["assumption_based_backtest_eligible"])

    def test_clean_rates_and_v01_unchanged(self):
        b=_grouped(self.db,"2024-11-15",["22222"])
        r=b["jockey_histories"]["22222"]["windows"]["ROLLING_3Y"]["all_flat"]
        self.assertEqual(r["start_basis_win_rate_candidate"],1)
        self.assertEqual(r["sample_support_status"],"INSUFFICIENT")
        old=_query(self.db,"2024-11-15","22222")
        self.assertEqual(old["schema_version"],"jpdb-history-reader-v0.1")
        self.assertEqual(old["all_flat"]["wins"],1)

    def test_invalid_requests(self):
        for codes in ([],["01234","01234"],["0"],["00000"],["01234"]*65,"01234"):
            with self.subTest(codes=codes),self.assertRaises(JPDBHistoryReaderError):
                _grouped(self.db,"2024-11-15",codes)
        with self.assertRaises(JPDBHistoryReaderError):
            _grouped(self.db,"2026-01-01",["01234"])


if __name__=="__main__":
    unittest.main()
