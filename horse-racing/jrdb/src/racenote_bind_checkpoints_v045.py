#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Materialize complete RaceNote v0.4.5 records from immutable race checkpoints.

All predictive choices and prose must already exist in checkpoints. This binder
only binds horse identities/source metadata and derives deterministic audit
fields.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from racenote_freeze_prepared_forecast import contains_key, validate_prepared_record
from validate_racenote_forecast_human_context import audit_turn

LOGIC = "RaceNote-Human-Context-Reader-0.4.5-candidate"
SCHEMA = "RaceNote-Forecast-Research-Record-0.4.5"
RRDB = "rrdb-recommendation-signals-v0.3"
VERSION = "racenote-bind-checkpoints-0.4.5"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def required(obj: dict, key: str):
    if key not in obj or obj[key] is None:
        raise ValueError(f"checkpoint field missing: {key}")
    return obj[key]


def load_clean_readers(root: Path, selection_id: str, date: str, main_sha: str):
    handoff = json.loads((root / "day_prep_handoff.json").read_text(encoding="utf-8"))
    manifest_path = root / "reader_stripped_manifest.json"
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if handoff["selection_id"] != selection_id or manifest["selection_id"] != selection_id:
        raise ValueError("selection mismatch")
    if handoff["target_date"] != date or manifest["target_date"] != date:
        raise ValueError("date mismatch")
    if handoff["main_sha"] != main_sha:
        raise ValueError("main SHA mismatch")
    if handoff["rrdb_contract"] != RRDB:
        raise ValueError("RRDB contract mismatch")
    if handoff["result_opened"] is not False or handoff["target_market_opened"] is not False:
        raise ValueError("result/market firewall failed")
    if handoff["market_blind"] is not True or handoff["stripped_at_input_bind"] is not True:
        raise ValueError("market-blind binding required")
    if digest(raw) != handoff["reader_stripped_manifest_sha256"]:
        raise ValueError("clean Reader manifest digest mismatch")

    readers = {}
    paths = sorted((root / "reader").glob("*.json"))
    if {p.name for p in paths} != set(manifest["reader_sha256"]):
        raise ValueError("clean Reader file set mismatch")
    for path in paths:
        data = path.read_bytes()
        if digest(data) != manifest["reader_sha256"][path.name]:
            raise ValueError(f"Reader digest mismatch: {path.name}")
        reader = json.loads(data)
        if contains_key(reader, "market"):
            raise ValueError(f"market field in clean Reader: {path.name}")
        race = reader["race"]
        key = (str(race["venue"]), int(race["race_no"]))
        readers[key] = (reader, path.name, manifest["reader_sha256"][path.name])
    if len(readers) != handoff["race_count"]:
        raise ValueError("clean Reader race count mismatch")
    return readers, handoff


def load_checkpoints(root: Path, handoff: dict, readers: dict) -> dict:
    mpath = root / "checkpoint_manifest.json"
    mraw = mpath.read_bytes()
    manifest = json.loads(mraw)
    if manifest.get("status") != "COMPLETE_READY_TO_FREEZE":
        raise ValueError("checkpoint card is not COMPLETE_READY_TO_FREEZE")
    if manifest.get("selection_id") != handoff["selection_id"] or manifest.get("target_date") != handoff["target_date"]:
        raise ValueError("checkpoint manifest identity mismatch")
    if int(manifest.get("completed_race_count", -1)) != int(handoff["race_count"]):
        raise ValueError("checkpoint count incomplete")

    keyed = {}
    for entry in manifest.get("entries", []):
        path = root / entry["file"]
        raw = path.read_bytes()
        if digest(raw) != entry.get("sha256"):
            raise ValueError(f"checkpoint digest mismatch: {path.name}")
        d = json.loads(raw)
        if digest(canonical({k:v for k,v in d.items() if k != "checkpoint"})) != entry.get("decision_core_sha256"):
            # Older checkpoint writer hashes the full pre-checkpoint decision.
            core = {k:v for k,v in d.items() if k != "checkpoint"}
            if digest(canonical(core)) != entry.get("decision_core_sha256"):
                raise ValueError(f"decision core digest mismatch: {path.name}")
        key = (str(d["venue"]), int(d["race_no"]))
        if key in keyed:
            raise ValueError(f"duplicate checkpoint: {key}")
        if key not in readers:
            raise ValueError(f"checkpoint race absent from clean Readers: {key}")
        cp = d.get("checkpoint") or {}
        reader, reader_file, reader_sha = readers[key]
        if cp.get("logic_version") != LOGIC or cp.get("source_reader_file") != reader_file or cp.get("source_reader_sha256") != reader_sha:
            raise ValueError(f"checkpoint source identity mismatch: {key}")
        if cp.get("source_reader_semantic_sha256") != digest(canonical(reader)):
            raise ValueError(f"checkpoint semantic Reader mismatch: {key}")
        keyed[key] = d
    if set(keyed) != set(readers):
        raise ValueError(f"incomplete checkpoint card: missing={sorted(set(readers)-set(keyed))}")
    return keyed


