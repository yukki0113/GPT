#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bind complete v0.4.6 venue batches to clean Reader identities.

This binder turns model-authored Decision Cores into final research records.
It derives only deterministic identities and RRDB metadata. It never chooses
horses or writes predictive prose.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from racenote_freeze_prepared_forecast import contains_key, validate_prepared_record
from validate_racenote_forecast_human_context import audit_turn

LOGIC = "RaceNote-Human-Context-Reader-0.4.6-candidate"
SCHEMA = "RaceNote-Forecast-Research-Record-0.4.6"
RRDB = "rrdb-recommendation-signals-v0.3"
VERSION = "racenote-bind-venue-batches-0.4.6"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_clean(prep: Path, selection_id: str, date: str, main_sha: str):
    handoff = json.loads((prep / "day_prep_handoff.json").read_text(encoding="utf-8"))
    raw_manifest = (prep / "reader_stripped_manifest.json").read_bytes()
    manifest = json.loads(raw_manifest)

    if handoff.get("selection_id") != selection_id or manifest.get("selection_id") != selection_id:
        raise ValueError("selection mismatch")
    if handoff.get("target_date") != date or manifest.get("target_date") != date:
        raise ValueError("date mismatch")
    if handoff.get("main_sha") != main_sha:
        raise ValueError("main SHA mismatch")
    if handoff.get("market_blind") is not True or handoff.get("result_opened") is not False:
        raise ValueError("clean-blind handoff required")
    if handoff.get("target_market_opened") is not False:
        raise ValueError("target market was opened")
    if handoff.get("rrdb_contract") != RRDB:
        raise ValueError("RRDB contract mismatch")
    if digest(raw_manifest) != handoff.get("reader_stripped_manifest_sha256"):
        raise ValueError("clean Reader manifest digest mismatch")

    expected = manifest.get("reader_sha256") or {}
    paths = sorted((prep / "reader").glob("*.json"))
    if set(expected) != {p.name for p in paths}:
        raise ValueError("clean Reader file set mismatch")

    readers = {}
    for path in paths:
        raw = path.read_bytes()
        if digest(raw) != expected[path.name]:
            raise ValueError(f"Reader digest mismatch: {path.name}")
        reader = json.loads(raw)
        if contains_key(reader, "market"):
            raise ValueError(f"market field in clean Reader: {path.name}")
        race = reader["race"]
        key = (str(race["venue"]), int(race["race_no"]))
        readers[key] = reader
    if len(readers) != int(handoff["race_count"]):
        raise ValueError("clean Reader race count mismatch")
    return handoff, readers


