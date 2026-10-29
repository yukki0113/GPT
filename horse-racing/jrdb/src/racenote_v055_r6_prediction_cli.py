#!/usr/bin/env python3
"""Compact RaceNote r6 prediction transport CLI. No model decisions or market access."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
from racenote_v055_r6_race_checkpoint_store import state
from racenote_v055_r6_submit_gate import build
from racenote_v055_turn2_two_phase import resolve_root

def run():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",required=True)
    p.add_argument("--store",required=True,type=Path)
    sub=p.add_subparsers(dest="action",required=True)
    sub.add_parser("status")
    sub.add_parser("next")
    save=sub.add_parser("save");save.add_argument("--draft",required=True,type=Path)
    fin=sub.add_parser("finalize");fin.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    root=resolve_root(a.root)
    store=a.store
    if store.is_symlink() or (store.exists() and not store.is_dir()):
        raise ValueError("invalid checkpoint store")
    if store.resolve().is_relative_to(root.parents[1].resolve()):
        raise ValueError("checkpoint store inside canonical BTDAY")
    session,saved,missing=state(root,store)
    if a.action=="save":
        if not a.draft.is_file() or a.draft.is_symlink():
            raise ValueError("invalid LLM draft")
        obj=json.loads(a.draft.read_text(encoding="utf-8"))
        key=(str(obj["venue"]),int(obj["race_no"]))
        subprocess.run([sys.executable,str(Path(__file__).with_name("racenote_v055_r6_race_checkpoint_store.py")),
                        "--root",str(root),"--store",str(store),"save","--draft",str(a.draft)],
                        check=True,capture_output=True,text=True)
        session,saved,missing=state(root,store)
        print(json.dumps({"status":"SAVED","race":{"venue":key[0],"race_no":key[1]},
                          "saved":len(saved),"remaining":len(missing),
                          "checkpoint_path":str(store/f"{key[0]}_{key[1]:02d}.json")},ensure_ascii=False))
        return
    if a.action=="finalize":
        if missing: raise ValueError(f"cannot finalize incomplete predictions: {len(saved)}/{len(saved)+len(missing)}")
        if a.output.exists():raise FileExistsError("finalized output already exists")
        from racenote_v055_r6_race_checkpoint_store import canon
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with a.output.open("xb") as f:f.write(canon([saved[k] for k in sorted(saved)]))
        try:
            gate=build(root,"prediction",a.output)
        except Exception:
            a.output.unlink()
            raise
        print(json.dumps(gate,ensure_ascii=False,sort_keys=True));return
    payload={"status":"PREDICTION_COMPLETE" if not missing else "PREDICTION_IN_PROGRESS",
             "selection_id":session["selection_id"],"session_id":session["session_id"],
             "completed":len(saved),"remaining":len(missing)}
    if a.action=="next":
        if missing:
            key=missing[0]
            _,_,entries=__import__("racenote_v055_single_day",fromlist=["load_session"]).load_session(root)
            reader=root/"reader"/entries[key]["derived_normal_filename"]
            payload["next_race"]={"venue":key[0],"race_no":key[1],
                "reader_path":str(reader),"reader_sha256":hashlib.sha256(reader.read_bytes()).hexdigest(),
                "checkpoint_path":str(store/f"{key[0]}_{key[1]:02d}.json")}
        else:payload["next_action"]="finalize"
    print(json.dumps(payload,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    try:run()
    except (ValueError,FileNotFoundError,FileExistsError,subprocess.CalledProcessError) as exc:
        print(json.dumps({"status":"BLOCKED","error":str(exc)},ensure_ascii=False),file=sys.stderr)
        sys.exit(1)
