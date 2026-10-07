#!/usr/bin/env python3
"""Prepare one RaceNote v0.5.2 forecast day directly from one PACI ZIP.

Common entrypoint for historical BTDAY and normal forward daily operation:
PACI -> daily RaceNote -> market-blind forecast_prep -> v0.5.2 single-day session.
No A/B session or barrier is created.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from build_racenote_daily import DailyBuildError, build_daily_package
from racenote_prepare_forecast_input import bind
from racenote_v052_single_day import init_session

VERSION = "racenote-v052-from-paci-0.1"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", required=True)
    ap.add_argument("--paci", type=Path, required=True)
    ap.add_argument("--selection-id", required=True,
                    help="BTDAY-XXXX for backtest or DAILY-YYYYMMDD for forward operation")
    ap.add_argument("--main-sha", required=True)
    ap.add_argument("--analysis-root", type=Path, required=True)
    rrdb = ap.add_mutually_exclusive_group(required=True)
    rrdb.add_argument("--racereview-root", type=Path)
    rrdb.add_argument("--racereview-current-cache", type=Path)
    ap.add_argument("--next-watch-rules", type=Path)
    ap.add_argument("--output-root", type=Path, required=True)
    args = ap.parse_args()

    if not args.paci.is_file():
        raise FileNotFoundError(args.paci)
    if args.output_root.exists():
        raise FileExistsError(f"output root already exists: {args.output_root}")
    if len(args.main_sha) != 40 or any(c not in "0123456789abcdef" for c in args.main_sha):
        raise ValueError("--main-sha must be a full lowercase commit SHA")

    args.output_root.mkdir(parents=True)
    day_build_parent = args.output_root / "day_prep"
    with tempfile.TemporaryDirectory(prefix="racenote-v052-rrdb-") as tmp:
        manifest, report, _ = build_daily_package(
            paci_path=args.paci,
            target_date=args.date,
            analysis_root=args.analysis_root,
            racereview_root=args.racereview_root,
            racereview_current_cache=args.racereview_current_cache,
            next_watch_rules=args.next_watch_rules,
            output_root=day_build_parent,
            rrdb_work_root=Path(tmp),
        )
    if report.get("status") != "PASS":
        raise DailyBuildError("daily package did not PASS")

    daily_root = day_build_parent / f"RaceNote_{args.date.replace('-', '')}"
    forecast_prep = args.output_root / "forecast_prep"
    handoff = bind(
        daily_root,
        forecast_prep,
        args.selection_id,
        args.date,
        args.main_sha,
    )
    v052_root = args.output_root / "v052"
    session = init_session(forecast_prep, v052_root, args.main_sha)

    operation = {
        "schema_version": VERSION,
        "status": "READY_FOR_V052_AUTHORING",
        "selection_id": args.selection_id,
        "target_date": args.date,
        "logic_version": session["logic_version"],
        "session_id": session["session_id"],
        "paci": {
            "filename": args.paci.name,
            "sha256": sha256(args.paci),
        },
        "daily_manifest_status": manifest.get("status"),
        "forecast_prep": str(forecast_prep),
        "v052_root": str(v052_root),
        "race_count": len(session["race_roster"]),
        "expected_venues": session["expected_venues"],
        "market_blind": handoff.get("market_blind"),
        "result_opened": False,
        "ab_required": False,
    }
    (args.output_root / "operation_handoff.json").write_text(
        json.dumps(operation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(operation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
