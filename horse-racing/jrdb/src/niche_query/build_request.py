#!/usr/bin/env python3
"""Wrap the canonical Data Storage dynamic Drive request builder for Analysis-only niche queries.

Connector observation file must contain before candidates, metadata_after and local bytes.
This script never contacts Drive or GitHub; no per-query Git commit is required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools" / "data-storage" / "scripts"))
from build_dynamic_drive_request import build_request  # noqa: E402; canonical transport validation
from compile_query import validate_spec  # noqa: E402


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",required=True,type=Path)
    p.add_argument("--spec-file",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--date",required=True,help="Request date YYYY-MM-DD; not race date")
    args=p.parse_args()
    spec=json.loads(args.spec_file.read_text(encoding="utf-8"));validate_spec(spec)
    all_sources=json.loads((ROOT/"tools/data-storage/config/drive_source_registry.json").read_text(encoding="utf-8"))
    sources=[s for s in all_sources["sources"] if s["key"]=="jrdb.analysis.current"]
    if len(sources)!=1:raise ValueError("Missing/duplicate canonical Analysis registry")
    registry={"schema_version":1,"sources":sources}
    template=json.loads((ROOT/"horse-racing/jrdb/config/niche_query/actions_template_v1.json").read_text(encoding="utf-8"))
    normalized=json.dumps(spec,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    for step in template["steps"]:
        step["args"]=[normalized if arg=="__QUERY_SPEC_JSON__" else arg for arg in step["args"]]
    # Runner audits reference/fingerprints; no user SQL is emitted.
    digest=hashlib.sha256(normalized.encode()).hexdigest()[:12]
    template["request_id"]=f"jrdb-niche-{args.date.replace('-','')}-{digest}"
    obs=json.loads(args.snapshot.read_text(encoding="utf-8"))
    request=build_request(registry,obs,template,args.date)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(request,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","request_id":request["request_id"],"output":str(args.output)},ensure_ascii=False))

if __name__=="__main__":main()