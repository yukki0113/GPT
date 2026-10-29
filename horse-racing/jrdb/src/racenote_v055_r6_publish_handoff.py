#!/usr/bin/env python3
"""Generate strict one-file GitHub commit instructions for RaceNote r6.

No network, no LLM inference, no writes, no Freeze execution.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from racenote_v055_r6_submit_gate import build
from racenote_v055_r6_race_checkpoint_store import state, canon
from racenote_v055_turn2_two_phase import resolve_root

REPO="yukki0113/GPT"
# Production checkpoints belong to main, separately from the canonical T1 root.
# PR regressions may explicitly select their isolated existing test branch.
BRANCH=os.environ.get("RACENOTE_CHECKPOINT_BRANCH", "main")
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}",BRANCH):
    raise ValueError("invalid checkpoint branch")

def make(root, store, action, draft=None):
    session,saved,missing=state(root,store)
    if action=="checkpoint":
        if draft is None or not draft.is_file() or draft.is_symlink():
            raise ValueError("missing regular draft")
        row=json.loads(draft.read_text(encoding="utf-8"))
        key=(str(row["venue"]),int(row["race_no"]))
        if key not in saved or canon(saved[key])!=canon(row):
            raise ValueError("draft is not a previously validated checkpoint")
        target=store/f"{key[0]}_{key[1]:02d}.json"
        # A checkpoint must live under the approved repository-local directory.
        allowed=Path(f"horse-racing/jrdb/llm_checkpoints/{session['selection_id']}/prediction")
        if store!=allowed or target.is_symlink():
            raise ValueError("unapproved checkpoint destination")
        return {"action":"COMMIT_ONE_FILE","repo":REPO,"branch":BRANCH,
                "path":str(target),"sha256":hashlib.sha256(canon(row)).hexdigest(),
                "requires_remote_absence_or_same_content":True,"freeze":False,
                "completed":len(saved),"remaining":len(missing)}
    if action=="prediction":
        if missing:raise ValueError(f"prediction incomplete: {len(saved)}/{len(saved)+len(missing)}")
        if draft is None:raise ValueError("missing assembled draft")
        expected=canon([saved[k] for k in sorted(saved)])
        if draft.read_bytes()!=expected:raise ValueError("assembled bytes disagree with validated checkpoints")
        gate=build(root,"prediction",draft)
        return {"action":"COMMIT_ONE_FILE","repo":REPO,"branch":"main",
                "path":gate["target_path"],"sha256":gate["draft_sha256"],
                "expected_workflow":gate["expected_workflow"],
                "requires_remote_absence":True,"freeze":True,
                "completed":len(saved),"remaining":0}
    raise ValueError("unknown action")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--store",required=True,type=Path)
    p.add_argument("--action",choices=("checkpoint","prediction"),required=True)
    p.add_argument("--draft",type=Path,required=True)
    a=p.parse_args()
    root=resolve_root(a.root)
    if a.store.is_symlink() or a.store.resolve().is_relative_to(root.parents[1].resolve()):
        raise ValueError("invalid checkpoint store")
    print(json.dumps(make(root,a.store,a.action,a.draft),ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
