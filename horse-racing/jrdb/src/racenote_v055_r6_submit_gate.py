#!/usr/bin/env python3
"""Fail-closed handoff descriptor for canonical r6 Freeze input.

This utility never authors decisions, commits, or triggers freezes. It checks
that the locally assembled payload is ready to be committed as ONE file on main.
"""
import argparse
import hashlib
import json
from pathlib import Path
from racenote_v055_r6_turn2_checkpoint import inspect
from racenote_v055_turn2_two_phase import resolve_root, preflight

FILES={"prediction":"llm_decisions.json","confidence":"llm_confidence.json"}
ACTIONS={"prediction":"LLM_PREDICTION_AUTHORING","confidence":"LLM_CONFIDENCE_REVIEW"}

def build(root, phase, draft):
    state=inspect(root)
    if state["next_action"] != ACTIONS[phase]:
        raise ValueError(f"Wrong phase or existing submitted/frozen state: {state['next_action']}")
    if not draft.is_file() or draft.is_symlink():
        raise ValueError("Draft must be a regular file")
    session,data=preflight(root,draft,phase)
    raw=draft.read_bytes()
    return {
      "status":"READY_TO_SUBMIT",
      "phase":phase,
      "selection_id":session["selection_id"],
      "session_id":session["session_id"],
      "race_count":len(data),
      "draft_sha256":hashlib.sha256(raw).hexdigest(),
      "target_path":str(root/"incoming"/FILES[phase]),
      "expected_workflow":f"racenote_v055_llm_{phase}_freeze.yml",
      "source_state":state["state"],
      "rule":"Commit ONLY target_path to main; verify persisted Freeze before next phase",
      "result_opened":False,"target_market_opened":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--phase",choices=tuple(FILES),required=True)
    p.add_argument("--draft",type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(build(resolve_root(args.root),args.phase,args.draft),ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    main()
