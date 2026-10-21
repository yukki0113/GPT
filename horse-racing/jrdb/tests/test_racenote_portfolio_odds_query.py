import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from racenote_portfolio_odds_query import query

SOURCE={"provider":"verified_market_snapshot","as_of":"2025-04-26T15:00:00+09:00","kind":"closing_or_latest"}
SNAPSHOT={
    "schema_version":"racenote-odds-snapshot-v0.1",
    "source":SOURCE,
    "races":[{"race_key":"20250426-京都-10",
              "win":{"8":3.4},
              "quinella":{"5-8":12.8,"6-8":21.6},
              "exacta":{"8>5":18.2,"8>6":27.5}}]
}
class FiveOddsQueryTests(unittest.TestCase):
    def test_success(self):
        data=query(SNAPSHOT,"20250426-京都-10",8,5,6)
        self.assertEqual(data["status"],"success")
        self.assertEqual(data["odds"],{"win_1":3.4,"quinella_1_2":12.8,
             "quinella_1_3":21.6,"exacta_1_2":18.2,"exacta_1_3":27.5})
        self.assertEqual(data["source"],SOURCE)
    def test_quinella_is_unordered_but_exacta_is_ordered(self):
        data=query(SNAPSHOT,"20250426-京都-10",5,8,6)
        self.assertEqual(data["odds"]["quinella_1_2"],12.8)
        self.assertIsNone(data["odds"]["exacta_1_2"])
        self.assertEqual(data["status"],"partial")
    def test_missing_odds_are_never_invented(self):
        snap={**SNAPSHOT,"races":[{**SNAPSHOT["races"][0],"quinella":{"5-8":12.8}}]}
        data=query(snap,"20250426-京都-10",8,5,6)
        self.assertEqual(data["status"],"partial")
        self.assertIn("quinella_1_3",data["missing"])
    def test_unavailable_race(self):
        self.assertEqual(query(SNAPSHOT,"20250426-東京-10",8,5,6)["status"],"not_found")
    def test_wrong_price_source(self):
        snap={**SNAPSHOT,"source":{**SOURCE,"kind":"paci_base"}}
        with self.assertRaises(ValueError):query(snap,"20250426-京都-10",8,5,6)
    def test_duplicate_race(self):
        snap={**SNAPSHOT,"races":SNAPSHOT["races"]*2}
        with self.assertRaises(ValueError):query(snap,"20250426-京都-10",8,5,6)
    def test_invalid_horse_inputs(self):
        with self.assertRaises(ValueError):query(SNAPSHOT,"20250426-京都-10",8,8,6)
        with self.assertRaises(ValueError):query(SNAPSHOT,"20250426-京都-10",0,5,6)
if __name__=="__main__":
    unittest.main()
