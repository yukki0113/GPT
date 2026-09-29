import json
from datetime import date
from pathlib import Path
import unittest

from keirin_canonical.audit import summarize
from keirin_canonical.raw_archive import LogicalAssetRegistry, read_archives
from keirin_canonical.schema import validated_table
from keirin_canonical.stage_a_parser import ParseError, actual_dates, meet_key, parse, race_key


FIXTURE = Path(__file__).parent / "fixtures" / "canonical_stage_a.json"


def html_fixture(payload):
    return ("<script>var jsonData = {}; jsonData['PC0201'] = " + json.dumps({"C0201data":payload["base"]}) +
            "; jsonData['PJ0301'] = " + json.dumps({"raceDayDataList":payload["days"]}) + ";</script>").encode()


class StageATests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text())
        self.record = {"metadata":{"venue_code":"13","venue_name":"いわき平","grade":"F2"}}

    def test_keys_and_same_venue_separate_meets(self):
        self.assertEqual(meet_key("13",date(2016,2,6)),"13|2016-02-06")
        self.assertNotEqual(meet_key("13",date(2016,2,6)),meet_key("13",date(2016,2,20)))
        self.assertEqual(meet_key("13",date(2016,2,6),2),"13|2016-02-06|2")
        self.assertEqual(race_key(date(2016,2,6),"13",1),"20160206|13|1")

    def test_actual_dates_irregular_gap_and_year_boundary(self):
        days=[{"txtEventDate":x} for x in ("12/30","01/02","01/05")]
        self.assertEqual(actual_dates(days,date(2020,1,2)),[date(2019,12,30),date(2020,1,2),date(2020,1,5)])

    def test_provenance_and_cancelled_day(self):
        meet,races,dates,warnings=parse(html_fixture(self.fixture),self.record)
        self.assertEqual(meet["meet_start_date"],date(2016,2,6))
        self.assertEqual(races[1]["race_date"],date(2016,2,8))
        self.assertEqual(races[1]["cancellation_status"],"cancelled")
        self.assertEqual(races[0]["detail_token"],"official-token")
        self.assertEqual(races[0]["race_label_raw"],"Ａ級チャレンジ予選")
        self.assertEqual(warnings,[])

    def test_restarted_day_same_label_maps_to_distinct_actual_dates(self):
        fixture=json.loads(json.dumps(self.fixture))
        fixture["base"]["C0201kaisai"]=[{"txtEventDate":"02/06","txtDaily":"(初日)"},
                                           {"txtEventDate":"02/08","txtDaily":"(初日)"}]
        fixture["days"][1]["strRaceNitiji"]="初日（再）"
        _,races,_,_=parse(html_fixture(fixture),self.record)
        self.assertEqual([r["race_date"] for r in races],[date(2016,2,6),date(2016,2,8)])

    def test_embedded_json_absent_or_malformed(self):
        with self.assertRaisesRegex(ParseError,"missing_PC0201_json"):
            parse(b"<html>missing embedded data</html>",self.record)
        with self.assertRaisesRegex(ParseError,"malformed_PC0201_json"):
            parse(b"jsonData['PC0201'] = {bad;",self.record)

    def test_duplicate_detection(self):
        meet,races,days,_=parse(html_fixture(self.fixture),self.record)
        result=summarize([meet,meet],races+races,[],[],{meet["meet_key"]:set(days)},[],expected_assets=2)
        self.assertEqual(result["integrity"]["duplicate_meet_key"],1)
        self.assertEqual(result["integrity"]["duplicate_race_key"],len(races))
        self.assertEqual(result["status"],"fail")

    def test_schema_rejects_null_required(self):
        with self.assertRaisesRegex(ValueError,"meet_key"):
            validated_table("meet",[{"venue_code":"13"}])

    def test_archive_reader_never_writes_input(self):
        import hashlib, tempfile, zipfile
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"keirin-historical-2020.zip"
            with zipfile.ZipFile(path,"w") as z:
                z.writestr("audit/202001_events_manifest.json",json.dumps({"sources":[]}))
            before=hashlib.sha256(path.read_bytes()).digest()
            self.assertEqual(list(read_archives([path])),[])
            self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),before)

    def test_logical_asset_duplicate_sha_deduplicates_and_conflict_fails_closed(self):
        registry=LogicalAssetRegistry()
        self.assertTrue(registry.register("raw/2016/01/events/13_01.html","aaa"))
        self.assertFalse(registry.register("raw/2016/01/events/13_01.html","aaa"))
        with self.assertRaisesRegex(ValueError,"conflicting SHA-256"):
            registry.register("raw/2016/01/events/13_01.html","bbb")

    def test_january_supplemental_summary_manifest_schedule_sha(self):
        from hashlib import sha256
        from keirin_canonical.cli import _supplemental_audit
        import tempfile,zipfile
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"keirin-historical-2016-01-poc-1185.zip"
            schedule=b"official schedule raw"
            manifest={"requested_sources":60,"successful_sources":60,"failed_sources":0,
                      "sources":[{"status":"success","relative_path":f"2016/01/events/{i:02d}.html"} for i in range(60)]}
            source_list="\n".join(json.dumps({"n":i}) for i in range(60))
            summary={"discovered_events":60,"successful_events":60,"failed_events":0,
                     "schedule_sha256":sha256(schedule).hexdigest(),"schedule_url":"https://keirin.jp/pc/raceschedule",
                     "schedule_http_status":200,"generated_at_utc":"2026-09-21T17:32:26+00:00"}
            with zipfile.ZipFile(path,"w") as z:
                z.writestr("audit/201601_events_manifest.json",json.dumps(manifest))
                z.writestr("audit/201601_source_list.jsonl",source_list)
                z.writestr("audit/201601_summary.json",json.dumps(summary))
                z.writestr("raw/2016/01/schedule.html",schedule)
                for i in range(60):z.writestr(f"raw/2016/01/events/{i:02d}.html",b"html")
            result=_supplemental_audit(path)
            self.assertEqual(result["event_html_count"],60)
            self.assertEqual(result["raw_sha256"],sha256(schedule).hexdigest())
            self.assertEqual(result["failed_events"],0)


if __name__=="__main__":
    unittest.main()
