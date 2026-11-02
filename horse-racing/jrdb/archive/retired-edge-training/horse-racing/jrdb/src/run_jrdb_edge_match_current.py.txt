#!/usr/bin/env python3
"""Run the reusable JRDB Edge pipeline for current PACI runners in one command."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import build_jrdb_edge_current_facts as current_facts
import jrdb_edge_matcher as matcher

VERSION = "0.1.0"


def parse_statuses(value: str) -> tuple[str, ...]:
    statuses = tuple(part.strip().upper() for part in value.split(",") if part.strip())
    bad = sorted(set(statuses) - set(matcher.STATUS_RANK))
    if not statuses or bad:
        raise ValueError(f"unsupported status(es): {bad}")
    return statuses


def run(
    *,
    paci_path: str | Path,
    registry_jsonl: str | Path,
    output_jsonl: str | Path,
    analysis_db: str | Path | None = None,
    facts_jsonl: str | Path | None = None,
    statuses: Sequence[str] = matcher.DEFAULT_STATUSES,
    only_matched: bool = False,
) -> dict[str, Any]:
    """Build current facts, match reusable Edges, and write consumer-neutral JSONL."""
    normalized_statuses = tuple(str(value).strip().upper() for value in statuses if str(value).strip())
    bad = sorted(set(normalized_statuses) - set(matcher.STATUS_RANK))
    if not normalized_statuses or bad:
        raise ValueError(f"unsupported status(es): {bad}")

    runners, fact_summary = current_facts.build_current_facts(paci_path, analysis_db)
    registry = matcher.load_registry(registry_jsonl)

    if facts_jsonl is not None:
        facts_path = Path(facts_jsonl)
        facts_path.parent.mkdir(parents=True, exist_ok=True)
        with facts_path.open("w", encoding="utf-8", newline="\n") as handle:
            for runner in runners:
                handle.write(json.dumps(runner, ensure_ascii=False, sort_keys=True) + "\n")

    output_rows: list[dict[str, Any]] = []
    total_matches = 0
    matched_runners = 0
    for runner in runners:
        matches = matcher.match_runner(registry, runner, statuses=normalized_statuses)
        if matches:
            matched_runners += 1
            total_matches += len(matches)
        if only_matched and not matches:
            continue
        key = {
            field: runner.get(field)
            for field in matcher.IDENTITY_FIELDS
            if field in runner
        }
        output_rows.append({"key": key, "edge_matches": matches})

    output_path = Path(output_jsonl)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in output_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    registry_versions = sorted(
        {
            str(edge.get("registry_version"))
            for edge in registry
            if edge.get("registry_version") not in (None, "")
        }
    )
    return {
        "status": "PASS",
        "runner_version": VERSION,
        "current_facts_version": current_facts.VERSION,
        "matcher_version": matcher.VERSION,
        "statuses": list(normalized_statuses),
        "registry_edges": len(registry),
        "registry_versions": registry_versions,
        "runner_rows": len(runners),
        "output_rows": len(output_rows),
        "matched_runners": matched_runners,
        "matches": total_matches,
        "current_facts": fact_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paci", required=True)
    parser.add_argument("--analysis-db")
    parser.add_argument("--registry-jsonl", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--facts-jsonl")
    parser.add_argument("--statuses", default="ACTIVE")
    parser.add_argument("--only-matched", action="store_true")
    args = parser.parse_args()

    summary = run(
        paci_path=args.paci,
        analysis_db=args.analysis_db,
        registry_jsonl=args.registry_jsonl,
        output_jsonl=args.output_jsonl,
        facts_jsonl=args.facts_jsonl,
        statuses=parse_statuses(args.statuses),
        only_matched=args.only_matched,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
