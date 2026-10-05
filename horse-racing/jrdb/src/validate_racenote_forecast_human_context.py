#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-Freeze guard for RaceNote Human-Context Reader v0.3-v0.4.6."""

from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any

VERSION = "racenote-human-context-validator-0.4.6"

V043_LOGIC = "RaceNote-Human-Context-Reader-0.4.3-candidate"
V043_SCHEMA = "RaceNote-Forecast-Research-Record-0.4.3"
V044_LOGIC = "RaceNote-Human-Context-Reader-0.4.4-candidate"
V044_SCHEMA = "RaceNote-Forecast-Research-Record-0.4.4"
V045_LOGIC = "RaceNote-Human-Context-Reader-0.4.5-candidate"
V045_SCHEMA = "RaceNote-Forecast-Research-Record-0.4.5"
V046_LOGIC = "RaceNote-Human-Context-Reader-0.4.6-candidate"
V046_SCHEMA = "RaceNote-Forecast-Research-Record-0.4.6"
PASS_FIELDS = (
    ("hierarchy_reviewed", "hierarchy_changed", "hierarchy_reason", "HIERARCHY_CONSISTENCY"),
    ("single_shot_promotion_reviewed", "single_shot_promoted", "single_shot_promotion_reason", "SINGLE_SHOT_PROMOTION"),
    ("coverage_challenger_reviewed", "coverage_changed", "coverage_reason", "COVERAGE_CHALLENGER"),
)

