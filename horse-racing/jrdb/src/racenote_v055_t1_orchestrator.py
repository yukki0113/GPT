#!/usr/bin/env python3
"""RaceNote r6 T1 pipeline selection and status control (NO LLM decisions).

Called from the T1 Orchestrator workflow. Only 'prepare NEXT' can reserve
one random eligible historical date. Existing T1 roots are immutable.
No prediction, market, results, or Freeze access.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from racenote_backtest_day_picker import load_json, pick_days, save_json

POOL=Path("horse-racing/jrdb/config/racenote_backtest_day_pool_2026.json")
BASE=Path("horse-racing/jrdb/backtests")
CONTRACT="v055-prediction-freeze-confidence-review-r6"
SID=re.compile(r"BTDAY-\d{4}\Z")

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
            or data.get("status")!="READY_FOR_V055_AUTHORING"
            or data.get("market_blind") is not True
            or data.get("result_opened") is not False
            or data.get("target_market_opened") is not False
            or not (base/"v055/authoring_bundle/manifest.json").is_file()):
            raise ValueError("T1 handoff corrupted or generation mismatch: "+sid)
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
        state=t1_state(selected)
        if state=="T1_NOT_CREATED":
            req=BASE/"requests"/(sid+".v055r6-turn1")
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

def run(command,sid=None):
    if command=="T2_ONLY":
        return {"mode":"T2_ONLY","action":"SKIPPED","start_t1":False}
    if command=="NEXT":
        selection,created=choose_next()
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
    request=BASE/"requests"/(selection["selection_id"]+".v055r6-turn1")
    if command=="STATUS":
        action="READ_ONLY_STATUS"
        start=False
    elif state=="T1_READY":
        action="REUSE_READY"
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
    p.add_argument("mode",choices=("NEXT","EXISTING","STATUS","T2_ONLY"))
    p.add_argument("--selection-id")
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    result=run(args.mode,args.selection_id)
    raw=json.dumps(result,ensure_ascii=False,sort_keys=True)+"\n"
    if args.output:
        if args.output.exists():
            raise ValueError("output already exists")
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(raw,encoding="utf-8")
    print(raw,end="")
if __name__=="__main__":
    main()
