#!/usr/bin/env python3
"""Collect independently LLM-authored per-race r6 drafts. Never predict or grade."""
import argparse
import json
import re
from pathlib import Path

from racenote_v055_turn2_two_phase import preflight, resolve_root

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--phase",choices=("prediction","confidence"),required=True)
    p.add_argument("--draft-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    root=resolve_root(args.root)
    session=json.loads((root/"session.json").read_text(encoding="utf-8"))
    if session.get("contract_revision")!="v055-prediction-freeze-confidence-review-r6":
        raise SystemExit("unsupported contract")
    if args.phase=="prediction" and (root/"frozen").exists():
        raise SystemExit("prediction already frozen")
    if args.phase=="confidence" and ((root/"confidence_frozen").exists() or not (root/"frozen/day_handoff.json").is_file()):
        raise SystemExit("confidence requires committed prediction freeze")
    if not args.draft_dir.is_dir() or args.draft_dir.is_symlink():
        raise SystemExit("invalid draft directory")
    expected={(str(x["venue"]),int(x["race_no"])) for x in session["race_roster"]}
    rows={}
    for file in sorted(args.draft_dir.iterdir()):
        if file.is_symlink() or not file.is_file() or not re.fullmatch(r"[^/\\]+_\d{1,2}\.json",file.name):
            raise SystemExit("unexpected draft path: "+file.name)
        data=json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(data,dict):raise SystemExit("one JSON object required per race")
        key=(str(data.get("venue")),int(data.get("race_no",-1)))
        if key not in expected or key in rows:raise SystemExit("unknown or duplicate race: "+str(key))
        if file.name!=f"{key[0]}_{key[1]:02d}.json":raise SystemExit("draft filename mismatch")
        rows[key]=data
    if set(rows)!=expected:
        raise SystemExit(f"incomplete coverage: {len(rows)}/{len(expected)}")
    draft=sorted(rows.values(),key=lambda x:(str(x["venue"]),int(x["race_no"])))
    # Validate using the canonical two-phase preflight; never invent grades or marks.
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit("refusing to overwrite any existing draft")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    # Output must be outside the target canonical incoming path while verifying.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        candidate=Path(tmp)/"draft.json"
        candidate.write_text(json.dumps(draft,ensure_ascii=False)+"\n",encoding="utf-8")
        preflight(root,candidate,args.phase)
        args.output.write_bytes(candidate.read_bytes())
    print(json.dumps({"status":"READY_FOR_CANONICAL_FREEZE","phase":args.phase,"records":len(draft),"output":str(args.output)},ensure_ascii=False))

if __name__=="__main__":
    main()