def _horse_no_ref(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    try:
        return int(value.get("horse_no"))
    except (TypeError, ValueError):
        return None


def validate_consistency_pass(r: dict[str,Any]) -> list[str]:
    trace=r.get("decision_trace") or {}
    cp=trace.get("consistency_pass")
    if not isinstance(cp,dict):
        return ["consistency_pass required"]

    research=r.get("research") or {}
    logic_version=research.get("logic_version")
    errors=[]
    changed=[]

    # Hierarchy / independent-single-shot semantics are inherited by v0.4.3+.
    for reviewed,flag,reason,label in PASS_FIELDS[:2]:
        if cp.get(reviewed) is not True:
            errors.append(f"{reviewed} must be true")
        if not isinstance(cp.get(flag),bool):
            errors.append(f"{flag} must be boolean")
        if cp.get(flag) is True:
            changed.append(label)
            if not str(cp.get(reason) or "").strip():
                errors.append(f"{reason} required for change")

    if logic_version == V044_LOGIC:
        if cp.get("coverage_scan_reviewed") is not True:
            errors.append("coverage_scan_reviewed must be true")

        scan=cp.get("coverage_scan")
        if not isinstance(scan,dict):
            errors.append("coverage_scan required")
            scan={}
        unmarked=scan.get("unmarked_count")
        direct=scan.get("direct_condition_candidate_count")
        shortlist=scan.get("shortlisted_horse_nos")
        if not isinstance(unmarked,int) or isinstance(unmarked,bool) or unmarked < 0:
            errors.append("coverage_scan.unmarked_count must be non-negative integer")
        if not isinstance(direct,int) or isinstance(direct,bool) or direct < 0:
            errors.append("coverage_scan.direct_condition_candidate_count must be non-negative integer")
        if not isinstance(shortlist,list) or any(not isinstance(x,int) or isinstance(x,bool) or x < 1 for x in (shortlist or [])):
            errors.append("coverage_scan.shortlisted_horse_nos must be positive-integer array")
            shortlist=[]
        elif len(shortlist) != len(set(shortlist)):
            errors.append("coverage_scan.shortlisted_horse_nos must be unique")
        if isinstance(unmarked,int) and isinstance(shortlist,list) and len(shortlist) > unmarked:
            errors.append("coverage shortlist cannot exceed unmarked_count")
        if isinstance(direct,int) and isinstance(shortlist,list) and len(shortlist) > direct:
            errors.append("coverage shortlist cannot exceed direct_condition_candidate_count")

        boundary=cp.get("coverage_boundary")
        if not isinstance(boundary,dict):
            errors.append("coverage_boundary required")
            boundary={}
        delta2=(boundary or {}).get("current_delta2")
        delta2_no=_horse_no_ref(delta2)
        if delta2_no is None or not str((delta2 or {}).get("horse_name") or "").strip():
            errors.append("coverage_boundary.current_delta2 horse required")

        verdict=cp.get("coverage_verdict")
        allowed_verdicts={"KEEP","SWAP","NO_ELIGIBLE_CHALLENGER"}
        if verdict not in allowed_verdicts:
            errors.append("coverage_verdict must be KEEP, SWAP or NO_ELIGIBLE_CHALLENGER")

        coverage_changed=cp.get("coverage_changed")
        if not isinstance(coverage_changed,bool):
            errors.append("coverage_changed must be boolean")
        elif verdict == "SWAP" and coverage_changed is not True:
            errors.append("SWAP requires coverage_changed=true")
        elif verdict in {"KEEP","NO_ELIGIBLE_CHALLENGER"} and coverage_changed is not False:
            errors.append(f"{verdict} requires coverage_changed=false")

        reason=str(cp.get("coverage_reason") or "").strip()
        if len(reason) < 8:
            errors.append("coverage_reason must explain the boundary decision")

        challenger=cp.get("coverage_best_challenger")
        challenger_no=_horse_no_ref(challenger)
        challenger_case=cp.get("coverage_challenger_case")
        labels={"CHALLENGER_STRONGER","DELTA2_STRONGER","ROUGHLY_EQUAL","UNCLEAR"}
        comparison_keys=("direct_condition_comparison","ability_comparison","race_model_comparison")

        if verdict == "NO_ELIGIBLE_CHALLENGER":
            if challenger is not None:
                errors.append("NO_ELIGIBLE_CHALLENGER requires coverage_best_challenger=null")
            if challenger_case is not None:
                errors.append("NO_ELIGIBLE_CHALLENGER requires coverage_challenger_case=null")
            for key in comparison_keys:
                if boundary.get(key) is not None:
                    errors.append(f"NO_ELIGIBLE_CHALLENGER requires coverage_boundary.{key}=null")
        elif verdict in {"KEEP","SWAP"}:
            if challenger_no is None or not str((challenger or {}).get("horse_name") or "").strip():
                errors.append(f"{verdict} requires coverage_best_challenger horse")
            if challenger_no is not None and challenger_no not in shortlist:
                errors.append("coverage_best_challenger must appear in shortlisted_horse_nos")
            if not isinstance(challenger_case,dict):
                errors.append(f"{verdict} requires coverage_challenger_case")
            else:
                for key in ("direct_condition","ability_proximity","race_model_fit","supporting_evidence"):
                    if not str(challenger_case.get(key) or "").strip():
                        errors.append(f"coverage_challenger_case.{key} required")
            for key in comparison_keys:
                if boundary.get(key) not in labels:
                    errors.append(f"coverage_boundary.{key} has invalid comparison label")
            if challenger_no is not None and delta2_no == challenger_no:
                errors.append("coverage challenger must differ from provisional delta2")

        marks=((r.get("prediction") or {}).get("marks") or {})
        others=marks.get("others") if isinstance(marks.get("others"),list) else []
        final_delta2_no=_horse_no_ref(others[1]) if len(others) >= 2 else None
        final_mark_nos=[
            _horse_no_ref(marks.get("main")),
            _horse_no_ref(marks.get("second")),
            _horse_no_ref(marks.get("third")),
            *[_horse_no_ref(x) for x in others[:2]],
        ]

        if verdict == "SWAP":
            changed.append("COVERAGE_CHALLENGER")
            if boundary.get("direct_condition_comparison") != "CHALLENGER_STRONGER":
                errors.append("SWAP requires challenger stronger on direct condition")
            if boundary.get("ability_comparison") not in {"CHALLENGER_STRONGER","ROUGHLY_EQUAL"}:
                errors.append("SWAP requires no material ability gap versus delta2")
            if boundary.get("race_model_comparison") not in {"CHALLENGER_STRONGER","ROUGHLY_EQUAL"}:
                errors.append("SWAP requires challenger to fit race model at least as well as delta2")
            if final_delta2_no != challenger_no:
                errors.append("SWAP final delta2 must equal coverage_best_challenger")
            if delta2_no is not None and delta2_no in final_mark_nos:
                errors.append("SWAP provisional delta2 must leave final five")
        elif verdict in {"KEEP","NO_ELIGIBLE_CHALLENGER"}:
            if final_delta2_no != delta2_no:
                errors.append(f"{verdict} final delta2 must equal provisional delta2")
            if verdict == "KEEP" and challenger_no is not None and challenger_no in final_mark_nos:
                errors.append("KEEP challenger must remain outside final five")
    elif logic_version == V045_LOGIC:
        if cp.get("coverage_scan_reviewed") is not True:
            errors.append("coverage_scan_reviewed must be true")

        scan=cp.get("coverage_scan")
        if not isinstance(scan,dict):
            errors.append("coverage_scan required")
            scan={}
        unmarked=scan.get("unmarked_count")
        shortlist=scan.get("shortlisted_horse_nos")
        if not isinstance(unmarked,int) or isinstance(unmarked,bool) or unmarked < 0:
            errors.append("coverage_scan.unmarked_count must be non-negative integer")
        if not isinstance(shortlist,list) or any(not isinstance(x,int) or isinstance(x,bool) or x < 1 for x in (shortlist or [])):
            errors.append("coverage_scan.shortlisted_horse_nos must be positive-integer array")
            shortlist=[]
        elif len(shortlist) != len(set(shortlist)):
            errors.append("coverage_scan.shortlisted_horse_nos must be unique")
        if isinstance(unmarked,int) and isinstance(shortlist,list) and len(shortlist) > unmarked:
            errors.append("coverage shortlist cannot exceed unmarked_count")

        boundary=cp.get("coverage_boundary")
        if not isinstance(boundary,dict):
            errors.append("coverage_boundary required")
            boundary={}
        delta2=(boundary or {}).get("current_delta2")
        delta2_no=_horse_no_ref(delta2)
        if delta2_no is None or not str((delta2 or {}).get("horse_name") or "").strip():
            errors.append("coverage_boundary.current_delta2 horse required")

        verdict=cp.get("coverage_verdict")
        if verdict not in {"KEEP","SWAP","NO_ELIGIBLE_CHALLENGER"}:
            errors.append("coverage_verdict must be KEEP, SWAP or NO_ELIGIBLE_CHALLENGER")

        coverage_changed=cp.get("coverage_changed")
        if not isinstance(coverage_changed,bool):
            errors.append("coverage_changed must be boolean")
        elif verdict == "SWAP" and coverage_changed is not True:
            errors.append("SWAP requires coverage_changed=true")
        elif verdict in {"KEEP","NO_ELIGIBLE_CHALLENGER"} and coverage_changed is not False:
            errors.append(f"{verdict} requires coverage_changed=false")

        if len(str(cp.get("coverage_reason") or "").strip()) < 8:
            errors.append("coverage_reason must explain the boundary decision")

        challenger=cp.get("coverage_best_challenger")
        challenger_no=_horse_no_ref(challenger)
        labels={"CHALLENGER_STRONGER","DELTA2_STRONGER","ROUGHLY_EQUAL","UNCLEAR"}
        comparison_keys=("direct_condition_comparison","ability_comparison","race_model_comparison")
        if verdict == "NO_ELIGIBLE_CHALLENGER":
            if challenger is not None:
                errors.append("NO_ELIGIBLE_CHALLENGER requires coverage_best_challenger=null")
            if shortlist:
                errors.append("NO_ELIGIBLE_CHALLENGER requires empty shortlist")
            for key in comparison_keys:
                if boundary.get(key) is not None:
                    errors.append(f"NO_ELIGIBLE_CHALLENGER requires coverage_boundary.{key}=null")
        elif verdict in {"KEEP","SWAP"}:
            if challenger_no is None or not str((challenger or {}).get("horse_name") or "").strip():
                errors.append(f"{verdict} requires coverage_best_challenger horse")
            if challenger_no is not None and challenger_no not in shortlist:
                errors.append("coverage_best_challenger must appear in shortlisted_horse_nos")
            for key in comparison_keys:
                if boundary.get(key) not in labels:
                    errors.append(f"coverage_boundary.{key} has invalid comparison label")
            if challenger_no is not None and delta2_no == challenger_no:
                errors.append("coverage challenger must differ from provisional delta2")

        marks=((r.get("prediction") or {}).get("marks") or {})
        others=marks.get("others") if isinstance(marks.get("others"),list) else []
        final_delta2_no=_horse_no_ref(others[1]) if len(others) >= 2 else None
        final_mark_nos=[
            _horse_no_ref(marks.get("main")),
            _horse_no_ref(marks.get("second")),
            _horse_no_ref(marks.get("third")),
            *[_horse_no_ref(x) for x in others[:2]],
        ]
        if verdict == "SWAP":
            changed.append("COVERAGE_CHALLENGER")
            if boundary.get("direct_condition_comparison") != "CHALLENGER_STRONGER":
                errors.append("SWAP requires challenger stronger on direct condition")
            if boundary.get("ability_comparison") not in {"CHALLENGER_STRONGER","ROUGHLY_EQUAL"}:
                errors.append("SWAP requires no material ability gap versus delta2")
            if boundary.get("race_model_comparison") not in {"CHALLENGER_STRONGER","ROUGHLY_EQUAL"}:
                errors.append("SWAP requires challenger to fit race model at least as well as delta2")
            if final_delta2_no != challenger_no:
                errors.append("SWAP final delta2 must equal coverage_best_challenger")
            if delta2_no is not None and delta2_no in final_mark_nos:
                errors.append("SWAP provisional delta2 must leave final five")
        elif verdict in {"KEEP","NO_ELIGIBLE_CHALLENGER"}:
            if final_delta2_no != delta2_no:
                errors.append(f"{verdict} final delta2 must equal provisional delta2")
            if verdict == "KEEP" and challenger_no is not None and challenger_no in final_mark_nos:
                errors.append("KEEP challenger must remain outside final five")

    else:
        reviewed,flag,reason,label=PASS_FIELDS[2]
        if cp.get(reviewed) is not True:
            errors.append(f"{reviewed} must be true")
        if not isinstance(cp.get(flag),bool):
            errors.append(f"{flag} must be boolean")
        if cp.get(flag) is True:
            changed.append(label)
            if not str(cp.get(reason) or "").strip():
                errors.append(f"{reason} required for change")

    attribution=cp.get("change_attribution")
    expected="+".join(changed) if changed else "UNCHANGED_AFTER_INDEPENDENT_REVIEW"
    if attribution != expected:
        errors.append(f"change_attribution must equal {expected}")
    return errors

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
        "RaceNote-Forecast-Research-Record-0.4.2",
        V043_SCHEMA,
        V044_SCHEMA,
        V045_SCHEMA,
        V046_SCHEMA,
    }:
        e.append(f"{pre}: unsupported schema version")
    logic_version=research.get("logic_version")
    if logic_version not in {
        "RaceNote-Human-Context-Reader-0.3",
        "RaceNote-Human-Context-Reader-0.3.1",
        "RaceNote-Human-Context-Reader-0.3.2",
        "RaceNote-Human-Context-Reader-0.4.0-candidate",
        "RaceNote-Human-Context-Reader-0.4.1-candidate",
        "RaceNote-Human-Context-Reader-0.4.2-candidate",
        V043_LOGIC,
        V044_LOGIC,
        V045_LOGIC,
        V046_LOGIC,
    }:
        e.append(f"{pre}: wrong logic_version")
    if research.get("evaluation_mode")=="CALIBRATION_REPLAY" and research.get("turn_id","").startswith("BTDAY-"):
        e.append(f"{pre}: calibration replay must use CAL-* turn id")

    is_v04=str(logic_version or "").startswith("RaceNote-Human-Context-Reader-0.4")
    if schema_version in {V043_SCHEMA,V044_SCHEMA,V045_SCHEMA} or logic_version in {V043_LOGIC,V044_LOGIC,V045_LOGIC}:
        expected_pair={
            V043_LOGIC: V043_SCHEMA,
            V044_LOGIC: V044_SCHEMA,
            V045_LOGIC: V045_SCHEMA,
        }.get(logic_version)
        if expected_pair is None or schema_version != expected_pair:
            e.append(f"{pre}: v0.4.3+ schema/logic mismatch")
        if research.get("independent_forecast") is not True or research.get("baseline_marks_used_as_input") is not False:
            e.append(f"{pre}: v0.4.3+ must declare independent forecast without baseline marks")
        e.extend(f"{pre}: {message}" for message in validate_consistency_pass(r))

    if schema_version == V046_SCHEMA or logic_version == V046_LOGIC:
        if schema_version != V046_SCHEMA or logic_version != V046_LOGIC:
            e.append(f"{pre}: v0.4.6 schema/logic mismatch")
        if research.get("independent_forecast") is not True or research.get("baseline_marks_used_as_input") is not False:
            e.append(f"{pre}: v0.4.6 must declare independent forecast without baseline marks")
        if research.get("execution_contract") != "RACENOTE_EXECUTION_V0.4.6":
            e.append(f"{pre}: wrong v0.4.6 execution contract")

    if is_v04:
        if len(str(t.get("race_model") or "").strip()) < 30:
            e.append(f"{pre}: race_model too short")

        mainline=t.get("mainline_cases")
        if not isinstance(mainline,list) or len(mainline) < 3:
            e.append(f"{pre}: mainline_cases must contain at least 3 horses")
        else:
            seen=set()
            for i,case in enumerate(mainline,1):
                horse=(case or {}).get("horse") if isinstance(case,dict) else None
                name=hname(horse)
                if not name:
                    e.append(f"{pre}: mainline[{i}] horse missing")
                if name in seen:
                    e.append(f"{pre}: duplicate mainline horse {name}")
                seen.add(name)

        single=t.get("single_shot_case")
        if not isinstance(single,dict):
            e.append(f"{pre}: single_shot_case required")
        else:
            horse=single.get("horse")
            if not hname(horse):
                e.append(f"{pre}: single_shot_case horse missing")
            if single.get("selected_independently_from_mainline") is not True:
                e.append(f"{pre}: single_shot_case must be independently selected")

        main=hname(marks.get("main")); second=hname(marks.get("second")); third=hname(marks.get("third"))
        others=marks.get("others") if isinstance(marks.get("others"),list) else []
        mark_names=[main,second,third]+[hname(x) for x in others[:2]]
        if len(mark_names) != 5 or any(not x for x in mark_names) or len(set(mark_names)) != 5:
            e.append(f"{pre}: v0.4 five marks must be five unique horses")
        if isinstance(single,dict) and hname(single.get("horse")) and third != hname(single.get("horse")):
            e.append(f"{pre}: final ▲ must equal single_shot_case horse")

        if logic_version == V046_LOGIC:
            if len(mainline) != 4:
                e.append(f"{pre}: v0.4.6 mainline_cases must contain exactly 4 horses")
            else:
                mainline_nos=[]
                for case in mainline:
                    horse=(case or {}).get("horse") if isinstance(case,dict) else None
                    try:
                        mainline_nos.append(int((horse or {}).get("horse_no")))
                    except (TypeError,ValueError):
                        pass
                    if len(str((case or {}).get("case") or "").strip()) < 8:
                        e.append(f"{pre}: v0.4.6 mainline case too short")
                mark_nos=[]
                for item in [marks.get("main"),marks.get("second"),*(others[:2] if isinstance(others,list) else [])]:
                    try:
                        mark_nos.append(int((item or {}).get("horse_no")))
                    except (TypeError,ValueError):
                        pass
                if len(mark_nos)==4 and set(mainline_nos) != set(mark_nos):
                    e.append(f"{pre}: v0.4.6 mainline must match ◎ ○ △1 △2")

            if len(str((single or {}).get("case") or "").strip()) < 8:
                e.append(f"{pre}: v0.4.6 single_shot_case case too short")

            boundary=t.get("support_boundary")
            if not isinstance(boundary,dict):
                e.append(f"{pre}: v0.4.6 support_boundary required")
            else:
                final_delta2=boundary.get("final_delta2")
                if hname(final_delta2) != (hname(others[1]) if len(others)>=2 else ""):
                    e.append(f"{pre}: v0.4.6 support_boundary final_delta2 must equal final △2")
                alt=boundary.get("alternative")
                if alt is not None:
                    alt_name=hname(alt)
                    if not alt_name:
                        e.append(f"{pre}: v0.4.6 boundary alternative horse missing")
                    if alt_name in mark_names:
                        e.append(f"{pre}: v0.4.6 boundary alternative must remain outside final five")
                if len(str(boundary.get("reason") or "").strip()) < 8:
                    e.append(f"{pre}: v0.4.6 support_boundary reason too short")

    else:
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
            for i,case in enumerate(cases,1):
                name=hname((case or {}).get("horse"))
                if not name: e.append(f"{pre}: candidate[{i}] horse missing")
                if name in seen: e.append(f"{pre}: duplicate candidate {name}")
                seen.add(name)
                if len(str((case or {}).get("case_for") or "").strip())<15:
                    e.append(f"{pre}: candidate[{i}] case_for too short")
                if len(str((case or {}).get("case_against") or "").strip())<10:
                    e.append(f"{pre}: candidate[{i}] case_against too short")
                if len(str((case or {}).get("context_hook") or "").strip())<10:
                    e.append(f"{pre}: candidate[{i}] context_hook too short")

        main=hname(marks.get("main")); second=hname(marks.get("second")); third=hname(marks.get("third"))
        for key,preferred,other in [("main_vs_second",main,second),("main_vs_third",main,third)]:
            comp=t.get(key) or {}
            reason=str(comp.get("reason") or "")
            if hname(comp.get("preferred")) != preferred or hname(comp.get("other")) != other:
                e.append(f"{pre}: {key} horse identity mismatch")
            if preferred and preferred not in reason: e.append(f"{pre}: {key} must name {preferred}")
            if other and other not in reason: e.append(f"{pre}: {key} must name {other}")
            if len(reason.strip())<20: e.append(f"{pre}: {key} reason too short")

    if schema_version in {"RaceNote-Forecast-Research-Record-0.3.1","RaceNote-Forecast-Research-Record-0.4.2",V043_SCHEMA,V044_SCHEMA,V045_SCHEMA,V046_SCHEMA}:
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
            if not isinstance(used,bool) and not is_v04:
                e.append(f"{pre}: rrdb_evidence.used_in_decision must be boolean")
            if not isinstance(refs,list):
                e.append(f"{pre}: rrdb_evidence.horse_refs must be array")
            if used is False and (not isinstance(reason,str) or len(reason.strip())<8):
                e.append(f"{pre}: unused RRDB requires reason_not_used")
            if used is True and (not isinstance(refs,list) or len(refs)<1):
                e.append(f"{pre}: used RRDB requires at least one horse_ref")
            if is_v04 and isinstance(refs,list):
                for idx,ref in enumerate(refs,1):
                    if not isinstance(ref,dict):
                        continue
                    if ref.get("next_watch_grade") not in {None, ""}:
                        e.append(f"{pre}: current RRDB must not use legacy next_watch_grade in horse_ref[{idx}]")
                    if "matched_rule_ids" in ref and ref.get("matched_rule_ids"):
                        e.append(f"{pre}: current RRDB must use matched_signal_ids, not matched_rule_ids")
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
    combined=" ".join(str(t.get(k) or "") for k in (
        ["race_model","mark_reason"] if is_v04 else
        ["race_model","primary_question","why_not_numeric_leader","strongest_counter","reversal_condition"]
    ))
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

    if is_v04:
        prose=str(p.get("reader_facing_reason") or "").strip()
        if len(prose) < 45:
            e.append(f"{pre}: reader_facing_reason too short for race-specific prose")
        if "\n" in prose:
            e.append(f"{pre}: reader_facing_reason must be one paragraph")
        internal_terms=("UPGRADE","DOWNGRADE","CONFIRM","hidden_strength","Next-Watch","DAY PREP","mainline_cases","single_shot_case")
        if any(x in prose for x in internal_terms):
            e.append(f"{pre}: reader_facing_reason exposes internal research terminology")

    if logic_version == V045_LOGIC:
        if research.get("prediction_semantics") != "INHERIT_V0.4.4":
            e.append(f"{pre}: v0.4.5 must declare inherited v0.4.4 prediction semantics")
        if research.get("execution_contract") != "RACENOTE_EXECUTION_V0.4.5":
            e.append(f"{pre}: wrong v0.4.5 execution contract")
        core_hash=str(audit.get("decision_core_sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", core_hash):
            e.append(f"{pre}: v0.4.5 decision_core_sha256 required")

    if logic_version == V046_LOGIC:
        core_hash=str(audit.get("decision_core_sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", core_hash):
            e.append(f"{pre}: v0.4.6 decision_core_sha256 required")

    if audit.get("pre_result_guard")!="PASS": e.append(f"{pre}: pre_result_guard must PASS")
    if audit.get("result_visible_at_freeze") is not False: e.append(f"{pre}: result must be hidden")
    return e

def audit_reader_prose(rows:list[dict[str,Any]]) -> tuple[list[str],dict[str,Any]]:
    errors=[]
    advisories=[]
    comments=[str(((r.get("prediction") or {}).get("reader_facing_reason") or "")).strip() for r in rows]
    comments=[x for x in comments if x]
    n=len(comments)
    canned=(
        "ここでは軸に取る",
        "相手の中心",
        "展開が噛み合えば上位へ割り込める",
        "本線とは違う形で上位へ割り込む余地を取った",
        "今回条件でも見直せる",
    )
    threshold=max(3, (n+3)//4) if n else 3
    repeated={}
    for phrase in canned:
        count=sum(phrase in c for c in comments)
        if count:
            repeated[phrase]=count
        if count >= threshold:
            errors.append(f"TURN: canned reader-facing phrase repeated too often: {phrase} ({count}/{n})")
    exact_unique=len(set(comments))
    if n >= 6 and exact_unique / n < .90:
        errors.append(f"TURN: reader_facing_reason unique ratio too low ({exact_unique}/{n})")

    direct_internal={
        "RRDB": sum("RRDB" in c for c in comments),
        "IDM": sum("IDM" in c for c in comments),
        "指数": sum("指数" in c for c in comments),
    }
    for term,count in direct_internal.items():
        if count:
            advisories.append(f"reader-facing prose directly exposes {term} in {count}/{n} races; prefer ordinary racing language unless the term itself is informative")

    mark_order_count=sum(
        ("◎" in c and "○" in c and "▲" in c and c.index("◎") < c.index("○") < c.index("▲"))
        for c in comments
    )
    made_ending_count=sum(bool(re.search(r"(?:まで|までを相手(?:に)?|までを押さえる?)。?$", c)) for c in comments)
    if n >= 8 and mark_order_count / n >= .80:
        advisories.append(f"reader-facing prose follows ◎→○→▲ order in {mark_order_count}/{n} races; vary structure from race evidence")
    if n >= 8 and made_ending_count / n >= .50:
        advisories.append(f"reader-facing prose uses a generic '...まで' ending in {made_ending_count}/{n} races; omit unsupported mark enumeration")

    return errors,{
        "status":"PASS" if not errors else "FAIL",
        "comment_count":n,
        "unique_comment_count":exact_unique,
        "one_paragraph_count":sum("\n" not in c for c in comments),
        "repeat_threshold":threshold,
        "repeated_canned_phrases":repeated,
        "direct_internal_term_counts":direct_internal,
        "ordered_mark_comment_count":mark_order_count,
        "generic_made_ending_count":made_ending_count,
        "advisories":advisories,
    }

def audit_turn(rows:list[dict[str,Any]]) -> dict[str,Any]:
    errors=[]
    for r in rows: errors.extend(validate_record(r))
    models=[str((r.get("decision_trace") or {}).get("race_model") or "").strip() for r in rows]
    if len(models)>=6:
        ratio=len(set(models))/len(models)
        if ratio < .85: errors.append(f"TURN: race_model unique ratio too low ({len(set(models))}/{len(models)})")
    prose_errors,anti_template=audit_reader_prose(rows)
    errors.extend(prose_errors)
    return {"validator_version":VERSION,"status":"PASS" if not errors else "FAIL","record_count":len(rows),"error_count":len(errors),"errors":errors,"anti_template":anti_template}

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
