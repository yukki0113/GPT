#!/usr/bin/env python3
"""One-command v0.2 current runner: PACI -> enriched facts -> Edge matches."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_jrdb_edge_current_facts_v0_2 import build_current_facts
import jrdb_edge_matcher_v0_2 as matcher

VERSION = "0.2.0"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--paci", required=True)
    p.add_argument("--analysis-db")
    p.add_argument("--registry-jsonl", required=True)
    p.add_argument("--output-jsonl", required=True)
    p.add_argument("--facts-jsonl")
    p.add_argument("--audit-json")
    p.add_argument("--statuses", default="ACTIVE")
    p.add_argument("--only-matched", action="store_true")
    args = p.parse_args()

    statuses = tuple(x.strip().upper() for x in args.statuses.split(",") if x.strip())
    bad = sorted(set(statuses) - set(matcher.base.STATUS_RANK))
    if not statuses or bad:
        raise ValueError(f"unsupported status(es): {bad}")

    facts, audit = build_current_facts(args.paci, args.analysis_db)
    registry = matcher.load_registry(args.registry_jsonl)
    output = []
    for runner in facts:
        matches = matcher.match_runner(registry, runner, statuses=statuses)
        if args.only_matched and not matches:
            continue
        key = {f: runner.get(f) for f in matcher.base.IDENTITY_FIELDS if f in runner}
        output.append({"key": key, "edge_matches": matches})

    with Path(args.output_jsonl).open("w", encoding="utf-8", newline="\n") as fh:
        for row in output:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    if args.facts_jsonl:
        with Path(args.facts_jsonl).open("w", encoding="utf-8", newline="\n") as fh:
            for row in facts:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    if args.audit_json:
        Path(args.audit_json).write_text(
            json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )

    print(json.dumps({
        "status":"PASS", "version":VERSION, "runner_rows":len(facts),
        "matched_runners":sum(bool(r["edge_matches"]) for r in output),
        "matches":sum(len(r["edge_matches"]) for r in output),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
