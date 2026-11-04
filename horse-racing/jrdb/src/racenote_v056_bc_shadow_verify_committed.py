#!/usr/bin/env python3
"""Audit immutable committed RaceNote B/C shadow against revalidated output, no results."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from racenote_v056_bc_shadow import validate

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--draft", type=Path, required=True)
    p.add_argument("--committed", type=Path, required=True)
    p.add_argument("--assert-results-unopened", action="store_true", required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args=p.parse_args()
    payload=validate(args.root,args.draft,asserted_unopened=args.assert_results_unopened)
    expected=(json.dumps(payload,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")
    actual=args.committed.read_bytes()
    if actual!=expected:
        raise ValueError(f"COMMITTED_SHADOW_DIFFERS from validated sealed draft: {args.committed}")
    if json.loads(actual).get("status")!="SHADOW_BC_DRAFT_VALIDATED_NOT_CANONICAL_FREEZE":
        raise ValueError("Shadow source is not the expected research-only status")
    output={"status":"PASS","btday":payload["selection_id"],"session_id":payload["session_id"],
            "record_count":payload["record_count"],"grade_transitions":payload["grade_transitions"],
            "committed_sha256":hashlib.sha256(actual).hexdigest(),
            "prediction_records_sha256":payload["prediction_records_sha256"],
            "confidence_records_sha256":payload["confidence_records_sha256"],
            "result_query_used":False,"payout_query_used":False}
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/"committed_verify.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(output,ensure_ascii=False))
if __name__=="__main__":
    main()
