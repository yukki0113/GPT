#!/usr/bin/env python3
"""Canonical mechanical T1 wrapper for RaceNote v0.5.6 forward days.

Prediction remains outside this module. The wrapper only:
1) invokes the existing PACI -> market-blind forecast_prep entrypoint;
2) builds the allowlisted KYI evidence bundle;
3) seals v0.5.6 Reader;
4) creates lossless venue authoring bundles;
5) writes a T1 handoff.

Analysis/RRDB are consumed as supplied currents. Their freshness is not checked.
RaceLap freshness is checked by the existing RaceLap resolver.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from racenote_v054_kyi_bundle import build_bundle
from racenote_v056_authoring_bundle import build as build_authoring_bundle
from racenote_v056_single_day import init_session, write_json


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", required=True)
    ap.add_argument("--paci", type=Path, required=True)
    ap.add_argument("--main-sha", required=True)
    ap.add_argument("--analysis-root", type=Path, required=True)
    ap.add_argument("--course-fit-root", type=Path, required=True)
    ap.add_argument("--racereview-root", type=Path, required=True)
    ap.add_argument("--race-lap-current-bundle", type=Path, required=True)
    ap.add_argument("--race-lap-expected-period-to", required=True)
    ap.add_argument("--output-root", type=Path, required=True)
    ap.add_argument("--selection-id")
    args = ap.parse_args()

    import datetime as dt
    target_date = dt.date.fromisoformat(args.date)
    if target_date.isoformat() != args.date:
        raise ValueError("date must be YYYY-MM-DD")
    canonical = Path("horse-racing/jrdb/daily") / args.date.replace("-", "") / "v056_day"
    if args.output_root != canonical:
        raise ValueError(f"v056 forward T1 must use canonical root: {canonical}")
    if args.output_root.exists():
        raise FileExistsError(f"output root already exists: {args.output_root}")
    selection_id = args.selection_id or f"DAILY-{args.date.replace('-', '')}"

    src = Path(__file__).resolve().parent
    prep_cmd = [
        sys.executable, str(src / "racenote_v053_from_paci.py"),
        "--date", args.date,
        "--paci", str(args.paci),
        "--selection-id", selection_id,
        "--main-sha", args.main_sha,
        "--analysis-root", str(args.analysis_root),
        "--course-fit-root", str(args.course_fit_root),
        "--race-lap-current-bundle", str(args.race_lap_current_bundle),
        "--race-lap-expected-period-to", args.race_lap_expected_period_to,
        "--racereview-root", str(args.racereview_root),
        "--output-root", str(args.output_root),
        "--prep-only",
    ]
    subprocess.run(prep_cmd, check=True)

    daily = args.output_root / "day_prep" / f"RaceNote_{args.date.replace('-', '')}"
    for name in ("manifest.json", "validation_report.json"):
        source = daily / name
        if source.is_file():
            shutil.copy2(source, args.output_root / "day_prep" / name)

    evidence_path = args.output_root / "v054_inputs" / "kyi_bundle.json"
    bundle = build_bundle(args.output_root / "forecast_prep", [args.paci])
    if bundle["coverage"]["kyi_missing_count"] != 0:
        raise ValueError("KYI coverage incomplete")
    write_json(evidence_path, bundle)

    race_lap_parquet = args.race_lap_current_bundle / "race_lap.parquet"
    session = init_session(
        args.output_root / "forecast_prep",
        args.output_root / "v056",
        args.main_sha,
        evidence_bundle=evidence_path,
        race_lap_parquet=race_lap_parquet,
    )
    authoring = build_authoring_bundle(
        args.output_root / "v056",
        args.output_root / "v056" / "authoring_bundle",
    )

    base_handoff = json.loads((args.output_root / "operation_handoff.json").read_text(encoding="utf-8"))
    base_handoff.update({
        "schema_version": "racenote-v056-forward-turn1-handoff-0.1",
        "status": "READY_FOR_V056_AUTHORING",
        "logic_version": session["logic_version"],
        "contract_revision": session.get("contract_revision"),
        "reader_projection": session.get("reader_projection"),
        "session_id": session["session_id"],
        "reader_count": len(session["race_roster"]),
        "kyi_coverage": bundle["coverage"],
        "authoring_bundle": {
            "path": "v056/authoring_bundle",
            "status": authoring["status"],
            "prediction_policy": authoring["prediction_policy"],
            "automated_scoring": False,
            "automated_ranking": False,
            "automated_marks": False,
        },
        "analysis_freshness": {
            "owner": "DEDICATED_ANALYSIS_OPERATION",
            "forward_t1_checked": False,
        },
        "rrdb_freshness": {
            "owner": "DEDICATED_RRDB_OPERATION",
            "forward_t1_checked": False,
        },
        "race_lap_freshness": {
            "owner": "FORWARD_T1",
            "forward_t1_checked": True,
            "expected_period_to": args.race_lap_expected_period_to,
        },
        "market_blind": True,
        "stripped_at_input_bind": True,
        "result_opened": False,
        "target_market_opened": False,
    })
    write_json(args.output_root / "operation_handoff.json", base_handoff)
    print(json.dumps({
        "status": base_handoff["status"],
        "session_id": session["session_id"],
        "race_count": len(session["race_roster"]),
        "authoring_bundle": "v056/authoring_bundle",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
