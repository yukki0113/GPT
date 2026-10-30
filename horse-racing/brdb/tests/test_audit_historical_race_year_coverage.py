import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audit_historical_race_year_coverage import classify_temporal, evaluate, parse_paci

class HistoricalAuditTests(unittest.TestCase):
    def test_future_observation_not_verified(self):
        value={"status":"AVAILABLE_ANNUAL_SNAPSHOT","profile":{"sire_name":"X"},
               "observed_date":"20200101","profile_data_date":"20190101"}
        self.assertEqual(classify_temporal(value,"20191231"),"AS_OF_UNVERIFIED")
        self.assertEqual(classify_temporal(value,"20200101"),"AS_OF_VERIFIED_DATE_ONLY")

    def test_no_source_is_unverified(self):
        self.assertEqual(classify_temporal({"profile":None,"status":"UNSUPPORTED_ANNUAL_HISTORY"},"20180101"),"AS_OF_UNVERIFIED")

    def test_repeat_starts_are_separate_entries(self):
        class Fake:
            facts={"12345678":{}}
            def horse_profile(self, horse_id, *, as_of):
                return {"status":"UNKNOWN_HORSE_ID","profile":None}
        rows=[{"race_date":"20180101","race_key":"0118AB01","horse_id":"12345678"},
              {"race_date":"20180102","race_key":"0118AB02","horse_id":"12345678"}]
        result=evaluate(rows,Fake())[0]
        self.assertEqual(result["kyi_declarations"],2)
        self.assertEqual(result["distinct_horses"],1)
        self.assertEqual(result["static_join_entries"],2)
        self.assertEqual(result["as_of_verified_date_only_entries"],0)

    def test_empty_inventory_fail_closed(self):
        with self.assertRaises(ValueError):
            parse_paci(Path("."), [])
if __name__=="__main__":
    unittest.main()
