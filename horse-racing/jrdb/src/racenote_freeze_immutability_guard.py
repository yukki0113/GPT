#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guard canonical RaceNote Freeze against semantic overwrite."""
from __future__ import annotations
import argparse,json
from pathlib import Path

VERSION='racenote-freeze-immutability-guard-0.1.0'

def load(path:Path):
    return json.loads(path.read_text(encoding='utf-8'))

def hashes(x):
    v=x.get('prediction_hashes')
    if not isinstance(v,list) or not v:
        raise ValueError('prediction_hashes missing')
    return list(map(str,v))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--candidate-handoff',type=Path,required=True)
    ap.add_argument('--canonical-handoff',type=Path,required=True)
    ap.add_argument('--output',type=Path)
    a=ap.parse_args()
    candidate=load(a.candidate_handoff)
    if not a.canonical_handoff.exists():
        out={'version':VERSION,'status':'NEW_FREEZE','publish_allowed':True}
        rc=0
    else:
        canonical=load(a.canonical_handoff)
        same_identity=(candidate.get('selection_id'),candidate.get('target_date'))==(canonical.get('selection_id'),canonical.get('target_date'))
        same_hashes=hashes(candidate)==hashes(canonical)
        if same_identity and same_hashes:
            out={'version':VERSION,'status':'IDENTICAL_RETRY','publish_allowed':False,'semantic_prediction_unchanged':True}
            rc=0
        else:
            out={'version':VERSION,'status':'CONFLICTING_FREEZE','publish_allowed':False,'semantic_prediction_unchanged':False}
            rc=3
    text=json.dumps(out,ensure_ascii=False,indent=2)+'\n'
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(text,encoding='utf-8')
    print(text,end='')
    return rc

if __name__=='__main__':
    raise SystemExit(main())
