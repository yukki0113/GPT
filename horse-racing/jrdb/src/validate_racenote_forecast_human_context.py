#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-Freeze guard for RaceNote Human-Context Reader v0.3."""

from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any

VERSION = "racenote-human-context-validator-0.2.2"

def load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    v=json.loads(path.read_text(encoding="utf-8"))
    return v if isinstance(v,list) else [v]

def hname(x: Any) -> str:
    return str((x or {}).get("horse_name") or "").strip() if isinstance(x,dict) else ""

def validate_record(r: dict[str,Any]) -> list[str]:
    e=[]
    ident=r.get("identity") or {}
    p=r.get("prediction") or {}
    marks=p.get("marks") or {}
    t=r.get("decision_trace") or {}
    research=r.get("research") or {}
    audit=r.get("audit") or {}
    pre=f"{ident.get('target_date','?')} {ident.get('venue','?')}{ident.get('race_no','?')}R"

    schema_version=r.get("schema_version")
    if schema_version not in {
        "RaceNote-Forecast-Research-Record-0.3",
        "RaceNote-Forecast-Research-Record-0.3.1",
    }:
        e.append(f"{pre}: unsupported schema version")
    if research.get("logic_version") not in {
        "RaceNote-Human-Context-Reader-0.3",
        "RaceNote-Human-Context-Reader-0.3.1",
        "RaceNote-Human-Context-Reader-0.3.2",
    }:
        e.append(f"{pre}: wrong logic_version")
    if research.get("evaluation_mode")=="CALIBRATION_REPLAY" and research.get("turn_id","").startswith("BTDAY-"):
        e.append(f"{pre}: calibration replay must use CAL-* turn id")

    principles=t.get("human_principles_used")
    if not isinstance(principles,list) or not (1 <= len(principles) <= 3):
        e.append(f"{pre}: human_principles_used must contain 1-3 IDs")

    for key,n in [("race_model",30),("primary_question",15),("why_not_numeric_leader",20),("strongest_counter",15),("reversal_condition",15)]:
        if len(str(t.get(key) or "").strip()) < n:
            e.append(f"{pre}: {key} too short")

    cases=t.get("candidate_cases")
    if not isinstance(cases,list) or not 3 <= len(cases) <= 5:
        e.append(f"{pre}: candidate_cases must contain 3-5 horses")
    else:
        seen=set()
        for i,c in enumerate(cases,1):
            name=hname((c or {}).get("horse"))
            if not name: e.append(f"{pre}: candidate[{i}] horse missing")
            if name in seen: e.append(f"{pre}: duplicate candidate {name}")
            seen.add(name)
            if len(str((c or {}).get("case_for") or "").strip())<15:
                e.append(f"{pre}: candidate[{i}] case_for too short")
            if len(str((c or {}).get("case_against") or "").strip())<10:
                e.append(f"{pre}: candidate[{i}] case_against too short")
            if len(str((c or {}).get("context_hook") or "").strip())<10:
                e.append(f"{pre}: candidate[{i}] context_hook too short")

    main=hname(marks.get("main")); second=hname(marks.get("second")); third=hname(marks.get("third"))
    for key,preferred,other in [("main_vs_second",main,second),("main_vs_third",main,third)]:
        c=t.get(key) or {}
        reason=str(c.get("reason") or "")
        if hname(c.get("preferred")) != preferred or hname(c.get("other")) != other:
            e.append(f"{pre}: {key} horse identity mismatch")
        if preferred and preferred not in reason: e.append(f"{pre}: {key} must name {preferred}")
        if other and other not in reason: e.append(f"{pre}: {key} must name {other}")
        if len(reason.strip())<20: e.append(f"{pre}: {key} reason too short")

    if schema_version=="RaceNote-Forecast-Research-Record-0.3.1":
        rrdb=t.get("rrdb_evidence")
        if not isinstance(rrdb,dict):
            e.append(f"{pre}: rrdb_evidence required for v0.3.1")
        else:
            available=rrdb.get("available")
            reviewed=rrdb.get("reviewed")
            used=rrdb.get("used_in_decision")
            refs=rrdb.get("horse_refs")
            reason=rrdb.get("reason_not_used")
            if not isinstance(available,bool):
                e.append(f"{pre}: rrdb_evidence.available must be boolean")
            if reviewed is not True:
                e.append(f"{pre}: RRDB must be reviewed in v0.3.1")
            if not isinstance(used,bool):
                e.append(f"{pre}: rrdb_evidence.used_in_decision must be boolean")
            if not isinstance(refs,list):
                e.append(f"{pre}: rrdb_evidence.horse_refs must be array")
            if used is False and (not isinstance(reason,str) or len(reason.strip())<8):
                e.append(f"{pre}: unused RRDB requires reason_not_used")
            if used is True and (not isinstance(refs,list) or len(refs)<1):
                e.append(f"{pre}: used RRDB requires at least one horse_ref")
            allowed_roles={
                "UPGRADE_RECENT_FORM",
                "DOWNGRADE_APPARENT_FORM",
                "SUPPORT_REPEATABILITY",
                "SUPPORT_COUNTERARGUMENT",
                "CONTEXT_ONLY",
            }
            if isinstance(refs,list):
                for idx,ref in enumerate(refs,1):
                    if not isinstance(ref,dict):
                        e.append(f"{pre}: rrdb horse_ref[{idx}] must be object")
                        continue
                    if ref.get("decision_role") not in allowed_roles:
                        e.append(f"{pre}: rrdb horse_ref[{idx}] invalid decision_role")

    # Hidden-score warning: reject traces whose race model/decision reason is mostly naked numeric fields.
    combined=" ".join(str(t.get(k) or "") for k in [
        "race_model","primary_question","why_not_numeric_leader","strongest_counter","reversal_condition"
    ])
    numeric_tokens=re.findall(r"\b\d+(?:\.\d+)?\b", combined)
    if len(numeric_tokens) >= 8 and len(combined) < 240:
        e.append(f"{pre}: trace appears numeric-dominated; reconsider hidden-score behavior")

    banned=[
        "総合的に最もまとまり",
        "能力水準、近走内容、今回の仕上がりを横並び",
        "最も数値が高",
        "総合値が最も高",
    ]
    if any(x in combined for x in banned):
        e.append(f"{pre}: generic/numeric selection phrase detected")

    if audit.get("pre_result_guard")!="PASS": e.append(f"{pre}: pre_result_guard must PASS")
    if audit.get("result_visible_at_freeze") is not False: e.append(f"{pre}: result must be hidden")
    return e

def audit_turn(rows:list[dict[str,Any]]) -> dict[str,Any]:
    errors=[]
    for r in rows: errors.extend(validate_record(r))
    models=[str((r.get("decision_trace") or {}).get("race_model") or "").strip() for r in rows]
    if len(models)>=6:
        ratio=len(set(models))/len(models)
        if ratio < .85: errors.append(f"TURN: race_model unique ratio too low ({len(set(models))}/{len(models))})")
    return {"validator_version":VERSION,"status":"PASS" if not errors else "FAIL","record_count":len(rows),"error_count":len(errors),"errors":errors}

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--records",required=True,type=Path)
    ap.add_argument("--output",type=Path)
    a=ap.parse_args()
    out=audit_turn(load_records(a.records))
    s=json.dumps(out,ensure_ascii=False,indent=2)+"\n"
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(s,encoding="utf-8")
    print(s,end="")
    return 0 if out["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
