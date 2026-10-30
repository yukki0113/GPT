"""v056 forward PACI safety and T1 execution seam regression tests."""
from __future__ import annotations
import hashlib
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import racenote_v056_forward_turn1 as forward
from racenote_v056_forward_drive_paci import CANONICAL_FOLDER_ID, VERSION as RECEIPT_VERSION

class ForwardPaciTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cwd=Path.cwd()
        os.chdir(self.temp.name)
        self.addCleanup(os.chdir,self.cwd)
        self.day="2026-10-31"
        self.root=Path("horse-racing/jrdb/daily/20261031/v056_day")
        self.paci=Path("PACI261031.zip")
        with zipfile.ZipFile(self.paci,"w") as z:
            z.writestr("KYI261031.TXT",b"safe-test")
        self.paci_sha=hashlib.sha256(self.paci.read_bytes()).hexdigest()
        self.receipt=Path("drive_source_receipt.json")
        self.receipt.write_text(json.dumps({
            "schema_version": RECEIPT_VERSION,
            "status": "DRIVE_PACI_VERIFIED",
            "source": "GOOGLE_DRIVE_CANONICAL_PACI",
            "canonical_folder_id": CANONICAL_FOLDER_ID,
            "drive_file_id": "1ABCDEFGHIJKLMNOPQRSTUVWXYZ12345",
            "target_date": self.day,
            "filename": self.paci.name,
            "sha256": self.paci_sha,
            "jrdb_direct_fetch": False,
        }), encoding="utf-8")
        self.lap=Path("lap")
        self.lap.mkdir()
        (self.lap/"race_lap.parquet").write_bytes(b"test-parquet-sha")
        self.lapsha=hashlib.sha256(b"test-parquet-sha").hexdigest()
        self.argv=[
            "prog","--date",self.day,"--paci",str(self.paci),
            "--paci-source-receipt",str(self.receipt),
            "--main-sha","a"*40,"--analysis-root","analysis",
            "--course-fit-root","fit","--racereview-root","rrdb",
            "--race-lap-current-bundle","lap",
            "--race-lap-expected-period-to","2026-10-30",
            "--output-root",str(self.root)]
    def run_args(self,extra=()):
        with patch.object(sys,"argv",self.argv+list(extra)):
            return forward.main()
    def test_reject_noncanonical_target(self):
        a=self.argv.copy();a[-1]="somewhere_else"
        with patch.object(sys,"argv",a),self.assertRaisesRegex(ValueError,"Noncanonical"):
            forward.main()
    def test_reject_wrong_paci_date(self):
        self.paci.rename("PACI261030.zip")
        a=self.argv.copy();a[a.index("--paci")+1]="PACI261030.zip"
        with patch.object(sys,"argv",a),self.assertRaisesRegex(ValueError,"Wrong PACI date"):
            forward.main()
    def test_reject_selection_mismatch(self):
        with self.assertRaisesRegex(ValueError,"selection-id/date mismatch"):
            self.run_args(["--selection-id","DAILY-20261030"])
    def test_reject_existing_canonical_root(self):
        self.root.mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            self.run_args()
    def test_builds_v056_reader_from_paci_without_creating_marks(self):
        def fake_prep(_cmd,check):
            self.root.mkdir(parents=True,exist_ok=True)
            (self.root/"day_prep"/"RaceNote_20261031").mkdir(parents=True)
            (self.root/"operation_handoff.json").write_text(json.dumps({
                "status":"FORECAST_PREP_READY",
                "selection_id":"DAILY-20261031","target_date":self.day,
                "paci":{"sha256":self.paci_sha},
                "race_lap_resolution":{
                    "status":"CURRENT_READY","updated":False,
                    "parquet_sha256":self.lapsha
                },
                "result_opened":False
            }),encoding="utf-8")
        session={"logic_version":"RaceNote-Human-Context-Reader-0.5.6-candidate",
                 "contract_revision":"v056-prediction-confidence-audit-newspaper-v1",
                 "reader_projection":"v055-lean-model-reader-r2",
                 "session_id":"V056-test",
                 "reader_manifest_sha256":"abc",
                 "race_roster":[{"venue":"東京","race_no":1}]}
        author={"status":"READY_FOR_LLM_RACE_BY_RACE_REVIEW",
                "prediction_policy":"LLM_RACE_BY_RACE_ONLY","race_count":1}
        with patch.object(forward.subprocess,"run",side_effect=fake_prep) as cmd,\
             patch.object(forward,"build_bundle",return_value={"coverage":{"kyi_missing_count":0}}),\
             patch.object(forward,"init_session",return_value=session) as init,\
             patch.object(forward,"build_authoring_bundle",return_value=author) as bundle:
            self.assertEqual(self.run_args(),0)
            handoff=json.loads((self.root/"operation_handoff.json").read_text())
            self.assertEqual(handoff["status"],"READY_FOR_V056_AUTHORING")
            self.assertEqual(handoff["execution_mode"],"FORWARD")
            self.assertEqual(handoff["paci_source"]["source"],"GOOGLE_DRIVE_CANONICAL_PACI")
            self.assertEqual(handoff["session_id"],"V056-test")
            self.assertEqual(handoff["reader_count"],1)
            self.assertEqual(handoff["authoring_bundle"]["path"],"v056/authoring_bundle")
            self.assertFalse(handoff["automated_marks"] if "automated_marks" in handoff else handoff["authoring_bundle"]["automated_marks"])
            cmd.assert_called_once()
            self.assertEqual(init.call_args.args[1],self.root/"v056")
            self.assertEqual(bundle.call_args.args[0],self.root/"v056")
    def test_reject_missing_drive_receipt(self):
        self.receipt.unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_args()

    def test_reject_modified_drive_paci(self):
        with zipfile.ZipFile(self.paci, "a") as archive:
            archive.writestr("CHANGED.TXT", b"modified")
        with self.assertRaisesRegex(ValueError, "changed after receipt"):
            self.run_args()

    def test_reject_jrdb_source_claim(self):
        receipt = json.loads(self.receipt.read_text(encoding="utf-8"))
        receipt["source"] = "JRDB_DIRECT"
        self.receipt.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not a verified canonical Drive"):
            self.run_args()

    def test_reject_mismatched_racelap_sha(self):
        def fake_prep(_cmd,check):
            self.root.mkdir(parents=True,exist_ok=True)
            (self.root/"day_prep"/"RaceNote_20261031").mkdir(parents=True)
            (self.root/"operation_handoff.json").write_text(json.dumps({
                "selection_id":"DAILY-20261031","target_date":self.day,
                "race_lap_resolution":{"status":"CURRENT_READY",
                    "updated":False,"parquet_sha256":"0"*64}
            }),encoding="utf-8")
        with patch.object(forward.subprocess,"run",side_effect=fake_prep),\
             patch.object(forward,"build_bundle",return_value={"coverage":{"kyi_missing_count":0}}),\
             self.assertRaisesRegex(ValueError,"RaceLap SHA differs"):
            self.run_args()

if __name__=="__main__":unittest.main()