def load_batches(root: Path, handoff: dict, readers: dict) -> dict:
    manifest = json.loads((root / "batch_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "COMPLETE_READY_TO_BIND":
        raise ValueError("venue batches are incomplete")
    if manifest.get("selection_id") != handoff["selection_id"] or manifest.get("target_date") != handoff["target_date"]:
        raise ValueError("batch manifest identity mismatch")
    if manifest.get("clean_reader_manifest_sha256") != handoff["reader_stripped_manifest_sha256"]:
        raise ValueError("batch manifest clean Reader mismatch")

    cores = {}
    for entry in manifest.get("entries", []):
        path = root / entry["file"]
        raw = path.read_bytes()
        if digest(raw) != entry.get("sha256"):
            raise ValueError(f"venue batch digest mismatch: {path.name}")
        payload = json.loads(raw)
        if payload.get("logic_version") != LOGIC:
            raise ValueError(f"venue batch logic mismatch: {path.name}")
        hashes = payload.get("decision_core_sha256") or []
        decisions = payload.get("decisions") or []
        if len(hashes) != len(decisions):
            raise ValueError(f"venue batch core hash count mismatch: {path.name}")
        for core, expected_hash in zip(decisions, hashes):
            if digest(canonical(core)) != expected_hash:
                raise ValueError(f"Decision Core hash mismatch: {path.name}")
            key = (str(core["venue"]), int(core["race_no"]))
            if key in cores:
                raise ValueError(f"duplicate Decision Core: {key}")
            if key not in readers:
                raise ValueError(f"Decision Core absent from clean card: {key}")
            cores[key] = core
    if set(cores) != set(readers):
        raise ValueError(f"incomplete Decision Core card: missing={sorted(set(readers)-set(cores))}")
    return cores


def materialize(core: dict, reader: dict, selection_id: str, date: str) -> dict:
    race = reader["race"]
    venue, race_no = str(race["venue"]), int(race["race_no"])
    horses = {int(h["basic"]["horse_no"]): h for h in reader["horses"]}

    def ref(n: int) -> dict:
        n = int(n)
        horse = horses[n]
        return {"horse_no": n, "horse_name": str(horse["basic"]["horse_name"]).strip()}

    marks = [int(x) for x in core["marks"]]
    mainline = core["mainline_cases"]
    single = core["single_shot_case"]
    boundary = core["boundary_review"]

    rrdb_refs = []
    for item in core.get("rrdb_refs", []):
        n = int(item["horse_no"])
        recommendation = (horses[n].get("racereview") or {}).get("recommendation") or {}
        if recommendation.get("contract_version") != RRDB:
            raise ValueError(f"{venue}{race_no}R: cited RRDB horse lacks v0.3 evidence")
        rrdb_refs.append({
            **ref(n),
            "decision_role": item["decision_role"],
            "recommendation_contract_version": RRDB,
            "source_run_ref": str((recommendation.get("source_run") or {}).get("race_key") or ""),
            "matched_signal_ids": recommendation.get("matched_signal_ids") or [],
            "next_watch_grade": None,
            "matched_rule_ids": [],
        })

    alt = boundary.get("alternative_horse_no")
    compact = date.replace("-", "")
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
            "execution_contract": "RACENOTE_EXECUTION_V0.4.6",
            "reader_facing_prose_contract": "FORECAST_READER_FACING_PROSE_v0_1",
            "authoring_mode": "MODEL_UNIFIED_RACE_JUDGMENT",
            "prose_origin": "MODEL_AUTHORED_NOT_SCRIPT_GENERATED",
            "independent_forecast": True,
            "baseline_marks_used_as_input": False,
        },
        "source": {
            "racenote_identity": f"{selection_id}/{venue}{race_no}R",
            "racenote_semantic_sha256": reader["source_semantic_sha256"],
            "reader_input_policy": "TARGET_DAY_MARKET_OBJECT_REMOVED_BEFORE_FORECAST",
        },
        "prediction": {
            "axis": ref(marks[0]),
            "marks": {
                "main": ref(marks[0]),
                "second": ref(marks[1]),
                "third": ref(marks[2]),
                "others": [ref(marks[3]), ref(marks[4])],
            },
            "reader_facing_reason": core["reader_facing_reason"],
        },
        "decision_trace": {
            "race_model": core["race_model"],
            "mainline_cases": [
                {"horse": ref(x["horse_no"]), "case": x["case"]} for x in mainline
            ],
            "single_shot_case": {
                "horse": ref(single["horse_no"]),
                "selected_independently_from_mainline": True,
                "case": single["case"],
            },
            "support_boundary": {
                "final_delta2": ref(marks[4]),
                "alternative": ref(alt) if alt is not None else None,
                "reason": boundary["reason"],
            },
            "rrdb_evidence": {
                "available": any(
                    ((h.get("racereview") or {}).get("recommendation") or {}).get("contract_version") == RRDB
                    for h in horses.values()
                ),
                "reviewed": True,
                "used_in_decision": bool(rrdb_refs),
                "horse_refs": rrdb_refs,
                "reason_not_used": None if rrdb_refs else "No RRDB evidence was material enough to cite in the final race decision.",
                "recommendation_contract_version": RRDB,
            },
        },
        "audit": {
            "pre_result_guard": "PASS",
            "result_visible_at_freeze": False,
            "market_blind": True,
            "target_market_opened": False,
            "decision_core_sha256": digest(canonical(core)),
        },
    }
    validate_prepared_record(record, reader, selection_id, date, LOGIC)
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prep-root", type=Path, required=True)
    ap.add_argument("--batches-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--selection-id", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--main-sha", required=True)
    args = ap.parse_args()

    handoff, readers = load_clean(args.prep_root, args.selection_id, args.date, args.main_sha)
    cores = load_batches(args.batches_root, handoff, readers)
    records = [materialize(cores[key], readers[key], args.selection_id, args.date) for key in sorted(readers)]

    report = audit_turn(records)
    if report["status"] != "PASS":
        raise ValueError("v0.4.6 card validator FAIL: " + "; ".join(report["errors"]))
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
