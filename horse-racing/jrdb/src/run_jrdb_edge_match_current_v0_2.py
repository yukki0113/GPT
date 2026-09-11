#!/usr/bin/env python3
"""One-command v0.2 current runner: PACI -> enriched facts -> Edge matches."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from build_jrdb_edge_current_facts_v0_2 import build_current_facts
import jrdb_edge_matcher_v0_2 as matcher

VERSION = "0.2.3"
DEFAULT_SERVING_PROFILE = matcher.PROFILE_STANDARD


def parse_statuses(raw: str | None) -> tuple[str, ...] | None:
    """Parse the optional legacy status filter used by compatibility callers."""
    if raw is None or not raw.strip():
        return None
    statuses = tuple(
        value.strip().upper()
        for value in raw.split(",")
        if value.strip()
    )
    allowed_statuses = set(matcher.base.STATUS_RANK) | {"REJECTED"}
    bad = sorted(set(statuses) - allowed_statuses)
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
    audit_json: str | Path | None = None,
    serving_profile: str = DEFAULT_SERVING_PROFILE,
    statuses: Sequence[str] | None = None,
    only_matched: bool = False,
) -> dict[str, object]:
    """Run v0.2 matching with an explicit serving profile and optional status filter."""
    if serving_profile not in matcher.SERVING_PROFILES:
        raise ValueError(f"unsupported serving profile: {serving_profile}")

    normalized_statuses: tuple[str, ...] | None = None
    if statuses is not None:
        normalized_statuses = tuple(str(value).strip().upper() for value in statuses if str(value).strip())
        allowed_statuses = set(matcher.base.STATUS_RANK) | {"REJECTED"}
        bad = sorted(set(normalized_statuses) - allowed_statuses)
        if not normalized_statuses or bad:
            raise ValueError(f"unsupported status(es): {bad}")

    facts, audit = build_current_facts(paci_path, analysis_db)
    registry = matcher.load_registry(registry_jsonl)
    output: list[dict[str, object]] = []

    # Match each runner using the selected v0.2 serving contract.
    for runner in facts:
        matches = matcher.match_runner(
            registry,
            runner,
            profile=serving_profile,
            statuses=normalized_statuses,
        )
        if only_matched and not matches:
            continue
        key = {
            field: runner.get(field)
            for field in matcher.base.IDENTITY_FIELDS
            if field in runner
        }
        output.append({"key": key, "edge_matches": matches})

    output_path = Path(output_jsonl)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in output:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    if facts_jsonl is not None:
        facts_path = Path(facts_jsonl)
        with facts_path.open("w", encoding="utf-8", newline="\n") as handle:
            for row in facts:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    if audit_json is not None:
        audit_payload = dict(audit)
        audit_payload["serving_profile"] = serving_profile
        audit_payload["status_filter"] = list(normalized_statuses) if normalized_statuses is not None else None
        Path(audit_json).write_text(
            json.dumps(audit_payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return {
        "status": "PASS",
        "version": VERSION,
        "serving_profile": serving_profile,
        "status_filter": list(normalized_statuses) if normalized_statuses is not None else None,
        "runner_rows": len(facts),
        "output_rows": len(output),
        "matched_runners": sum(bool(row["edge_matches"]) for row in output),
        "matches": sum(len(row["edge_matches"]) for row in output),
    }


def main() -> int:
    """CLI entry point for the operational v0.2 current matcher."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--paci", required=True)
    parser.add_argument("--analysis-db")
    parser.add_argument("--registry-jsonl", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--facts-jsonl")
    parser.add_argument("--audit-json")
    parser.add_argument(
        "--serving-profile",
        default=DEFAULT_SERVING_PROFILE,
        choices=matcher.SERVING_PROFILES,
        help="v0.2 serving profile. Default: STANDARD; use CONFIRMED_ONLY for strict ACTIVE-only evidence.",
    )
    parser.add_argument(
        "--statuses",
        help="Optional compatibility/status filter. STANDARD normally leaves this unset.",
    )
    parser.add_argument("--only-matched", action="store_true")
    args = parser.parse_args()

    summary = run(
        paci_path=args.paci,
        analysis_db=args.analysis_db,
        registry_jsonl=args.registry_jsonl,
        output_jsonl=args.output_jsonl,
        facts_jsonl=args.facts_jsonl,
        audit_json=args.audit_json,
        serving_profile=args.serving_profile,
        statuses=parse_statuses(args.statuses),
        only_matched=args.only_matched,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
