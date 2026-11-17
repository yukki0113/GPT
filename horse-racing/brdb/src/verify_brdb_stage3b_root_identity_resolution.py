#!/usr/bin/env python3
"""Verify committed Stage3B root decisions are byte-identical to resolver output."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from brdb_stage3b_root_identity_resolution import resolve

EXPECTED_SHA="41af186f3d48e5357c835ace0fb0507fd9ec33a05c2747e82c3fcac984980740"

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def main():
 p=argparse.ArgumentParser()
 for n in ("fixed-audit","old-decisions","evidence","aliases","seed","committed"):
  p.add_argument("--"+n,type=Path,required=True)
 a=p.parse_args()
 load=lambda p:json.loads(p.read_text(encoding="utf-8"))
 out=resolve(load(a.fixed_audit),load(a.old_decisions),load(a.evidence),load(a.aliases),load(a.seed))
 generated=(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
 committed=a.committed.read_bytes()
 if generated!=committed: raise SystemExit("committed v0.2 differs from canonical resolver output")
 if sha(committed)!=EXPECTED_SHA: raise SystemExit("committed v0.2 SHA drift")
 print(json.dumps({"status":"PASS","approved_total":out["approved_total"],"newly_resolved":out["newly_resolved"],"sha256":EXPECTED_SHA},sort_keys=True))
if __name__=="__main__":main()
