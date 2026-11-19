"""JPDB P3 synthetic regression: D-exclusion, race integrity and OOT peer baselines."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import duckdb
from jpdb_p3_market_baselines import prepare, validate


class P3MarketResearchTests(unittest.TestCase):
    def setUp(self):
        self.db=duckdb.connect(":memory:")
        self.db.execute("""CREATE TABLE p3_all (
            race_date VARCHAR, race_key_raw VARCHAR, horse_no INTEGER,
            jockey_code VARCHAR,surface_code VARCHAR,abnormal_code VARCHAR,
            finish INTEGER,field_size INTEGER,final_win_odds DOUBLE,
            final_popularity INTEGER,venue_code VARCHAR)""")

    def race(self,key,day,*,missing_odds=False,two_winners=False,demotion=False):
        rows=[
            (day,key,1,"10001","1","0",1,3,2.0,1,"01"),
            (day,key,2,"10002","1","0",1 if two_winners else 2,3,3.0,2,"01"),
            (day,key,3,"10003","1","5" if demotion else "3",None,3,6.0,3,"01"),
        ]
        if missing_odds:
            row=list(rows[1]);row[8]=None;rows[1]=tuple(row)
        self.db.executemany("INSERT INTO p3_all VALUES (?,?,?,?,?,?,?,?,?,?,?)",rows)

    def test_same_date_excluded_and_market_race_conserved(self):
        self.race("23010101","2023-01-01")
        self.race("24010101","2024-01-01")
        self.race("24010102","2024-01-02")
        prepare(self.db,"2024-01-02")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM p3_eval").fetchone()[0],6)
        self.assertEqual(self.db.execute("SELECT SUM(win) FROM p3_eval").fetchone()[0],2)
        self.assertAlmostEqual(self.db.execute("SELECT SUM(market_p) FROM p3_eval").fetchone()[0],2)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM p3_eval WHERE race_date>='2024-01-02'").fetchone()[0],0)
        self.assertEqual(validate(self.db,"2024-01-02",9)["market_eligible_rows"],6)

    def test_leave_one_rider_out_uses_only_prior_calendar_year(self):
        for year in (2023,2024,2025):
            self.race(str(year)+"0101",f"{year}-01-01")
        prepare(self.db,"2026-01-01")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM p3_eval WHERE event_year='2023' AND n_train IS NOT NULL").fetchone()[0],0)
        self.assertEqual(self.db.execute("SELECT SUM(n_train) FROM p3_eval WHERE event_year='2024'").fetchone()[0],5)
        self.assertEqual(self.db.execute("SELECT SUM(n_train) FROM p3_eval WHERE event_year='2025'").fetchone()[0],10)
        peer=self.db.execute("""SELECT n_prior_peer FROM p3_eval
           WHERE event_year='2024' AND jockey_code='10002'""").fetchone()[0]
        self.assertEqual(peer,1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM p3_eval WHERE empirical_prior_p IS NOT NULL").fetchone()[0],0)

    def test_incomplete_odds_demotion_or_duplicate_win_rejects_whole_race(self):
        self.race("23010101","2023-01-01")
        self.race("23010102","2023-01-02",missing_odds=True)
        self.race("23010103","2023-01-03",two_winners=True)
        self.race("23010104","2023-01-04",demotion=True)
        prepare(self.db,"2023-02-01")
        self.assertEqual(self.db.execute("SELECT COUNT(DISTINCT race_key_raw) FROM p3_eval").fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT SUM(top3) FROM p3_eval").fetchone()[0],2)
        self.assertEqual(self.db.execute("SELECT bad_statuses FROM p3_race WHERE race_key_raw='23010104'").fetchone()[0],1)

    def tearDown(self):
        self.db.close()


if __name__=="__main__":
    unittest.main()
