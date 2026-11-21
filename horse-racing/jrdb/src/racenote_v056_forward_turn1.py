#!/usr/bin/env python3
"""Canonical mechanical T1 wrapper for RaceNote v0.5.6 forward days.

Prediction remains outside this module. The wrapper only:
1) invokes the existing PACI -> market-blind forecast_prep entrypoint;
2) builds the allowlisted KYI evidence bundle;
3) seals v0.5.6 Reader;
4) creates lossless venue authoring bundles;
5) writes a T1 handoff.

Analysis/RRDB updates remain dedicated operations. A05 requires their accepted
coverage and actual generation/SHA to pass a fail-closed preflight before T1.
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
    ap.add_argument("--paci-source-receipt", type=Path, required=True,
                    help="Verified Drive PACI download receipt; no direct JRDB fallback")
    ap.add_argument("--main-sha", required=True)
    ap.add_argument("--analysis-root", type=Path, required=True)
    ap.add_argument("--course-fit-root", type=Path, required=True)
    ap.add_argument("--racereview-root", type=Path, required=True)
    ap.add_argument("--race-lap-current-bundle", type=Path, required=True)
    ap.add_argument("--race-lap-expected-period-to", required=True)
    ap.add_argument("--freshness-acceptance", type=Path,
                    help="Accepted Analysis+RRDB coverage receipt from dedicated operations")
    ap.add_argument("--analysis-artifact-id")
    ap.add_argument("--v2-source-acceptance", type=Path,
                    help="Committed v2 producer receipt; mutually exclusive with legacy A05")
    ap.add_argument("--v2-materialization-receipt", type=Path)
    ap.add_argument("--analysis-generation-id")
    ap.add_argument("--rrdb-zip", type=Path, required=True)
    ap.add_argument("--rrdb-receipt", type=Path, required=True)
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
    from racenote_v056_forward_drive_paci import CANONICAL_FOLDER_ID, VERSION as DRIVE_RECEIPT_VERSION
    paci_receipt = json.loads(args.paci_source_receipt.read_text(encoding="utf-8"))
    if (paci_receipt.get("schema_version") != DRIVE_RECEIPT_VERSION
        or paci_receipt.get("status") != "DRIVE_PACI_VERIFIED"
        or paci_receipt.get("source") != "GOOGLE_DRIVE_CANONICAL_PACI"
        or paci_receipt.get("canonical_folder_id") != CANONICAL_FOLDER_ID
        or paci_receipt.get("target_date") != args.date
        or paci_receipt.get("filename", "").upper() != paci_name.upper()
        or paci_receipt.get("jrdb_direct_fetch") is not False
        or not paci_receipt.get("drive_file_id")):
        raise ValueError("PACI is not a verified canonical Drive download")
    h = hashlib.sha256()
    with args.paci.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    if h.hexdigest() != paci_receipt.get("sha256"):
        raise ValueError("Drive PACI download has changed after receipt")


    if args.output_root.exists():
        raise FileExistsError(f"output root already exists: {args.output_root}")
    # Fail before any forecast package, Reader or session can be created.
    if args.v2_source_acceptance:
        if args.freshness_acceptance or args.analysis_artifact_id or args.analysis_generation_id:
            raise ValueError("v2 source acceptance and legacy A05 inputs are mutually exclusive")
        if args.v2_materialization_receipt is None:
            raise ValueError("v2 materialization receipt is mandatory")
        from racenote_forward_source_acceptance import (
            accept as accept_v2, _load, _sha, _resolve_target_acceptance,
        )
        import tempfile
        materialized = _load(args.v2_materialization_receipt)
        if (materialized.get("status") != "MATERIALIZED"
                or materialized.get("schema_version") != "racenote-forward-materialization-v2"):
            raise ValueError("v2 inputs have no validated materialization")
        with tempfile.TemporaryDirectory(prefix="racenote-v2-lock-") as temporary:
            source_lock = accept_v2(
                args.v2_source_acceptance, repo_root=Path("."),
                target_date=args.date, analysis_root=args.analysis_root,
                rrdb_root=args.racereview_root, rrdb_zip=args.rrdb_zip,
                rrdb_receipt=args.rrdb_receipt,
                course_fit_root=args.course_fit_root,
                race_lap_current_bundle=args.race_lap_current_bundle,
                paci_sha256=paci_receipt["sha256"],
                output=Path(temporary) / "forward_source_lock.json",
            )
        if source_lock["acceptance_sha256"] != materialized.get("acceptance_sha256"):
            raise ValueError("v2 materialization is not bound to committed acceptance")
        effective_acceptance, _ = _resolve_target_acceptance(
            args.v2_source_acceptance, Path("."), args.date
        )
        for name in ("analysis", "course_fit", "race_lap"):
            entry = effective_acceptance[name]
            receipt = materialized.get("sources", {}).get(name)
            if not isinstance(receipt, dict):
                raise ValueError(name + ": missing materialization receipt")
            if receipt.get("source_mode") != entry.get("source_mode") or receipt.get(
                    "producer_acceptance_ref") != entry.get("producer_acceptance_ref"):
                raise ValueError(name + ": materialization and source acceptance mismatch")
            if entry.get("source_parts") is not None:
                expected_parts = [{**part, "archive_format": part.get("archive_format", "zip")}
                                  for part in entry["source_parts"]]
                if receipt.get("source_parts") != expected_parts:
                    raise ValueError(name + ": multipart materialization identity mismatch")
            elif any(receipt.get(field) != entry.get(field)
                     for field in ("source_ref", "source_sha256")) or receipt.get(
                         "archive_format") != entry.get("archive_format", "zip"):
                raise ValueError(name + ": materialization and source acceptance mismatch")
        if source_lock["race_lap"]["period_to"] != args.race_lap_expected_period_to:
            raise ValueError("v2 RaceLap cutoff argument differs from validated source")
        freshness = {
            "schema_version": "racenote-forward-analysis-rrdb-freshness-v2",
            "status": "PASS", "target_date": args.date,
            "required_completed_through": source_lock["required_completed_through"],
            "analysis": source_lock["analysis"], "rrdb": source_lock["rrdb"],
            "source_lock_sha256": None,
        }
    else:
        if not all((args.freshness_acceptance, args.analysis_artifact_id, args.analysis_generation_id)):
            raise ValueError("legacy A05 requires all accepted source parameters")
        from racenote_v056_forward_freshness import validate as validate_freshness
        freshness = validate_freshness(
            args.freshness_acceptance,
            target_date=args.date,
            analysis_root=args.analysis_root,
            analysis_artifact_id=args.analysis_artifact_id,
            analysis_generation_id=args.analysis_generation_id,
            rrdb_root=args.racereview_root,
            rrdb_zip=args.rrdb_zip,
            rrdb_receipt=args.rrdb_receipt,
        )
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
        "paci_source": paci_receipt,
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
            "forward_t1_checked": True,
            "status": freshness["status"],
            "required_completed_through": freshness["required_completed_through"],
            **freshness["analysis"],
        },
        "rrdb_freshness": {
            "owner": "DEDICATED_RRDB_OPERATION",
            "forward_t1_checked": True,
            "status": freshness["status"],
            "required_completed_through": freshness["required_completed_through"],
            **freshness["rrdb"],
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
    if base_handoff.get("paci", {}).get("sha256") != paci_receipt["sha256"]:
        raise ValueError("Day prep PACI SHA is inconsistent with Drive receipt")
    if base_handoff.get("selection_id") != selection_id or base_handoff.get("target_date") != args.date:
        raise ValueError("PACI/preparation identity changed")
    if authoring.get("race_count") != len(session["race_roster"]) or not session["race_roster"]:
        raise ValueError("Reader/authoring roster mismatch")
    audit_root = args.output_root / "source_audit"
    audit_root.mkdir(exist_ok=True)
    if args.v2_source_acceptance:
        lock_path = audit_root / "forward_source_lock.json"
        write_json(lock_path, source_lock)
        with lock_path.open("rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        freshness["source_lock_sha256"] = digest
        base_handoff["source_contract_version"] = "v2"
        base_handoff["source_lock_sha256"] = digest
    write_json(audit_root / "forward_analysis_rrdb_freshness.json", freshness)
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
