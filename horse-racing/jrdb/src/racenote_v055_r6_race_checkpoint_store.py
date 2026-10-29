#!/usr/bin/env python3
"""Immutable, per-race LLM checkpoint store (transport, never authoring).

Separate from canonical BTDAY root and r6 Freeze. A race is saved only when a
human/LLM-supplied Decision Core passes the existing canonical validator.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from racenote_v055_single_day import load_session, _validator_reader
from racenote_decision_core_v055 import validate_core

SID = re.compile(r"BTDAY-\d{4}")
def canon(obj):
    return (json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
def load(p): return json.loads(p.read_bytes())
def state(root,store):
    session,_,entries=load_session(root)
    expected={(x["venue"],int(x["race_no"])) for x in session["race_roster"]}
    accepted={}
    for file in sorted(store.glob("*.json")) if store.is_dir() else []:
        m=re.fullmatch(r"(.+)_([0-9]{2})\.json",file.name)
        if not m or file.is_symlink(): raise ValueError("unexpected checkpoint: "+str(file))
        row=load(file);key=(str(row["venue"]),int(row["race_no"]))
        if key!=(m.group(1),int(m.group(2))) or key not in expected or key in accepted:
            raise ValueError("checkpoint identity mismatch")
        normal=load(root/"reader"/entries[key]["derived_normal_filename"])
        validate_core(row,_validator_reader(normal),contract_revision=session["contract_revision"])
        accepted[key]=row
    remaining=sorted(expected-set(accepted))
    return session,accepted,remaining
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--store",type=Path,required=True)
    sub=p.add_subparsers(dest="action",required=True)
    save=sub.add_parser("save");save.add_argument("--draft",type=Path,required=True)
    sub.add_parser("status")
    assemble=sub.add_parser("assemble");assemble.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    root=a.root
    if not re.fullmatch(r"horse-racing/jrdb/backtests/BTDAY-\d{4}/\d{8}/v055",root.as_posix()):
        raise SystemExit("unapproved root")
    if a.store.is_symlink() or (a.store.exists() and not a.store.is_dir()):
        raise SystemExit("invalid checkpoint store")
    # checkpoints must never be placed under any canonical BTDAY source root
    if a.store.resolve().is_relative_to(root.parents[1].resolve()):
        raise SystemExit("checkpoint store must be outside BTDAY canonical root")
    session,accepted,remaining=state(root,a.store)
    if a.action=="save":
        if not a.draft.is_file() or a.draft.is_symlink(): raise SystemExit("invalid draft")
        obj=load(a.draft)
        key=(obj.get("venue"),int(obj.get("race_no",-1)))
        if key in accepted:
            if canon(accepted[key])!=canon(obj):raise SystemExit("immutable checkpoint conflict")
            print(json.dumps({"status":"ALREADY_SAVED","race":key},ensure_ascii=False));return
        if key not in remaining: raise SystemExit("unknown race")
        _,_,entries=load_session(root)
        normal=load(root/"reader"/entries[key]["derived_normal_filename"])
        validate_core(obj,_validator_reader(normal),contract_revision=session["contract_revision"])
        a.store.mkdir(parents=True,exist_ok=True)
        destination=a.store/f"{key[0]}_{key[1]:02d}.json"
        with destination.open("xb") as out:out.write(canon(obj))
        accepted[key]=obj;remaining.remove(key)
    if a.action=="assemble":
        if remaining:raise SystemExit(f"incomplete day {len(accepted)}/{len(accepted)+len(remaining)}")
        if a.output.exists():raise SystemExit("output exists")
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with a.output.open("xb") as out:out.write(canon([accepted[k] for k in sorted(accepted)]))
    print(json.dumps({"status":"COMPLETE" if not remaining else "IN_PROGRESS","selection_id":session["selection_id"],"session_id":session["session_id"],"saved":len(accepted),"remaining":len(remaining),"remaining_races":[{"venue":v,"race_no":n} for v,n in remaining],"checkpoint_hashes":{f"{v}_{n:02d}":hashlib.sha256(canon(item)).hexdigest() for (v,n),item in sorted(accepted.items())}},ensure_ascii=False))
if __name__=="__main__": main()
