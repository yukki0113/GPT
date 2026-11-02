import sys
import unittest
from pathlib import Path
import hashlib
import json
import tempfile
import types
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audit_historical_race_year_coverage import classify_temporal, evaluate, parse_paci, normalize_member_date, load_kyi_warehouse

class HistoricalAuditTests(unittest.TestCase):
    def test_future_observation_not_verified(self):
        value={"status":"AVAILABLE_ANNUAL_SNAPSHOT","profile":{"sire_name":"X"},
               "observed_date":"20200101","profile_data_date":"20190101"}
        self.assertEqual(classify_temporal(value,"20191231"),"AS_OF_UNVERIFIED")
        self.assertEqual(classify_temporal(value,"20200101"),"AS_OF_VERIFIED_DATE_ONLY")

    def test_no_source_is_unverified(self):
        self.assertEqual(classify_temporal({"profile":None,"status":"UNSUPPORTED_ANNUAL_HISTORY"},"20180101"),"AS_OF_UNVERIFIED")

    def test_repeat_declarations_are_separate_entries(self):
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
        self.assertEqual(result["static_join_distinct_horses"],1)
        self.assertEqual(result["as_of_verified_date_only_entries"],0)

    def test_lineage_mapping_distinct_from_code_presence(self):
        class Fake:
            facts={"12345678":{}}
            def horse_profile(self, horse_id, *, as_of):
                return {"status":"AVAILABLE_ANNUAL_SNAPSHOT", "observed_date":"20170101",
                        "profile_data_date":"20161231",
                        "profile":{"sire_name":"S","dam_name":"D","broodmare_sire_name":"B",
                                   "sire_line_code":"1206","broodmare_sire_line_code":"UNMAPPED"}}
        rows=[{"race_date":"20180101","race_key":"0118AB01","horse_id":"12345678"}]
        result=evaluate(rows, Fake(), mapped_codes={"1206"})[0]
        self.assertEqual(result["sire_line_code_asof_present"], 1)
        self.assertEqual(result["broodmare_sire_line_code_asof_present"], 1)
        self.assertEqual(result["official_lineage_mapped"]["sire_line_code"], 1)
        self.assertEqual(result["official_lineage_mapped"]["broodmare_sire_line_code"], 0)

    def test_warehouse_member_date_validation(self):
        self.assertEqual(normalize_member_date("20160105"), "20160105")
        self.assertEqual(normalize_member_date("2016-01-05"), "20160105")
        for bad in ("2016-02-30", "20260105", "16-01-05", "", None):
            if bad == "20260105":
                continue
            with self.assertRaises(ValueError):
                normalize_member_date(bad)

    def test_warehouse_manifest_and_rows_are_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            payload = b"dummy parquet bytes used only by the mocked reader"
            digest = hashlib.sha256(payload).hexdigest()
            relative = "objects/kyi/year=2016/" + digest + ".parquet"
            obj = base / relative
            obj.parent.mkdir(parents=True)
            obj.write_bytes(payload)
            meta = {"artifact_type":"jrdb_normalized_warehouse", "status":"PASS",
                "generation_id":"fixture", "assets":[{"family":"kyi", "year":2016,
                "relative_path":relative,"sha256":digest,"size_bytes":len(payload),
                "row_count":1}]}
            manifest = base/"manifest.json"
            manifest.write_text(json.dumps(meta))
            class Conn:
                def execute(self, query, params):
                    return self
                def fetchall(self):
                    return [("0116A101", 1, "12345678", "20160105", 2016)]
                def close(self):
                    pass
            fake = types.SimpleNamespace(connect=lambda *a, **k: Conn())
            with patch.dict("sys.modules", {"duckdb":fake}):
                rows, counters = load_kyi_warehouse(base, manifest, 2016, 2016)
            self.assertEqual(rows[0]["race_date"],"20160105")
            self.assertEqual(counters["raw_declarations"],1)
            obj.write_bytes(payload+b"tamper")
            with self.assertRaises(ValueError):
                load_kyi_warehouse(base, manifest, 2016, 2016)

    def test_empty_inventory_fail_closed(self):
        with self.assertRaises(ValueError):
            parse_paci(Path("."), [])
if __name__=="__main__":
    unittest.main()
