#!/usr/bin/env python3
"""Materialize the operator-verified canonical Google Drive PACI ZIP.

This is the only v0.5.6 FORWARD PACI transport. Never download from JRDB.
The caller must resolve and verify the target-day Drive file ID (and parent)
using the connected Drive inventory before dispatching the workflow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

CANONICAL_FOLDER_ID = "1zFajenPU5jxInZCcmqZzkgiaYil3MD8r"
DRIVE_ID = re.compile(r"[A-Za-z0-9_-]{20,128}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
VERSION = "racenote-v056-forward-drive-paci-receipt-0.1"


def materialize(
    target_date: str,
    drive_file_id: str,
    output: Path,
    receipt: Path,
    *,
    expected_sha256: str | None = None,
) -> dict:
    day = date.fromisoformat(target_date)
    if day.isoformat() != target_date:
        raise ValueError("Target date must be YYYY-MM-DD")
    if not DRIVE_ID.fullmatch(drive_file_id):
        raise ValueError("Invalid canonical Google Drive file ID")
    if expected_sha256 and not SHA256.fullmatch(expected_sha256):
        raise ValueError("Invalid expected PACI SHA-256")
    filename = "PACI" + day.strftime("%y%m%d") + ".zip"
    if output.name.casefold() != filename.casefold():
        raise ValueError("PACI destination must have exact target-day filename")
    if output.exists() or output.is_symlink():
        raise FileExistsError("PACI output already exists (will not overwrite)")
    if receipt.exists() or receipt.is_symlink():
        raise FileExistsError("PACI receipt already exists (will not overwrite)")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["gdown", drive_file_id, "-O", str(output)],
            check=True,
        )
        if not output.is_file() or output.is_symlink() or output.stat().st_size == 0:
            raise ValueError("Google Drive PACI download missing or empty")
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            if not names or archive.testzip() is not None:
                raise ValueError("Google Drive PACI ZIP CRC failed")
            if any(x.startswith("/") or ".." in Path(x).parts for x in names):
                raise ValueError("PACI ZIP contains unsafe member names")
            expected_kyi = "KYI" + day.strftime("%y%m%d") + ".TXT"
            if not any(Path(member).name.upper() == expected_kyi for member in names):
                raise ValueError("PACI ZIP does not contain target-date KYI")
        h = hashlib.sha256()
        with output.open("rb") as stream:
            for part in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(part)
        content_sha = h.hexdigest()
        if expected_sha256 and content_sha != expected_sha256:
            raise ValueError("PACI SHA-256 mismatch against canonical Drive reference")
        metadata = {
            "schema_version": VERSION,
            "status": "DRIVE_PACI_VERIFIED",
            "source": "GOOGLE_DRIVE_CANONICAL_PACI",
            "drive_file_id": drive_file_id,
            "canonical_folder_id": CANONICAL_FOLDER_ID,
            "filename": filename,
            "target_date": target_date,
            "sha256": content_sha,
            "size_bytes": output.stat().st_size,
            "expected_sha256_matched": bool(expected_sha256),
            "jrdb_direct_fetch": False,
        }
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(metadata, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return metadata
    except BaseException:
        # The previous failed attempt is not an accepted canonical input.
        output.unlink(missing_ok=True)
        raise


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", required=True)
    p.add_argument("--drive-file-id", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--expected-sha256")
    args = p.parse_args()
    print(json.dumps(materialize(
        args.date, args.drive_file_id, args.output, args.receipt,
        expected_sha256=args.expected_sha256,
    ), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
