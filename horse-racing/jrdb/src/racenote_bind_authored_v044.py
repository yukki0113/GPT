#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bind complete model-authored v0.4.4 decisions to clean Reader identities.

Only horse names, source hashes and fixed contract metadata are supplied here.
No mark, reason, challenger, comparison, RRDB role or verdict is inferred.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from racenote_freeze_prepared_forecast import contains_key, validate_prepared_record
from validate_racenote_forecast_human_context import audit_turn

LOGIC = "RaceNote-Human-Context-Reader-0.4.4-candidate"
RRDB = "rrdb-recommendation-signals-v0.3"


def required(obj: dict, key: str):
    if key not in obj or obj[key] is None:
        raise ValueError(f"model-authored field missing: {key}")
    return obj[key]


def load_clean_readers(root: Path, selection_id: str, date: str, main_sha: str):
    handoff = json.loads((root / "day_prep_handoff.json").read_text(encoding="utf-8"))
    manifest_path = root / "reader_stripped_manifest.json"
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    assert handoff["selection_id"] == manifest["selection_id"] == selection_id
    assert handoff["target_date"] == manifest["target_date"] == date
    assert handoff["main_sha"] == main_sha
    assert handoff["rrdb_contract"] == RRDB
    assert handoff["result_opened"] is False and handoff["target_market_opened"] is False
    assert handoff["market_blind"] is True and handoff["stripped_at_input_bind"] is True
    assert hashlib.sha256(raw).hexdigest() == handoff["reader_stripped_manifest_sha256"]
    paths = sorted((root / "reader").glob("*.json"))
    assert {p.name for p in paths} == set(manifest["reader_sha256"])
    readers = {}
    for path in paths:
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == manifest["reader_sha256"][path.name]
        reader = json.loads(raw)
        assert not contains_key(reader, "market")
        race = reader["race"]
        key = (str(race["venue"]), int(race["race_no"]))
        assert key not in readers
        readers[key] = reader
    assert len(readers) == handoff["race_count"] == manifest["race_count"]
    return readers


