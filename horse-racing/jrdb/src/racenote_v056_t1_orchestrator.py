#!/usr/bin/env python3
"""RaceNote v0.5.6 T1 pipeline selection and status control (NO LLM decisions).

Called from the T1 Orchestrator workflow. Only 'prepare NEXT' can reserve
one random eligible historical date. Existing T1 roots are immutable.
No prediction, market, results, or Freeze access.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from racenote_backtest_day_picker import load_json, pick_days, save_json
from racenote_v056_btday_source_router import (
    draw_v2, plan_reservation, resolve_inventory, verify_readiness_receipt,
)

POOL=Path("horse-racing/jrdb/config/racenote_backtest_day_pool_2026.json")
BASE=Path("horse-racing/jrdb/backtests")
INVENTORY=Path("horse-racing/jrdb/config/racenote_btday_source_inventory_v2.json")
GATE=Path("horse-racing/jrdb/config/racenote_v056_mixed_source_gate.json")
CONTRACT="v056-prediction-confidence-audit-newspaper-v1"
SID=re.compile(r"BTDAY-\d{4}\Z")


def mixed_source_enabled(source_mode=None):
    """Allow only source modes with verifiable T1 acceptance; never infer READY.

    This is a *per-source* admission check. Prediction/Confidence Freeze is
    validated after T1, not demanded before the first BTDAY prediction.
    Legacy E2E proofs also remain valid as stronger evidence.
    """
    if source_mode is not None and source_mode not in ("historical_warehouse", "paci"):
        raise ValueError("unknown BTDAY source mode")
    if not GATE.exists():
        return False
    gate = load_json(GATE)
    if gate.get("schema_version") != "racenote-v056-mixed-source-gate-v1":
        raise ValueError("invalid mixed-source gate schema")
    if gate.get("status") == "DISABLED":
        return False
    if gate.get("status") not in ("ACCEPTED", "PARTIAL_ACCEPTED"):
        raise ValueError("invalid mixed-source gate status")
    approved = set()
    root = Path.cwd().resolve()
    for key in ("historical_warehouse", "paci"):
        proof = (gate.get("acceptance") or {}).get(key)
        if proof is None:
            continue
        if (not isinstance(proof, dict) or proof.get("status") != "PASS"
                or not re.fullmatch(r"[1-9]\d*", str(proof.get("run_id", "")))
                or not re.fullmatch(r"[0-9a-f]{64}", str(proof.get("receipt_sha256", "")))):
            raise ValueError(f"mixed-source gate lacks {key} acceptance")
        rel = Path(str(proof.get("receipt_path") or ""))
        path = root / rel
        if (rel.is_absolute() or not rel.parts or ".." in rel.parts or path.is_symlink()
                or not path.is_file() or not path.resolve().is_relative_to(root)
                or hashlib.sha256(path.read_bytes()).hexdigest() != proof["receipt_sha256"]):
            raise ValueError(f"mixed-source gate {key} acceptance receipt invalid")
        receipt = load_json(path)
        if (receipt.get("schema_version") not in
                ("racenote-v056-btday-e2e-acceptance-v1",
                 "racenote-v056-btday-t1-acceptance-v1")
                or receipt.get("status") != "PASS"
                or receipt.get("source_mode") != key
                or str(receipt.get("run_id")) != str(proof["run_id"])
                or any(receipt.get(field) is not True for field in
                       ("t1_verified", "artifact_verified", "main_readback_verified",
                        "blind_verified"))):
            raise ValueError(f"mixed-source gate {key} T1 acceptance incomplete")
        approved.add(key)
    if not approved:
        raise ValueError("mixed-source gate has no accepted source")
    if gate["status"] == "ACCEPTED" and len(approved) != 2:
        raise ValueError("ACCEPTED gate requires both sources; use PARTIAL_ACCEPTED")
    return bool(approved) if source_mode is None else source_mode in approved


def preview_mixed(inventory_path, operational_date=None, seed=None):
    """Resolve a proposed v2 draw without reserving or enabling production NEXT."""
    payload = load_json(inventory_path)
    rows = payload.get("source_inventory") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("source_inventory must be a list")
    day = operational_date or datetime.now(ZoneInfo("Asia/Tokyo")).date()
    pool = load_json(POOL)
    resolved = resolve_inventory(rows, day, lambda row: verify_readiness_receipt(row, Path.cwd()))
    proposal = draw_v2(resolved, pool.get("selections", []), BASE, day, seed)
    return {"mode": "SHADOW", "action": "PREVIEW_ONLY", "start_t1": False,
            "created_selection": False, "proposal": proposal}

def selection_path(sid):
    if not SID.fullmatch(sid):
        raise ValueError("invalid BTDAY selection ID")
    return BASE/sid/"selection.json"

def read_selection(sid):
    path=selection_path(sid)
    if not path.is_file():
        raise ValueError("selection not found: "+sid)
    selection=load_json(path)
    sources=selection.get("sources",[])
    if selection.get("selection_schema_version") == "btday-source-selection-v2":
        row = selection.get("source_row") or {}
        if (selection.get("selection_id") != sid or selection.get("n") != 1
                or selection.get("dates") != [selection.get("target_date")]
                or len(sources) != 1 or row.get("target_date") != selection.get("target_date")
                or any(sources[0].get(key) != row.get(row_key) for key, row_key in (
                    ("target_date", "target_date"), ("source_mode", "source_mode"),
                    ("source_reference", "source_reference"), ("source_generation_id", "source_generation_id"),
                    ("source_receipt_sha256", "receipt_sha256")))
                or row.get("source_mode") not in ("paci", "historical_warehouse")
                or row.get("source_mode") != selection.get("source_mode")
                or row.get("source_generation_id") != selection.get("source_generation_id")
                or row.get("source_reference") != selection.get("source_reference")
                or row.get("receipt_sha256") != selection.get("source_receipt_sha256")):
            raise ValueError("v2 selection source identity mismatch")
        if date.fromisoformat(selection["target_date"]).isoformat() != selection["target_date"]:
            raise ValueError("v2 selection date is not canonical")
        return selection
    if (selection.get("selection_id")!=sid or selection.get("n")!=1
        or len(selection.get("dates",[]))!=1
        or len(sources)!=1
        or sources[0].get("source_mode")!="historical_warehouse"
        or not str(selection["dates"][0]).startswith("2025-")):
        raise ValueError("selection incompatible with shared T1")
    return selection

def t1_state(selection):
    sid=selection["selection_id"]
    base=BASE/sid/selection["dates"][0].replace("-","")
    op=base/"operation_handoff.json"
    if op.exists():
        data=load_json(op)
        if (data.get("selection_id")!=sid
            or data.get("target_date")!=selection["dates"][0]
            or data.get("contract_revision")!=CONTRACT
            or data.get("status")!="READY_FOR_V056_AUTHORING"
            or data.get("market_blind") is not True
            or data.get("result_opened") is not False
            or data.get("target_market_opened") is not False
            or not (base/"v056/authoring_bundle/manifest.json").is_file()):
            raise ValueError("T1 handoff corrupted or generation mismatch: "+sid)
        if selection.get("selection_schema_version") == "btday-source-selection-v2":
            row = selection["source_row"]
            mode = data.get("source_mode", data.get("source_backend"))
            if (mode != row["source_mode"] or data.get("source_generation_id") != row["source_generation_id"]
                    or data.get("source_receipt_sha256") != row["receipt_sha256"]
                    or data.get("source_sha256") != row["input_sha256"]
                    or data.get("as_of_exclusive") != selection["target_date"]):
                raise ValueError("v2 T1 source binding mismatch: " + sid)
            from racenote_v056_single_day import load_session
            session, _, readers = load_session(base / "v056")
            authoring = load_json(base / "v056/authoring_bundle/manifest.json")
            if (session.get("selection_id") != sid or session.get("target_date") != selection["target_date"]
                    or session.get("session_id") != data.get("session_id")
                    or session.get("market_blind") is not True or session.get("result_opened") is not False
                    or session.get("target_market_opened") is not False
                    or authoring.get("session_id") != session.get("session_id")
                    or authoring.get("race_count") != len(readers)):
                raise ValueError("v2 T1 Reader or authoring identity mismatch: " + sid)
        return "T1_READY"
    if base.exists():
        raise ValueError("partial canonical T1; do not overwrite: "+sid)
    return "T1_NOT_CREATED"

def choose_next():
    # Idempotently resume a selected but not yet launched selection.
    # If a request already exists, another T1 may be in flight: do not start it twice.
    pool=load_json(POOL)
    for item in reversed(pool.get("selections",[])):
        sid=item.get("selection_id")
        if not sid or not SID.fullmatch(sid) or not selection_path(sid).exists():
            continue
        selected=read_selection(sid)
        # A previous v055 selection is historical and must not be interpreted
        # as a corrupt v056 T1. Reserve a new selection instead.
        base=BASE/sid/selected["dates"][0].replace("-","")
        legacy=base/"operation_handoff.json"
        if legacy.is_file():
            old_handoff=load_json(legacy)
            if old_handoff.get("contract_revision") != CONTRACT:
                break
        state=t1_state(selected)
        if state=="T1_NOT_CREATED":
            req=BASE/"requests"/(sid+".v056-turn1")
            if req.exists():
                raise ValueError("T1 request already exists for "+sid+"; inspect workflow rather than duplicate")
            return selected,False
        # The most recent selection is READY: reserve the next random day.
        break
    # Current shared T1 depends on verified 2025 KYI/BAC archives.
    # Restore the inventory's true eligibility after choosing a 2025 date.
    flags=[row.get("eligible",True) for row in pool["days"]]
    try:
        for row in pool["days"]:
            if not str(row.get("date","")).startswith("2025-"):
                row["eligible"]=False
        new=pick_days(pool,1,source_mode="historical_warehouse")
    finally:
        for row,eligible in zip(pool["days"],flags):
            row["eligible"]=eligible
    sid=new["selection_id"]
    if selection_path(sid).exists():
        raise ValueError("selection already exists: "+sid)
    save_json(POOL,pool)
    save_json(selection_path(sid),new)
    return new,True


def choose_next_v2(operational_date=None, seed=None):
    """Prepare pool+Selection together; remote publication is one Git commit."""
    day = operational_date or datetime.now(ZoneInfo("Asia/Tokyo")).date()
    lock_id = hashlib.sha256(str(POOL.resolve()).encode()).hexdigest()[:20]
    lock_path = Path(tempfile.gettempdir()) / f"racenote-v056-{lock_id}.lock"
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        pool = load_json(POOL)
        if pool.get("selections"):
            last = pool["selections"][-1]
            if last.get("selection_schema_version") == "btday-source-selection-v2" and not last.get("released_at"):
                selected = read_selection(last["selection_id"])
                if selected != last:
                    raise ValueError("reserved Selection differs from pool")
                if t1_state(selected) == "T1_NOT_CREATED":
                    return selected, False
            elif not last.get("released_at") and SID.fullmatch(str(last.get("selection_id") or "")):
                sid = last["selection_id"]
                if selection_path(sid).is_file():
                    selected = read_selection(sid)
                    op = BASE / sid / selected["dates"][0].replace("-", "") / "operation_handoff.json"
                    if not op.exists() and t1_state(selected) == "T1_NOT_CREATED":
                        return selected, False
        payload = load_json(INVENTORY)
        rows = payload.get("source_inventory") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise ValueError("source_inventory must be a list")
        resolved = resolve_inventory(rows, day, lambda row: verify_readiness_receipt(row, Path.cwd()))
        # An accepted source cannot authorize an unaccepted mode's inventory.
        resolved = {day_key: row for day_key, row in resolved.items()
                    if mixed_source_enabled(row["source_mode"])}
        updated, selected = plan_reservation(pool, resolved, BASE, day, seed)
        # Verify the selected receipt immediately before reservation.
        verify_readiness_receipt(selected["source_row"], Path.cwd())
        path = selection_path(selected["selection_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        created_file = False
        try:
            with path.open("x", encoding="utf-8") as f:
                created_file = True
                json.dump(selected, f, ensure_ascii=False, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            save_json(POOL, updated)
        except BaseException:
            if created_file:
                path.unlink(missing_ok=True)
            raise
        return selected, True

def run(command,sid=None,inventory=None,operational_date=None,seed=None):
    if command=="SHADOW":
        if inventory is None:
            raise ValueError("SHADOW requires --inventory")
        return preview_mixed(inventory, operational_date, seed)
    if command=="T2_ONLY":
        return {"mode":"T2_ONLY","action":"SKIPPED","start_t1":False}
    if command=="NEXT":
        selection,created=(choose_next_v2(operational_date,seed) if mixed_source_enabled() else choose_next())
    elif command in ("EXISTING","STATUS"):
        if not sid:
            if command=="STATUS":
                pool=load_json(POOL)
                if not pool.get("selections"):
                    raise ValueError("no selections")
                sid=pool["selections"][-1]["selection_id"]
            else:
                raise ValueError("EXISTING requires --selection-id")
        selection=read_selection(sid)
        created=False
    else:
        raise ValueError("unknown command")
    state=t1_state(selection)
    request=BASE/"requests"/(selection["selection_id"]+".v056-turn1")
    if command=="STATUS":
        action="READ_ONLY_STATUS"
        start=False
    elif state=="T1_READY":
        action="REUSE_READY"
        start=False
    elif selection.get("selection_schema_version") == "btday-source-selection-v2" and not mixed_source_enabled(selection["source_mode"]):
        action="SOURCE_GATE_CLOSED"
        start=False
    elif request.exists():
        action="ALREADY_REQUESTED"
        start=False
    else:
        action="PREPARE_NEW_T1"
        start=True
    return {
        "mode":command,
        "selection_id":selection["selection_id"],
        "target_date":selection["dates"][0],
        "source_mode": (selection.get("source_mode") or selection["sources"][0].get("source_mode")),
        "contract_revision":CONTRACT,
        "state":state,
        "action":action,
        "created_selection":created,
        "start_t1":start,
        "immutable_target":str(BASE/selection["selection_id"]/selection["dates"][0].replace("-","")),
        "result_opened":False,
        "target_market_opened":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("NEXT","EXISTING","STATUS","T2_ONLY","SHADOW"))
    p.add_argument("--selection-id")
    p.add_argument("--output",type=Path)
    p.add_argument("--inventory",type=Path)
    p.add_argument("--operational-date",type=date.fromisoformat)
    p.add_argument("--seed")
    args=p.parse_args()
    result=run(args.mode,args.selection_id,args.inventory,args.operational_date,args.seed)
    raw=json.dumps(result,ensure_ascii=False,sort_keys=True)+"\n"
    if args.output:
        if args.output.exists():
            raise ValueError("output already exists")
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(raw,encoding="utf-8")
    print(raw,end="")
if __name__=="__main__":
    main()
