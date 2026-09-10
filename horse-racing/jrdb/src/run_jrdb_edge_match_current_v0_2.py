#!/usr/bin/env python3
"""One-command v0.2 current runner: PACI -> enriched facts -> Edge matches."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_jrdb_edge_current_facts_v0_2 import build_current_facts
import jrdb_edge_matcher_v0_2 as matcher

VERSION = "0.2.1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paci", required=True)
    parser.add_argument("--analysis-db")
    parser.add_argument("--registry-jsonl", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--facts-jsonl")
    parser.add_argument("--audit-json")
    parser.add_argument(
        "--serving-profile",
        default=matcher.PROFILE_CONFIRMED_ONLY,
        choices=matcher.SERVING_PROFILES,
    )
    parser.add_argument(
        "--statuses",
        help="Optional compatibility/status filter. STANDARD normally leaves this unset.",
    )
    parser.add_argument("--only-matched", action="store_true")
    args = parser.parse_args()

    statuses = None
    if args.statuses:
        statuses = tuple(
            value.strip().upper()
            for value in args.statuses.split(",")
            if value.strip()
        )
        allowed_statuses = set(matcher.base.STATUS_RANK) | {"REJECTED"}
        bad = sorted(set(statuses) - allowed_statuses)
        if not statuses or bad:
            raise ValueError(f"unsupported status(es): {bad}")

    facts, audit = build_current_facts(args.paci, args.analysis_db)
    registry = matcher.load_registry(args.registry_jsonl)
    output = []
    for runner in facts:
        matches = matcher.match_runner(
            registry,
            runner,
            profile=args.serving_profile,
            statuses=statuses,
        )
        if args.only_matched and not matches:
            continue
        key = {
            field: runner.get(field)
            for field in matcher.base.IDENTITY_FIELDS
            if field in runner
        }
        output.append({"key": key, "edge_matches": matches})

    with Path(args.output_jsonl).open("w", encoding="utf-8", newline="\n") as handle:
        for row in output:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    if args.facts_jsonl:
        with Path(args.facts_jsonl).open("w", encoding="utf-8", newline="\n") as handle:
            for row in facts:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    if args.audit_json:
        audit = dict(audit)
        audit["serving_profile"] = args.serving_profile
        audit["status_filter"] = list(statuses) if statuses is not None else None
        Path(args.audit_json).write_text(
            json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "status": "PASS",
                "version": VERSION,
                "serving_profile": args.serving_profile,
                "runner_rows": len(facts),
                "matched_runners": sum(bool(row["edge_matches"]) for row in output),
                "matches": sum(len(row["edge_matches"]) for row in output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
