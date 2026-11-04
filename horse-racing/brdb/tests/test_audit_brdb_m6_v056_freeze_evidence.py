"""Synthetic-only tests for BRDB read-only RaceNote v056 Freeze handoff gate."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from audit_brdb_m6_v056_freeze_evidence import check,PAIR_SCHEMA,FROZEN_SCHEMA

def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    data=(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()

def fixture(root):
    records=[{
      "venue":"京都","race_no":1,"target_date":"2026-11-07",
      "session_id":"test-session","reader_manifest_sha256":"a"*64,
      "horse_nos":[1,2],"decision_core":{"race_no":1}}]
    body=root/"frozen"/"records.json"
    record_sha=write(body,records)
    h={"schema_version":FROZEN_SCHEMA,"status":"PREDICTION_FROZEN_CLEAN_BLIND",
       "validator_status":"PASS","market_blind":True,"result_opened":False,
       "target_market_opened":False,"session_id":"test-session",
       "reader_manifest_sha256":"a"*64,"target_date":"2026-11-07",
       "record_count":1,"race_roster":[{"venue":"京都","race_no":1,"horse_nos":[1,2]}],
       "records_sha256":record_sha}
    write(root/"frozen"/"day_handoff.json",h)
    prob={"schema_version":PAIR_SCHEMA,"target_date":"2026-11-07",
          "prediction_safe":False,"source_freeze_records_sha256":record_sha,
          "entries":[{"venue":"京都","race_no":1,"horse_no":1,
                      "p_baseline":0.6,"p_blood_challenger":0.55},
                     {"venue":"京都","race_no":1,"horse_no":2,
                      "p_baseline":0.4,"p_blood_challenger":0.45}]}
    pp=root/"research_probability_pairs.json";write(pp,prob)
    return pp

class TestV056Evidence(unittest.TestCase):
    def test_valid_freeze_not_promoted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);prob=fixture(root)
            r=check(root)
            self.assertEqual(r["status"],"FREEZE_STRUCTURE_VALID_RELEASE_TIME_NOT_ATTESTED")
            self.assertFalse(r["prediction_safe"])
            self.assertEqual(r["probability_pair_count"],0)
            self.assertEqual(r["roster_entry_count"],2)
            self.assertFalse(r["p1_7_log_loss_evaluable"])
            self.assertEqual(check(root,prob)["probability_pair_count"],2)
            self.assertFalse(check(root,prob)["p1_7_log_loss_evaluable"])

    def test_frozen_record_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);fixture(root)
            p=root/"frozen"/"records.json";p.write_bytes(p.read_bytes()+b"altered")
            with self.assertRaisesRegex(ValueError,"SHA mismatch"):check(root)

    def test_malformed_handoff_and_roster_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);fixture(root)
            p=root/"frozen"/"day_handoff.json";v=json.loads(p.read_text())
            v["result_opened"]=True;write(p,v)
            with self.assertRaisesRegex(ValueError,"unaccepted"):check(root)
            v["result_opened"]=False;v["race_roster"][0]["horse_nos"]=[1,1];write(p,v)
            with self.assertRaisesRegex(ValueError,"invalid horse numbers"):check(root)

    def test_incomplete_or_invalid_probabilities_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pp=fixture(root)
            v=json.loads(pp.read_text());v["entries"][0]["p_baseline"]=0.9;write(pp,v)
            with self.assertRaisesRegex(ValueError,"sum to 1"):check(root,pp)
            v["entries"]=v["entries"][:1];write(pp,v)
            with self.assertRaisesRegex(ValueError,"roster incomplete"):check(root,pp)

    def test_claimed_source_attestation_cannot_promote(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pp=fixture(root)
            v=json.loads(pp.read_text())
            v["signed_source_attestation"]=True
            v["claimed_provider_timestamp"]="2026-11-06T12:00:00Z"
            write(pp,v)
            self.assertFalse(check(root,pp)["prediction_safe"])
            with self.assertRaisesRegex(ValueError,"eligibility HOLD"):
                check(root,pp,require_prediction_safe=True)
            v["prediction_safe"]=True;write(pp,v)
            with self.assertRaisesRegex(ValueError,"untrusted"):check(root,pp)

if __name__=="__main__":
    unittest.main()
