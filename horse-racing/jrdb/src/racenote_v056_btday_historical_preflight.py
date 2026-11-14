#!/usr/bin/env python3
"""Validate staged Warehouse T1 inputs before any historical output is made."""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from racenote_v056_btday_paci_t1 import _read, _sha, validate_as_of
from racenote_v056_btday_source_router import verify_readiness_receipt


def validate(args) -> dict:
    day = date.fromisoformat(args.date)
    if day.isoformat() != args.date or not re.fullmatch(r"BTDAY-\d{4}", args.selection_id):
        raise ValueError("invalid target date or selection")
    selection = _read(args.selection)
    row = selection.get("source_row") or {}
    if (selection.get("selection_schema_version") != "btday-source-selection-v2"
            or selection.get("selection_id") != args.selection_id
            or selection.get("dates") != [args.date]
            or selection.get("target_date") != args.date
            or selection.get("source_mode") != "historical_warehouse"
            or row.get("source_mode") != "historical_warehouse"
            or row.get("target_date") != args.date
            or selection.get("source_generation_id") != row.get("source_generation_id")
            or selection.get("source_receipt_sha256") != row.get("receipt_sha256")):
        raise ValueError("historical selection/source mismatch")
    verify_readiness_receipt(row, args.repository_root)
    acceptance = _read(args.repository_root / row["readiness_receipt_path"])
    pointer = _read(args.warehouse_root / "current.json")
    relative = Path(str(pointer.get("manifest") or ""))
    if (relative.is_absolute() or not relative.parts or ".." in relative.parts
            or pointer.get("status") != "accepted"
            or pointer.get("generation_id") != row["source_generation_id"]
            or pointer.get("manifest_sha256") != row["input_sha256"]):
        raise ValueError("Warehouse current pointer mismatch")
    manifest_path = args.warehouse_root / relative
    if (manifest_path.is_symlink() or not manifest_path.is_file()
            or not manifest_path.resolve().is_relative_to(args.warehouse_root.resolve())
            or _sha(manifest_path) != row["input_sha256"]):
        raise ValueError("Warehouse manifest SHA mismatch")
    manifest = _read(manifest_path)
    if manifest.get("status") != "PASS" or manifest.get("generation_id") != row["source_generation_id"]:
        raise ValueError("Warehouse manifest generation invalid")
    verified = 0
    for item in manifest.get("assets") or []:
        rel = Path(str(item.get("relative_path") or ""))
        if rel.is_absolute() or not rel.parts or ".." in rel.parts:
            raise ValueError("unsafe Warehouse asset path")
        path = args.warehouse_root / rel
        if not path.exists():
            continue  # Reader fails if a required partition is missing.
        if (path.is_symlink() or not path.is_file()
                or not path.resolve().is_relative_to(args.warehouse_root.resolve())
                or _sha(path) != item.get("sha256")):
            raise ValueError("Warehouse staged asset SHA mismatch")
        verified += 1
    if not verified:
        raise ValueError("no verified Warehouse assets")
    evidence = acceptance["warehouse"]
    for family in ("BAC", "KYI"):
        raw = args.raw_root / family / f"{family}_{day.year}.zip"
        if not raw.is_file() or raw.is_symlink() or _sha(raw) != evidence.get(f"raw_{family.lower()}_sha256"):
            raise ValueError(f"{family} annual archive SHA mismatch")
    as_of = validate_as_of(args, row, acceptance)
    return {"status": "PASS", "target_date": args.date,
            "source_mode": "historical_warehouse", "source_generation_id": row["source_generation_id"],
            "source_sha256": row["input_sha256"], "source_receipt_sha256": row["receipt_sha256"],
            "as_of_exclusive": args.date, "verified_warehouse_assets": verified, "as_of": as_of}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("date", "selection-id", "race-lap-expected-period-to"):
        parser.add_argument("--" + name, required=True)
    for name in ("selection", "repository-root", "warehouse-root", "raw-root", "analysis-root", "course-fit-root",
                 "racereview-root", "rrdb-zip", "rrdb-receipt", "race-lap-current-bundle", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = validate(args)
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
