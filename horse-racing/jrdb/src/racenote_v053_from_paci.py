#!/usr/bin/env python3
"""Prepare one RaceNote v0.5.3 forecast day directly from one PACI ZIP.

Common entrypoint for historical BTDAY and normal forward daily operation:
PACI -> daily RaceNote -> market-blind forecast_prep -> v0.5.3 single-day session.
No A/B session or barrier is created.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from build_racenote_daily import DailyBuildError, build_daily_package
from jrdb_race_lap_current_resolver import resolve_current
from racenote_prepare_forecast_input import bind
from racenote_v053_single_day import init_session

VERSION = "racenote-v053-from-paci-0.1"


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
    ap.add_argument("--course-fit-root", type=Path, required=True)
    race_lap = ap.add_mutually_exclusive_group(required=True)
    race_lap.add_argument("--race-lap-parquet", type=Path)
    race_lap.add_argument("--race-lap-current-bundle", type=Path)
    ap.add_argument("--analysis-period-to")
    ap.add_argument("--race-lap-sed", type=Path, action="append")
    ap.add_argument("--race-lap-expected-date", action="append")
    ap.add_argument("--race-lap-work-root", type=Path)
    ap.add_argument("--race-lap-generation-id")
    ap.add_argument("--race-lap-resolved-bundle", type=Path)
    rrdb = ap.add_mutually_exclusive_group(required=True)
    rrdb.add_argument("--racereview-root", type=Path)
    rrdb.add_argument("--racereview-current-cache", type=Path)
    ap.add_argument("--next-watch-rules", type=Path)
    ap.add_argument("--output-root", type=Path, required=True)
    ap.add_argument("--prep-only", action="store_true", help="Build DAY PREP + forecast_prep only; do not initialize legacy v0.5.3 session")
    args = ap.parse_args()

    if not args.paci.is_file():
        raise FileNotFoundError(args.paci)
    race_lap_parquet = args.race_lap_parquet
    race_lap_resolution = None
    if args.race_lap_current_bundle is not None:
        if not args.analysis_period_to:
            raise ValueError("--analysis-period-to is required with --race-lap-current-bundle")
        race_lap_resolution = resolve_current(
            args.race_lap_current_bundle,
            args.date,
            args.analysis_period_to,
            sed_archives=args.race_lap_sed,
            expected_dates=args.race_lap_expected_date,
            work_root=args.race_lap_work_root,
            generation_id=args.race_lap_generation_id,
            resolved_bundle=args.race_lap_resolved_bundle,
        )
        race_lap_parquet = Path(race_lap_resolution["parquet"])
    if race_lap_parquet is None or not race_lap_parquet.is_file():
        raise FileNotFoundError(race_lap_parquet)
    if args.output_root.exists():
        raise FileExistsError(f"output root already exists: {args.output_root}")
    if len(args.main_sha) != 40 or any(c not in "0123456789abcdef" for c in args.main_sha):
        raise ValueError("--main-sha must be a full lowercase commit SHA")

    args.output_root.mkdir(parents=True)
    day_build_parent = args.output_root / "day_prep"
    with tempfile.TemporaryDirectory(prefix="racenote-v053-rrdb-") as tmp:
        manifest, report, _ = build_daily_package(
            paci_path=args.paci,
            target_date=args.date,
            analysis_root=args.analysis_root,
            course_fit_root=args.course_fit_root,
            race_lap_parquet=race_lap_parquet,
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
    v053_root = args.output_root / "v053"
    session = None if args.prep_only else init_session(forecast_prep, v053_root, args.main_sha)

    operation = {
        "schema_version": VERSION,
        "status": "FORECAST_PREP_READY" if args.prep_only else "READY_FOR_V053_AUTHORING",
        "selection_id": args.selection_id,
        "target_date": args.date,
        "logic_version": None if session is None else session["logic_version"],
        "contract_revision": None if session is None else session.get("contract_revision"),
        "session_id": None if session is None else session["session_id"],
        "paci": {
            "filename": args.paci.name,
            "sha256": sha256(args.paci),
        },
        "daily_manifest_status": manifest.get("status"),
        "race_lap_resolution": race_lap_resolution,
        "forecast_prep": str(forecast_prep),
        "v053_root": None if session is None else str(v053_root),
        "race_count": len(handoff["race_roster"]),
        "expected_venues": sorted({row["venue"] for row in handoff["race_roster"]}),
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
