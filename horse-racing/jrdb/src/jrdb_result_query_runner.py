#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Operational runner for JRDB completed-race result queries.

This module intentionally does not access Google Drive or the Web itself.
The GPT/Work layer must materialize the exact Drive Raw files requested by
build_materialization_plan(), then invoke this runner against that local cache.

Reason: repository source and Raw are deliberately separated.  "Raw is not in
repo" is expected and must never be treated as a reason to search the Web.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from jrdb_result_query import ResultQueryError, parse_date, query_results

VERSION = "0.1.0"
PLAN_SCHEMA = "jrdb-result-query-materialization-plan-v0.1"
DEFAULT_DRIVE_ROOT = "/Google Drive/GPT/horse-racing/00_raw"


def source_archive_names(date: dt.date) -> dict[str, str]:
    """Return canonical Drive archive names for a completed-race query."""
    if date.year <= 2025:
        return {
            "SED": f"SED_{date.year}.zip",
            "HJC": f"HJC_{date.year}.zip",
        }
    return {
        "SED": f"SED{date:%y%m%d}.zip",
        "HJC": f"HJC{date:%y%m%d}.zip",
    }


def build_materialization_plan(
    date: str | dt.date,
    *,
    drive_root: str = DEFAULT_DRIVE_ROOT,
    local_root: Path = Path("/mnt/data/jrdb_result_query"),
) -> dict[str, Any]:
    """Describe exactly which Drive files GPT/Work must materialize."""
    target = date if isinstance(date, dt.date) else parse_date(date)
    names = source_archive_names(target)
    day_dir = local_root / target.strftime("%Y%m%d")
    files = []
    for family in ("SED", "HJC"):
        name = names[family]
        files.append(
            {
                "family": family,
                "name": name,
                "drive_path": f"{drive_root}/{family}/{name}",
                "local_path": str(day_dir / name),
                "required": True,
            }
        )
    return {
        "schema_version": PLAN_SCHEMA,
        "date": target.isoformat(),
        "coverage": "annual_raw" if target.year <= 2025 else "daily_raw",
        "files": files,
        "web_fallback_allowed_before_drive_check": False,
        "note": (
            "Raw is intentionally not stored in Git. Materialize these Drive files "
            "with the native Google Drive connector before executing the query."
        ),
    }


def _plan_paths(plan: dict[str, Any]) -> tuple[Path, Path]:
    by_family = {row["family"]: Path(row["local_path"]) for row in plan["files"]}
    return by_family["SED"], by_family["HJC"]


def execute_materialized(
    *,
    date: str | dt.date,
    venue: str | None = None,
    race_no: int | None = None,
    bet_types: Sequence[str] | None = None,
    include_all_runners: bool = False,
    local_root: Path = Path("/mnt/data/jrdb_result_query"),
) -> dict[str, Any]:
    """Run Result Query against files already materialized by GPT/Work."""
    target = date if isinstance(date, dt.date) else parse_date(date)
    plan = build_materialization_plan(target, local_root=local_root)
    sed_path, hjc_path = _plan_paths(plan)

    missing = [str(p) for p in (sed_path, hjc_path) if not p.is_file()]
    if missing:
        raise ResultQueryError(
            "required Drive Raw has not been materialized into the runtime: "
            + ", ".join(missing)
            + ". Do not use Web as a substitute; materialize the plan first."
        )

    result = query_results(
        date=target,
        venue=venue,
        race_no=race_no,
        bet_types=bet_types,
        include_all_runners=include_all_runners,
        source="raw",
        sed=sed_path,
        hjc=hjc_path,
    )
    result["materialization"] = {
        "mode": "native_drive_connector",
        "local_root": str(local_root),
        "plan_schema_version": PLAN_SCHEMA,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="JRDB operational result query runner for GPT/Work materialized Drive Raw"
    )
    parser.add_argument("--date", required=True)
    parser.add_argument("--venue")
    parser.add_argument("--race", dest="race_no", type=int)
    parser.add_argument("--bet-type", dest="bet_types", action="append")
    parser.add_argument("--include-all-runners", action="store_true")
    parser.add_argument("--local-root", type=Path, default=Path("/mnt/data/jrdb_result_query"))
    parser.add_argument(
        "--plan",
        action="store_true",
        help="print native-Drive materialization plan and do not execute query",
    )
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args()

    try:
        if args.plan:
            payload = build_materialization_plan(args.date, local_root=args.local_root)
            rc = 0
        else:
            payload = execute_materialized(
                date=args.date,
                venue=args.venue,
                race_no=args.race_no,
                bet_types=args.bet_types,
                include_all_runners=args.include_all_runners,
                local_root=args.local_root,
            )
            rc = 3 if payload.get("status") == "partial" else (
                4 if payload.get("status") == "review_required" else 0
            )

        text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
        sys.stdout.write(text)
        return rc
    except (ResultQueryError, FileNotFoundError) as exc:
        print(
            json.dumps(
                {
                    "schema_version": PLAN_SCHEMA,
                    "status": "error",
                    "error": str(exc),
                    "web_fallback_allowed": False,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