def materialize(d: dict, reader: dict, selection_id: str, date: str) -> dict:
    race = reader["race"]
    venue, race_no = str(race["venue"]), int(race["race_no"])
    horses = {int(h["basic"]["horse_no"]): h for h in reader["horses"]}

    def ref(n: int) -> dict:
        n = int(n)
        if n not in horses:
            raise ValueError(f"{venue}{race_no}R: horse {n} absent from clean Reader")
        return {"horse_no": n, "horse_name": str(horses[n]["basic"]["horse_name"]).strip()}

    boundary = [int(x) for x in required(d, "boundary_marks")]
    final = [int(x) for x in required(d, "final_marks")]
    cov = required(d, "coverage")
    hierarchy = required(d, "hierarchy")
    promotion = required(d, "single_shot_promotion")
    shortlist = [int(x) for x in required(cov, "shortlist")]
    challenger = cov.get("challenger")
    verdict = required(cov, "verdict")

    changed = []
    if hierarchy["changed"]:
        changed.append("HIERARCHY_CONSISTENCY")
    if promotion["promoted"]:
        changed.append("SINGLE_SHOT_PROMOTION")
    coverage_changed = verdict == "SWAP"
    if coverage_changed:
        changed.append("COVERAGE_CHALLENGER")
    attribution = "+".join(changed) if changed else "UNCHANGED_AFTER_INDEPENDENT_REVIEW"

    rr = copy.deepcopy(required(d, "rrdb_evidence"))
    bound_refs = []
    for item in rr["horse_refs"]:
        n = int(required(item, "horse_no"))
        role = required(item, "decision_role")
        recommendation = (horses[n].get("racereview") or {}).get("recommendation") or {}
        if recommendation.get("contract_version") != RRDB:
            raise ValueError(f"{venue}{race_no}R: RRDB reference lacks v0.3 evidence for {n}")
        bound_refs.append({
            **ref(n),
            "recommendation_contract_version": RRDB,
            "source_run_ref": str((recommendation.get("source_run") or {}).get("race_key") or ""),
            "matched_signal_ids": recommendation.get("matched_signal_ids") or [],
            "decision_role": role,
            "next_watch_grade": None,
            "matched_rule_ids": [],
        })
    rr["horse_refs"] = bound_refs
    rr["recommendation_contract_version"] = RRDB

    mainline = required(d, "mainline_cases")
    single = required(d, "single_shot_case")
    compact = date.replace("-", "")
    comparisons = {
        "direct_condition_comparison": cov.get("direct_condition"),
        "ability_comparison": cov.get("ability"),
        "race_model_comparison": cov.get("race_model"),
    }

    record = {
        "schema_version": SCHEMA,
        "identity": {
            "target_date": date,
            "venue": venue,
            "race_no": race_no,
            "race_key": f"{compact}_{venue}{race_no}R",
        },
        "research": {
            "evaluation_mode": "BLINDED_HISTORICAL",
            "turn_id": selection_id,
            "logic_version": LOGIC,
            "prediction_semantics": "INHERIT_V0.4.4",
            "execution_contract": "RACENOTE_EXECUTION_V0.4.5",
            "reader_facing_prose_contract": "FORECAST_READER_FACING_PROSE_v0_1",
            "authoring_mode": "MODEL_RACE_BY_RACE_DECISION_CORE",
            "prose_origin": "MODEL_AUTHORED_NOT_SCRIPT_GENERATED",
            "independent_forecast": True,
            "baseline_marks_used_as_input": False,
        },
        "source": {
            "racenote_identity": f"{selection_id}/{venue}{race_no}R",
            "racenote_semantic_sha256": reader["source_semantic_sha256"],
            "reader_input_policy": "TARGET_DAY_MARKET_OBJECT_REMOVED_BEFORE_FORECAST",
            "reader_chunking": "LOSSLESS_SEMANTIC_V0.4.5",
        },
        "prediction": {
            "axis": ref(final[0]),
            "marks": {
                "main": ref(final[0]),
                "second": ref(final[1]),
                "third": ref(final[2]),
                "others": [ref(final[3]), ref(final[4])],
            },
            "reader_facing_reason": required(d, "reader_facing_reason"),
        },
        "decision_trace": {
            "race_model": required(d, "race_model"),
            "mainline_cases": [
                {"horse": ref(x["horse_no"]), "case": x["case"]} for x in mainline
            ],
            "single_shot_case": {
                "horse": ref(single["horse_no"]),
                "selected_independently_from_mainline": True,
                "case": single["case"],
            },
            "mark_reason": {"model_authored_reason": required(d, "mark_reason")},
            "rrdb_evidence": rr,
            "consistency_pass": {
                "hierarchy_reviewed": True,
                "hierarchy_changed": bool(hierarchy["changed"]),
                "hierarchy_reason": hierarchy.get("reason") if hierarchy["changed"] else None,
                "single_shot_promotion_reviewed": True,
                "single_shot_promoted": bool(promotion["promoted"]),
                "single_shot_promotion_reason": promotion.get("reason") if promotion["promoted"] else None,
                "coverage_scan_reviewed": True,
                "coverage_scan": {
                    "unmarked_count": len(horses) - 5,
                    "shortlisted_horse_nos": shortlist,
                },
                "coverage_best_challenger": ref(challenger) if challenger is not None else None,
                "coverage_boundary": {
                    "current_delta2": ref(boundary[4]),
                    **comparisons,
                },
                "coverage_verdict": verdict,
                "coverage_changed": coverage_changed,
                "coverage_reason": required(cov, "reason"),
                "change_attribution": attribution,
            },
        },
        "audit": {
            "pre_result_guard": "PASS",
            "result_visible_at_freeze": False,
            "market_blind": True,
            "target_market_opened": False,
            "decision_core_checkpoint_version": (d.get("checkpoint") or {}).get("version"),
            "decision_core_sha256": digest(canonical({k:v for k,v in d.items() if k != "checkpoint"})),
        },
    }
    validate_prepared_record(record, reader, selection_id, date, LOGIC)
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prep-root", type=Path, required=True)
    ap.add_argument("--checkpoints-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--selection-id", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--main-sha", required=True)
    args = ap.parse_args()

    readers, handoff = load_clean_readers(args.prep_root, args.selection_id, args.date, args.main_sha)
    checkpoints = load_checkpoints(args.checkpoints_root, handoff, readers)
    records = [materialize(checkpoints[key], readers[key][0], args.selection_id, args.date) for key in sorted(readers)]
    report = audit_turn(records)
    if report["status"] != "PASS":
        raise ValueError("materialized card validator FAIL: " + "; ".join(report["errors"]))
    if args.output.exists():
        raise FileExistsError(f"prepared records already exist: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "binder_version": VERSION,
        "selection_id": args.selection_id,
        "record_count": len(records),
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
