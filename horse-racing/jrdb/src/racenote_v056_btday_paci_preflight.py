#!/usr/bin/env python3
"""Read-only BTDAY PACI preflight; does not create or accept a T1."""
from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import date
from pathlib import Path

from jrdb_raw import Parser, split_fixed_records
from racenote_v056_forward_drive_paci import CANONICAL_FOLDER_ID, VERSION


def validate_paci(target_date: str, archive: Path, source_receipt: Path) -> dict:
    day = date.fromisoformat(target_date)
    if day.isoformat() != target_date:
        raise ValueError("target date must be ISO YYYY-MM-DD")
    if archive.is_symlink() or not archive.is_file():
        raise ValueError("PACI must be a regular file")
    name = f"PACI{day:%y%m%d}.zip"
    if archive.name.upper() != name.upper():
        raise ValueError("PACI filename/date mismatch")
    receipt = json.loads(source_receipt.read_text(encoding="utf-8"))
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    if (receipt.get("schema_version") != VERSION
            or receipt.get("status") != "DRIVE_PACI_VERIFIED"
            or receipt.get("source") != "GOOGLE_DRIVE_CANONICAL_PACI"
            or receipt.get("canonical_folder_id") != CANONICAL_FOLDER_ID
            or receipt.get("target_date") != target_date
            or str(receipt.get("filename", "")).upper() != name.upper()
            or not receipt.get("drive_file_id") or receipt.get("sha256") != sha
            or receipt.get("jrdb_direct_fetch") is not False):
        raise ValueError("PACI source receipt mismatch")
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if not names or z.testzip() is not None:
            raise ValueError("PACI ZIP CRC failed")
        if any(Path(n).is_absolute() or ".." in Path(n).parts for n in names):
            raise ValueError("unsafe PACI ZIP member")
        forbidden = {f"{kind}{day:%y%m%d}.TXT" for kind in ("SED", "HJC")}
        if any(Path(n).name.upper() in forbidden for n in names):
            raise ValueError("target-date result member in PACI")
        records = {}
        for kind in ("BAC", "KYI"):
            expected = f"{kind}{day:%y%m%d}.TXT"
            matches = [n for n in names if Path(n).name.upper() == expected]
            if len(matches) != 1:
                raise ValueError(f"missing or duplicate {kind} member")
            records[kind] = split_fixed_records(z.read(matches[0]), kind)
            if not records[kind]:
                raise ValueError(f"empty or invalid {kind} records")
    parser = Parser()
    races = [parser.bac(r) for r in records["BAC"]]
    horses = [parser.kyi(r) for r in records["KYI"]]
    keys = [r.get("race_key_raw") for r in races]
    if (any(r.get("date_raw") != day.strftime("%Y%m%d") for r in races)
            or len(set(keys)) != len(keys) or not all(keys)):
        raise ValueError("PACI BAC date or roster invalid")
    entries = [(h.get("race_key_raw"), h.get("horse_no")) for h in horses]
    if (any(key not in keys or not number for key, number in entries)
            or len(entries) != len(set(entries))
            or set(key for key, _ in entries) != set(keys)):
        raise ValueError("PACI KYI roster invalid")
    return {"status": "PACI_PREFLIGHT_PASS", "target_date": target_date,
            "drive_file_id": receipt["drive_file_id"], "sha256": sha,
            "race_count": len(races), "horse_count": len(horses)}