def bind_decision(d: dict, reader: dict, selection_id: str, date: str) -> dict:
    race = reader["race"]
    venue, race_no = str(race["venue"]), int(race["race_no"])
    horses = {int(h["basic"]["horse_no"]): h for h in reader["horses"]}

    def ref(n):
        n = int(n)
        if n not in horses:
            raise ValueError(f"{venue}{race_no}R: horse {n} absent from clean Reader")
        return {"horse_no": n, "horse_name": str(horses[n]["basic"]["horse_name"]).strip()}

    marks = required(d, "marks")
    if not isinstance(marks, list) or len(marks) != 5:
        raise ValueError(f"{venue}{race_no}R: five authored marks required")
    mainline = required(d, "mainline_cases")
    if not isinstance(mainline, list) or len(mainline) != 4:
        raise ValueError(f"{venue}{race_no}R: four authored mainline cases required")
    single = required(d, "single_shot_case")
    rr = copy.deepcopy(required(d, "rrdb_evidence"))
    cp = copy.deepcopy(required(d, "consistency_pass"))
    for item in mainline:
        required(item, "case")
        required(item, "horse_no")
    required(single, "case")
    required(single, "horse_no")
    if int(single["horse_no"]) != int(marks[2]):
        raise ValueError(f"{venue}{race_no}R: independently authored ▲ identity mismatch")

    scan = required(cp, "coverage_scan")
    for field in ("unmarked_count", "direct_condition_candidate_count", "shortlisted_horse_nos"):
        required(scan, field)
    boundary = required(cp, "coverage_boundary")
    boundary["current_delta2"] = ref(required(boundary, "current_delta2"))
    challenger = cp.get("coverage_best_challenger")
    cp["coverage_best_challenger"] = ref(challenger) if challenger is not None else None
    for field in ("coverage_scan_reviewed", "coverage_verdict", "coverage_changed",
                  "coverage_reason", "change_attribution", "hierarchy_reviewed",
                  "hierarchy_changed", "hierarchy_reason", "single_shot_promotion_reviewed",
                  "single_shot_promoted", "single_shot_promotion_reason"):
        required(cp, field)
    # The author must explicitly supply the case (or null if no challenger).
    if "coverage_challenger_case" not in cp:
        raise ValueError(f"{venue}{race_no}R: Coverage challenger case missing")
    for field in ("direct_condition_comparison", "ability_comparison", "race_model_comparison"):
        if field not in boundary:
            raise ValueError(f"{venue}{race_no}R: Coverage comparison missing: {field}")

    for field in ("available", "reviewed", "used_in_decision", "horse_refs"):
        required(rr, field)
    if "reason_not_used" not in rr:
        raise ValueError(f"{venue}{race_no}R: RRDB reason_not_used field missing")
    bound_refs = []
    for item in rr["horse_refs"]:
        n = int(required(item, "horse_no"))
        role = required(item, "decision_role")
        recommendation = (horses[n].get("racereview") or {}).get("recommendation") or {}
        if recommendation.get("contract_version") != RRDB:
            raise ValueError(f"{venue}{race_no}R: RRDB reference lacks v0.3 evidence for {n}")
        bound_refs.append({**ref(n), "recommendation_contract_version": RRDB,
                           "source_run_ref": str((recommendation.get("source_run") or {}).get("race_key") or ""),
                           "matched_signal_ids": recommendation.get("matched_signal_ids") or [],
                           "decision_role": role, "next_watch_grade": None, "matched_rule_ids": []})
    rr["horse_refs"] = bound_refs
    rr["recommendation_contract_version"] = RRDB

    ordered = [ref(n) for n in marks]
    compact = date.replace("-", "")
    record = {
        "schema_version": "RaceNote-Forecast-Research-Record-0.4.4",
        "identity": {"target_date": date, "venue": venue, "race_no": race_no,
                     "race_key": f"{compact}_{venue}{race_no}R"},
        "research": {"evaluation_mode": "BLINDED_HISTORICAL", "turn_id": selection_id,
                     "logic_version": LOGIC,
                     "reader_facing_prose_contract": "FORECAST_READER_FACING_PROSE_v0_1",
                     "authoring_mode": "MODEL_RACE_BY_RACE_REASONING",
                     "prose_origin": "MODEL_AUTHORED_NOT_SCRIPT_GENERATED",
                     "independent_forecast": True, "baseline_marks_used_as_input": False},
        "source": {"racenote_identity": f"{selection_id}/{venue}{race_no}R",
                   "racenote_semantic_sha256": reader["source_semantic_sha256"],
                   "reader_input_policy": "TARGET_DAY_MARKET_OBJECT_REMOVED_BEFORE_FORECAST"},
        "prediction": {"axis": ordered[0],
                       "marks": {"main": ordered[0], "second": ordered[1],
                                 "third": ordered[2], "others": ordered[3:]},
                       "reader_facing_reason": required(d, "reader_facing_reason")},
        "decision_trace": {"race_model": required(d, "race_model"),
                           "mainline_cases": [{"horse": ref(x["horse_no"]), "case": x["case"]}
                                              for x in mainline],
                           "single_shot_case": {"horse": ref(single["horse_no"]),
                                                "selected_independently_from_mainline": True,
                                                "case": single["case"]},
                           "mark_reason": {"model_authored_reason": required(d, "mark_reason")},
                           "rrdb_evidence": rr, "consistency_pass": cp},
        "audit": {"pre_result_guard": "PASS", "result_visible_at_freeze": False,
                  "market_blind": True, "target_market_opened": False},
    }
    validate_prepared_record(record, reader, selection_id, date, LOGIC)
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prep-root", type=Path, required=True)
    ap.add_argument("--decisions", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--selection-id", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--main-sha", required=True)
    a = ap.parse_args()
    readers = load_clean_readers(a.prep_root, a.selection_id, a.date, a.main_sha)
    decisions = json.loads(a.decisions.read_text(encoding="utf-8"))
    if not isinstance(decisions, list):
        raise ValueError("decisions must be a JSON array")
    keyed = {}
    for d in decisions:
        key = (str(required(d, "venue")), int(required(d, "race_no")))
        if key in keyed:
            raise ValueError(f"duplicate authored race: {key}")
        keyed[key] = d
    if set(keyed) != set(readers):
        raise ValueError(f"incomplete card: missing={sorted(set(readers)-set(keyed))}, "
                         f"unexpected={sorted(set(keyed)-set(readers))}")
    records = [bind_decision(keyed[key], readers[key], a.selection_id, a.date)
               for key in sorted(readers)]
    report = audit_turn(records)
    if report["status"] != "PASS":
        raise ValueError("authored card validator FAIL: " + "; ".join(report["errors"]))
    if a.output.exists():
        raise FileExistsError(f"prepared records already exist: {a.output}")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "selection_id": a.selection_id,
                      "record_count": len(records), "output": str(a.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
