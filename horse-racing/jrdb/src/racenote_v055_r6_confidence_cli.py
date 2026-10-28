#!/usr/bin/env python3
"""Independent LLM-authored r6 Confidence checkpoints. No grade generation.

Works only AFTER a verified canonical Prediction Freeze is present locally.
No direct writes to canonical root, no market/results, and no model calls.
"""
import argparse
import json
import re
from pathlib import Path

from racenote_v055_r6_race_checkpoint_store import canon
from racenote_v055_turn2_two_phase import resolve_root, preflight
from racenote_v055_single_day import (
    load_session, verify_freeze, _validate_confidence_grade,
)

def context(root, store):
    if store.is_symlink() or (store.exists() and not store.is_dir()):
        raise ValueError("invalid confidence checkpoint directory")
    if store.resolve().is_relative_to(root.parents[1].resolve()):
        raise ValueError("checkpoints inside canonical BTDAY")
    if not (root / "frozen/day_handoff.json").is_file():
        raise ValueError("committed Prediction Freeze required")
    if (root / "confidence_frozen").exists():
        raise ValueError("Confidence already frozen")
    verify_freeze(root)
    session, _, entries = load_session(root)
    frozen = json.loads((root / "frozen/records.json").read_text(encoding="utf-8"))
    by_key = {(r["venue"], int(r["race_no"])): r for r in frozen}
    if len(by_key) != len(session["race_roster"]):
        raise ValueError("frozen race roster mismatch")
    existing = {}
    for path in sorted(store.glob("*.json")) if store.is_dir() else []:
        match = re.fullmatch(r"(.+)_([0-9]{2})\.json", path.name)
        if path.is_symlink() or not match:
            raise ValueError("unexpected confidence checkpoint path")
        obj = json.loads(path.read_text(encoding="utf-8"))
        key = (str(obj.get("venue")), int(obj.get("race_no", -1)))
        if key != (match.group(1), int(match.group(2))) or key in existing:
            raise ValueError("confidence identity mismatch")
        validate(root, session, entries, by_key, key, obj)
        existing[key] = obj
    return session, entries, by_key, existing

def validate(root, session, entries, by_key, key, obj):
    if key not in by_key or set(obj) != {"venue","race_no","honmei","confidence","reason"}:
        raise ValueError("unknown race or malformed Confidence draft")
    if type(obj["race_no"]) is not int or type(obj["honmei"]) is not int:
        raise ValueError("invalid race/honmei type")
    expected = by_key[key]["decision_core"]["marks"][0]
    if obj["honmei"] != expected:
        raise ValueError("frozen honmei mismatch")
    reader = json.loads((root / "reader" / entries[key]["derived_normal_filename"]).read_text(encoding="utf-8"))
    _validate_confidence_grade(reader, obj["confidence"], session["contract_revision"])
    if not isinstance(obj["reason"],str) or len(obj["reason"].strip()) < 12:
        raise ValueError("insufficient independent Confidence reason")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--store", required=True, type=Path)
    sub = p.add_subparsers(dest="action",required=True)
    sub.add_parser("status")
    sub.add_parser("next")
    save=sub.add_parser("save");save.add_argument("--draft",required=True,type=Path)
    assemble=sub.add_parser("finalize");assemble.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    root=resolve_root(args.root)
    session, entries, by_key, records=context(root,args.store)
    if args.action=="save":
        if args.draft.is_symlink() or not args.draft.is_file():raise ValueError("invalid draft")
        obj=json.loads(args.draft.read_text(encoding="utf-8"))
        key=(str(obj["venue"]),int(obj["race_no"]))
        validate(root,session,entries,by_key,key,obj)
        if key in records:
            if canon(records[key])!=canon(obj):raise ValueError("immutable Confidence conflict")
        else:
            args.store.mkdir(parents=True,exist_ok=True)
            with (args.store / f"{key[0]}_{key[1]:02d}.json").open("xb") as f:f.write(canon(obj))
            records[key]=obj
    missing=sorted(set(by_key)-set(records))
    response={"status":"COMPLETE" if not missing else "IN_PROGRESS",
              "phase":"confidence","selection_id":session["selection_id"],
              "session_id":session["session_id"],"completed":len(records),
              "remaining":len(missing)}
    if args.action=="next" and missing:
        key=missing[0]
        response["next_race"]={"venue":key[0],"race_no":key[1],
                               "frozen_honmei":by_key[key]["decision_core"]["marks"][0],
                               "reader_path":str(root/"reader"/entries[key]["derived_normal_filename"])}
    if args.action=="finalize":
        if missing:raise ValueError(f"incomplete Confidence: {len(records)}/{len(by_key)}")
        if args.output.exists() or args.output.is_symlink():raise FileExistsError("output exists")
        args.output.parent.mkdir(parents=True,exist_ok=True)
        data=canon([records[k] for k in sorted(records)])
        with args.output.open("xb") as f:f.write(data)
        try:preflight(root,args.output,"confidence")
        except Exception:
            args.output.unlink()
            raise
        response["ready_for_submit_gate"]=True
        response["output"]=str(args.output)
    print(json.dumps(response,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
