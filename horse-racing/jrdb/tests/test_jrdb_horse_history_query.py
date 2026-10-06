import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jrdb_horse_history_query import HorseHistoryError, query


def _db(path):
    con=sqlite3.connect(path)
    con.execute("CREATE TABLE fact_entry_result_lite (horse_id TEXT, race_date TEXT, race_key TEXT, horse_no INTEGER, venue_code TEXT, race_no INTEGER, track_type TEXT, distance INTEGER, frame_no INTEGER, finish_position INTEGER, odds REAL, popularity INTEGER)")
    con.executemany("INSERT INTO fact_entry_result_lite VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",[("h1","2024-01-01","r1",1,"01",1,"T",1200,1,1,2.1,1),("h1","2024-03-01","r2",2,"02",3,"D",1800,4,4,8.0,4),("h1","2024-05-01","r3",3,"03",6,"T",1600,6,2,3.5,2),("h2","2024-02-01","r4",1,"01",1,"T",1200,1,1,1.2,1)])
    con.commit(); con.close()


class HorseHistoryTests(unittest.TestCase):
    def test_exact_horse_dates_order_limit_and_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            db=Path(temp)/"analysis.sqlite"; _db(db)
            out=query(horse_id="h1",analysis_db=db,from_date="2024-02-01",to_date="2024-05-01",limit=1,order="desc")
            self.assertEqual(out["schema_version"],"jrdb-horse-history/v1")
            self.assertEqual(out["source_provenance"]["backend"],"sqlite_compatibility")
            self.assertEqual([r["race_key"] for r in out["starts"]],["r3"])
            self.assertEqual(out["starts"][0]["race_horse_key"],"r303")
            all_rows=query(horse_id="h1",analysis_db=db)
            self.assertEqual([r["race_key"] for r in all_rows["starts"]],["r1","r2","r3"])
            self.assertTrue(all(r["horse_id"]=="h1" for r in all_rows["starts"]))

    def test_duplicate_start_guard_and_date_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            db=Path(temp)/"analysis.sqlite"; _db(db)
            con=sqlite3.connect(db); con.execute("INSERT INTO fact_entry_result_lite VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",("h1","2024-01-01","r1",1,"01",1,"T",1200,1,1,2.1,1)); con.commit(); con.close()
            with self.assertRaisesRegex(HorseHistoryError,"duplicate"): query(horse_id="h1",analysis_db=db)
            with self.assertRaisesRegex(ValueError,"YYYY-MM-DD"): query(horse_id="h1",analysis_db=db,from_date="20240101")

    def test_duckdb_missing_dependency_guidance(self):
        import builtins
        original=builtins.__import__
        def missing(name,*args,**kwargs):
            if name=="duckdb": raise ImportError("not installed")
            return original(name,*args,**kwargs)
        with tempfile.TemporaryDirectory() as temp, patch("builtins.__import__",side_effect=missing):
            with self.assertRaisesRegex(HorseHistoryError,"Actions fallback"): query(horse_id="h1",analysis_root=temp)

if __name__ == "__main__": unittest.main()
