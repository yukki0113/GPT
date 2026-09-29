#!/usr/bin/env python3
"""Day-level RaceNote production orchestrator.

D1 freezes the public CLI, stage model and manifest contract only.
Production execution remains fail-closed until D2-D4 are implemented.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

PIPELINE_VERSION = "RaceNote-Daily-Build-0.1"
MANIFEST_SCHEMA_VERSION = "RaceNote-Daily-Build-Manifest-0.1"
STAGE_NAMES = ("base", "history", "rrdb", "reader", "validation", "package")


class DailyBuildNotImplementedError(RuntimeError):
    """Raised while the D1 skeleton has no production execution path."""


def iso_date(value: str) -> str:
    """Normalize YYYY-MM-DD / YYYYMMDD into ISO date."""
    text = value.strip()
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "target date must be YYYY-MM-DD or YYYYMMDD"
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build one day's RaceNote packages through base -> history/P1/P2 "
            "-> RRDB -> Reader View -> validation -> package."
        )
    )
    parser.add_argument("--date", required=True, type=iso_date, dest="target_date")
    parser.add_argument("--paci", required=True, type=Path)
    parser.add_argument("--analysis-root", required=True, type=Path)
    rrdb_source = parser.add_mutually_exclusive_group(required=True)
    rrdb_source.add_argument("--racereview-root", type=Path)
    rrdb_source.add_argument("--racereview-current-cache", type=Path)
    parser.add_argument("--next-watch-rules", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--keep-intermediate",
        action="store_true",
        help="D2+ debug option; intermediates are never canonical outputs.",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Print the D1 execution plan without building RaceNote.",
    )
    return parser.parse_args()


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    rrdb_source: dict[str, str]
    if args.racereview_root is not None:
        rrdb_source = {
            "mode": "generation_root",
            "path": str(args.racereview_root),
        }
    else:
        rrdb_source = {
            "mode": "current_cache",
            "path": str(args.racereview_current_cache),
        }
    output_root = args.output / f"RaceNote_{args.target_date.replace('-', '')}"
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "target_date": args.target_date,
        "status": "PLANNED",
        "pipeline_version": PIPELINE_VERSION,
        "stages": {name: "PLANNED" for name in STAGE_NAMES},
        "sources": {
            "paci": {"path": str(args.paci)},
            "analysis": {"root": str(args.analysis_root), "backend": "parquet"},
            "rrdb": rrdb_source,
            "next_watch": {"path": str(args.next_watch_rules)},
        },
        "counts": {
            "races_expected": None,
            "races_built": 0,
            "reader_views": 0,
            "horses": 0,
            "technical_skips": 0,
        },
        "firewall": {
            "target_result_exposed": None,
            "market_exposed": None,
            "analysis_as_of_violations": None,
            "rrdb_as_of_violations": None,
        },
        "validation": {
            "base": "PLANNED",
            "history": "PLANNED",
            "pedigree": "PLANNED",
            "rrdb": "PLANNED",
            "reader_roundtrip": "PLANNED",
        },
        "artifacts": {
            "authoritative_dir": str(output_root / "authoritative"),
            "reader_dir": str(output_root / "reader"),
            "manifest": str(output_root / "manifest.json"),
            "validation_report": str(output_root / "validation_report.json"),
        },
        "warnings": [
            "D1 skeleton only: production execution is not implemented."
        ],
        "errors": [],
    }


def run(args: argparse.Namespace) -> int:
    if args.plan:
        print(json.dumps(build_plan(args), ensure_ascii=False, indent=2))
        return 0
    raise DailyBuildNotImplementedError(
        "RaceNote daily build production execution is not implemented in D1. "
        "Use --plan to inspect the frozen contract; D2 will connect BASE/HISTORY."
    )


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except DailyBuildNotImplementedError as exc:
        print(json.dumps({
            "status": "NOT_IMPLEMENTED",
            "pipeline_version": PIPELINE_VERSION,
            "error": str(exc),
        }, ensure_ascii=False))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
