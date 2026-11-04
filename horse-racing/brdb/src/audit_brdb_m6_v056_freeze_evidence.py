#!/usr/bin/env python3
"""Read-only BRDB research adapter for existing RaceNote v0.5.6 Prediction Freeze.

This validator CANNOT independently verify when a GitHub commit or Drive object
became available. It never upgrades source files to as-of-safe by JSON claims.
No prediction results, payouts, or licensed horse data are published.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
from collections import Counter

VERSION="brdb-m6-v056-freeze-evidence-v0.1"
FROZEN_SCHEMA="racenote-v056-single-day-frozen-0.1"
PAIR_SCHEMA="brdb-p1-7-pre-race-pairs-v0.1"

def sha(blob:bytes)->str:
    return hashlib.sha256(blob).hexdigest()

def strict_json(path:Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def check(root:Path, pair_path:Path|None=None, *, require_prediction_safe=False):
    root=Path(root)
    handoff_path=root/"frozen"/"day_handoff.json"
    records_path=root/"frozen"/"records.json"
    handoff=strict_json(handoff_path)
    raw=records_path.read_bytes()
    if (handoff.get("schema_version")!=FROZEN_SCHEMA or
        handoff.get("status")!="PREDICTION_FROZEN_CLEAN_BLIND" or
        handoff.get("validator_status")!="PASS" or
        handoff.get("market_blind") is not True or
        handoff.get("result_opened") is not False or
        handoff.get("target_market_opened") is not False):
        raise ValueError("unaccepted canonical v056 clean-blind Freeze handoff")
    if sha(raw)!=handoff.get("records_sha256"):
        raise ValueError("frozen records content SHA mismatch")
    records=json.loads(raw)
    roster=handoff.get("race_roster")
    if not isinstance(records,list) or not isinstance(roster,list) or len(records)!=handoff.get("record_count") or len(records)!=len(roster) or not records:
        raise ValueError("Freeze race roster/record count mismatch")
    target=handoff.get("target_date")
    if not isinstance(target,str) or len(target)!=10:
        raise ValueError("invalid target date")
    expected={}
    for race in roster:
        if not isinstance(race,dict):
            raise ValueError("invalid roster")
        venue=race.get("venue")
        no=race.get("race_no")
        nos=race.get("horse_nos")
        if not isinstance(venue,str) or not isinstance(no,int) or not isinstance(nos,list) or not nos:
            raise ValueError("invalid race roster")
        if any(type(n) is not int or n<=0 for n in nos) or len(set(nos))!=len(nos):
            raise ValueError("invalid horse numbers")
        key=(venue,no)
        if key in expected:raise ValueError("duplicate race in Freeze")
        expected[key]=set(nos)
    seen=set()
    for record in records:
        key=(record.get("venue"),record.get("race_no"))
        if key not in expected or key in seen:
            raise ValueError("unmatched or duplicate frozen race")
        seen.add(key)
        if (record.get("target_date")!=target or
            record.get("session_id")!=handoff.get("session_id") or
            record.get("reader_manifest_sha256")!=handoff.get("reader_manifest_sha256") or
            set(record.get("horse_nos",[]))!=expected[key] or
            len(record.get("horse_nos",[]))!=len(expected[key]) or
            not isinstance(record.get("decision_core"),dict)):
            raise ValueError("frozen identity/roster mismatch")
    if seen!=set(expected):
        raise ValueError("incomplete Freeze")

    status="FREEZE_STRUCTURE_VALID_RELEASE_TIME_NOT_ATTESTED"
    pairs=0
    if pair_path is not None:
        obj=strict_json(pair_path)
        if (obj.get("schema_version")!=PAIR_SCHEMA or
            obj.get("target_date")!=target or
            obj.get("prediction_safe") is not False or
            obj.get("source_freeze_records_sha256")!=handoff["records_sha256"]):
            raise ValueError("untrusted or wrong-day paired probability record")
        entries=obj.get("entries")
        if not isinstance(entries,list):
            raise ValueError("missing probability entries")
        present=set()
        sums={}
        for r in entries:
            if not isinstance(r,dict):raise ValueError("malformed pair entry")
            v,n,h=r.get("venue"),r.get("race_no"),r.get("horse_no")
            key=(v,n)
            if key not in expected or type(h) is not int or h not in expected[key]:
                raise ValueError("probability key absent from frozen roster")
            identity=(v,n,h)
            if identity in present:raise ValueError("duplicate probability pair")
            present.add(identity)
            for label in ("p_baseline","p_blood_challenger"):
                p=r.get(label)
                if isinstance(p,bool) or not isinstance(p,(int,float)) or not math.isfinite(p) or not 0<p<1:
                    raise ValueError("non-finite/out-of-range probability")
                sums[(key,label)]=sums.get((key,label),0)+p
        necessary={(v,n,h) for (v,n),ids in expected.items() for h in ids}
        if present!=necessary:
            raise ValueError("probability roster incomplete")
        if any(abs(value-1.0)>0.000001 for value in sums.values()):
            raise ValueError("per-race win probabilities must sum to 1")
        pairs=len(entries)
        status="PAIRS_STRUCTURALLY_VALID_PROVIDER_ASOF_NOT_ATTESTED"

    report={"version":VERSION,"status":status,"target_date":target,
      "race_count":len(records),"roster_entry_count":sum(map(len,expected.values())),
      "probability_pair_count":pairs,"freeze_records_sha256":handoff["records_sha256"],
      "freeze_handoff_sha256":sha(handoff_path.read_bytes()),
      "probability_file_sha256":sha(Path(pair_path).read_bytes()) if pair_path else None,
      "prediction_safe":False,"p1_7_log_loss_evaluable":False,
      "require_independent_git_or_drive_provider_timestamp":True,
      "require_independent_pre_race_feature_provenance":True,
      "notes":["This is an internal integrity check, NOT an immutable GitHub/Drive timestamp attestation.",
               "An applicant-supplied timestamp or signed_source_attestation flag is never proof.",
               "RaceNote v056 freezes are authoritative; BRDB never writes/duplicates them.",
               "No P1-7 model skill, predictive uplift or odds ROI is claimed."]}
    if require_prediction_safe:
        raise ValueError("P1-7 predictive eligibility HOLD: external pre-race source attestation and independent blood features missing")
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--v056-root",required=True,type=Path)
    p.add_argument("--pairs",type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--require-prediction-safe",action="store_true")
    a=p.parse_args()
    report=check(a.v056_root,a.pairs,require_prediction_safe=a.require_prediction_safe)
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"v056_freeze_evidence_audit.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"pairs":report["probability_pair_count"],
                      "prediction_safe":False}))

if __name__=="__main__":
    main()
