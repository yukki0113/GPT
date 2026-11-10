#!/usr/bin/env python3
"""Candidate PACI BTDAY T1 adapter; not wired into production NEXT."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from racenote_v056_btday_paci_preflight import validate_paci
from racenote_v056_btday_source_router import verify_readiness_receipt
from racenote_v056_forward_freshness import _inspect_analysis, _inspect_rrdb
from racenote_v056_forward_turn1 import build_common


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_rrdb_objects(root: Path, archive: Path) -> None:
    """Bind every extracted RRDB relation object to the verified archive."""
    pointer = _read(root / "current.json")
    manifest_ref = Path(str(pointer.get("manifest") or ""))
    if manifest_ref.is_absolute() or ".." in manifest_ref.parts:
        raise ValueError("unsafe RRDB manifest path")
    manifest = _read(root / manifest_ref)
    partitions = [part for relation in (manifest.get("relations") or {}).values()
                  for part in relation.get("partitions", [])]
    if not partitions:
        raise ValueError("RRDB has no relation objects")
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate RRDB archive member")
        for part in partitions:
            rel = Path(str(part.get("relative_path") or ""))
            if rel.is_absolute() or not rel.parts or ".." in rel.parts:
                raise ValueError("unsafe RRDB relation path")
            path = root / rel
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("RRDB extracted object unavailable")
            suffix = "/" + rel.as_posix()
            matches = [name for name in names if name == rel.as_posix() or name.endswith(suffix)]
            if len(matches) != 1:
                raise ValueError("RRDB archive object missing or ambiguous")
            digest = hashlib.sha256()
            with z.open(matches[0]) as member:
                for block in iter(lambda: member.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != _sha(path):
                raise ValueError("RRDB extracted object differs from verified archive")


def validate_as_of(args, row: dict, receipt: dict) -> dict:
    target = date.fromisoformat(args.date)
    evidence = receipt["as_of_evidence"]
    measured = {"analysis": _inspect_analysis(args.analysis_root),
                "rrdb": _inspect_rrdb(args.racereview_root, args.rrdb_zip, args.rrdb_receipt)}
    for label, actual in measured.items():
        expected = evidence[label]
        for key in ("generation_id", "manifest_sha256", "coverage_through"):
            if actual.get(key) != expected.get(key):
                raise ValueError(f"{label} {key} differs from accepted as-of evidence")
        if date.fromisoformat(actual["coverage_through"]) >= target:
            raise ValueError(f"{label} contains target or future information")
    rrdb = evidence["rrdb"]
    if (measured["rrdb"]["zip_sha256"] != rrdb.get("zip_sha256")
            or measured["rrdb"]["file_id"] != rrdb.get("file_id")):
        raise ValueError("RRDB transport differs from accepted as-of evidence")
    verify_rrdb_objects(args.racereview_root, args.rrdb_zip)
    lap = evidence["race_lap"]
    lap_manifest_path = args.race_lap_current_bundle / "manifest.json"
    lap_manifest = _read(lap_manifest_path)
    if (date.fromisoformat(args.race_lap_expected_period_to) >= target
            or lap.get("coverage_through") != args.race_lap_expected_period_to
            or lap_manifest.get("period_to") != args.race_lap_expected_period_to
            or lap_manifest.get("validation_status") != "PASS"
            or lap_manifest.get("generation_id") != lap.get("generation_id")
            or _sha(lap_manifest_path) != lap.get("manifest_sha256")
            or _sha(args.race_lap_current_bundle / "race_lap.parquet") != lap.get("parquet_sha256")):
        raise ValueError("RaceLap as-of evidence mismatch")
    return {"status": "PASS", "target_date": args.date,
            "required_completed_through": args.race_lap_expected_period_to,
            "analysis": measured["analysis"], "rrdb": measured["rrdb"]}


def prepare(args) -> int:
    if not re.fullmatch(r"BTDAY-\d{4}", args.selection_id):
        raise ValueError("invalid BTDAY selection ID")
    day = date.fromisoformat(args.date)
    if day.isoformat() != args.date:
        raise ValueError("invalid target date")
    if day > datetime.now(ZoneInfo("Asia/Tokyo")).date():
        raise ValueError("BTDAY target cannot be future")
    expected = Path("horse-racing/jrdb/backtests") / args.selection_id / day.strftime("%Y%m%d")
    if args.output_root != expected or args.output_root.exists() or args.output_root.is_symlink():
        raise ValueError("BTDAY output root must be canonical and new")
    if not re.fullmatch(r"[0-9a-f]{40}", args.main_sha):
        raise ValueError("main SHA must be full lowercase SHA")
    selection = _read(expected.parent / "selection.json")
    row = _read(args.source_row)
    if (selection.get("selection_schema_version") != "btday-source-selection-v2"
            or selection.get("selection_id") != args.selection_id
            or selection.get("target_date") != args.date
            or selection.get("dates") != [args.date]
            or selection.get("source_mode") != "paci"
            or row.get("target_date") != args.date or row.get("source_mode") != "paci"
            or row.get("readiness_status") != "READY" or row.get("eligible") is not True
            or selection.get("source_reference") != row.get("source_reference")
            or selection.get("source_generation_id") != row.get("source_generation_id")
            or selection.get("source_receipt_sha256") != row.get("receipt_sha256")):
        raise ValueError("selection and source identity mismatch")
    verify_readiness_receipt(row, Path.cwd())
    accepted = _read(Path(row["readiness_receipt_path"]))
    paci = validate_paci(args.date, args.paci, args.paci_source_receipt)
    if paci["sha256"] != row["input_sha256"] or paci["drive_file_id"] != row["drive_file_id"]:
        raise ValueError("materialized PACI differs from reserved source")
    freshness = validate_as_of(args, row, accepted)
    paci_receipt = _read(args.paci_source_receipt)
    return build_common(
        args, paci_receipt, freshness, args.selection_id, execution_mode="BTDAY",
        handoff_extra={"source_mode": "paci", "source_generation_id": row["source_generation_id"],
                       "source_sha256": paci["sha256"], "source_receipt_sha256": row["receipt_sha256"],
                       "as_of_exclusive": args.date},
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ("date", "selection-id", "main-sha", "race-lap-expected-period-to"):
        p.add_argument("--" + flag, required=True)
    for flag in ("paci", "paci-source-receipt", "source-row", "analysis-root", "course-fit-root",
                 "racereview-root", "race-lap-current-bundle", "rrdb-zip", "rrdb-receipt", "output-root"):
        p.add_argument("--" + flag, type=Path, required=True)
    return prepare(p.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
