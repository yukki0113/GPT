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
import hashlib
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
    from datetime import date as Date
    from zipfile import ZipFile
    import hashlib
    try:
        parsed = Date.fromisoformat(args.date)
    except ValueError as exc:
        raise ValueError("Date must be YYYY-MM-DD") from exc
    if parsed.isoformat() != args.date:
        raise ValueError("Date must be YYYY-MM-DD")
    expected_root = Path("horse-racing/jrdb/daily") / args.date.replace("-", "") / "v056_day"
    if args.output_root != expected_root:
        raise ValueError(f"Noncanonical forward root: {args.output_root}, expected: {expected_root}")
    expected_selection = "DAILY-" + args.date.replace("-", "")
    if args.selection_id and args.selection_id != expected_selection:
        raise ValueError("Forward selection-id/date mismatch")
    if args.paci.is_symlink() or not args.paci.is_file():
        raise ValueError("PACI must be an existing regular ZIP file")
    paci_name = "PACI" + args.date[2:4] + args.date[5:7] + args.date[8:10] + ".zip"
    if args.paci.name.upper() != paci_name.upper():
        raise ValueError(f"Wrong PACI date: expected {paci_name}")
    with ZipFile(args.paci) as archive:
        if not archive.namelist() or archive.testzip() is not None:
            raise ValueError("PACI CRC/contents invalid")

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

    # Both the prepared Reader and v056 seal must bind the same pre-race RaceLap.
    base_receipt = json.loads((args.output_root / "operation_handoff.json").read_text(encoding="utf-8"))
    lap = base_receipt.get("race_lap_resolution") or {}
    race_lap_parquet = args.race_lap_current_bundle / "race_lap.parquet"
    if lap.get("status") != "CURRENT_READY" or lap.get("updated") is not False:
        raise ValueError("RaceLap CURRENT must be pre-resolved and exact-cutoff")
    if not race_lap_parquet.is_file():
        raise FileNotFoundError(race_lap_parquet)
    h = hashlib.sha256()
    with race_lap_parquet.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    if h.hexdigest() != lap.get("parquet_sha256"):
        raise ValueError("RaceLap SHA differs from forecast_prep");

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
        "execution_mode": "FORWARD",
        "reader_manifest_sha256": session["reader_manifest_sha256"],
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
    if base_handoff.get("selection_id") != selection_id or base_handoff.get("target_date") != args.date:
        raise ValueError("PACI/preparation identity changed")
    if authoring.get("race_count") != len(session["race_roster"]) or not session["race_roster"]:
        raise ValueError("Reader/authoring roster mismatch")
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
