#!/usr/bin/env python3
"""Fetch mutable RRDB CURRENT and bind the exact validated bytes per run.

Only the RRDB CURRENT transport is dynamic. This does NOT weaken frozen
BTDAY prediction / clean-blind barriers or validate RRDB semantic correctness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile

CURRENT_FILE_ID = "1UwNfrupMTHRPhkzULPvClGre4MWz2TFg"
CURRENT_MEMBER = "postrace_review/v0_1/current.json"
MAX_BYTES = 150_000_000


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fetch(destination: Path, receipt: Path):
    import gdown

    destination.parent.mkdir(parents=True, exist_ok=True)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    # Deliberately use a new file, not the previous week's immutable digest.
    with tempfile.TemporaryDirectory(prefix="rrdb-current-", dir=destination.parent) as tmp:
        local = Path(tmp) / "rrdb.zip"
        fetched = gdown.download(id=CURRENT_FILE_ID, output=str(local), quiet=True)
        if fetched is None or not local.is_file():
            raise ValueError("RRDB CURRENT download failed")
        size = local.stat().st_size
        if not (1024 < size <= MAX_BYTES):
            raise ValueError(f"RRDB CURRENT unexpected download size: {size}")
        with zipfile.ZipFile(local) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or CURRENT_MEMBER not in names:
                raise ValueError("RRDB CURRENT invalid archive members")
            for member in archive.infolist():
                parts = Path(member.filename).parts
                if (member.filename.startswith("/") or ".." in parts
                        or "\\" in member.filename or member.is_dir() and not member.filename.endswith("/")):
                    raise ValueError("RRDB CURRENT unsafe archive member")
            member = archive.getinfo(CURRENT_MEMBER)
            if member.file_size > 10_000_000:
                raise ValueError("RRDB CURRENT metadata unexpectedly large")
            if archive.testzip() is not None:
                raise ValueError("RRDB CURRENT archive CRC failed")
            metadata = json.loads(archive.read(CURRENT_MEMBER))
            if not isinstance(metadata, dict):
                raise ValueError("RRDB CURRENT metadata must be an object")
        record = {
            "schema_version": 1,
            "transport": "public_google_drive_current_verified_at_download",
            "artifact_id": "rrdb_current",
            "file_id": CURRENT_FILE_ID,
            "destination": "rrdb.zip",
            "size": size,
            "sha256": sha256(local),
            "verified": True,
            "validation": ["ZIP_CRC", "SAFE_ARCHIVE_MEMBERS", "CURRENT_JSON_OBJECT"],
        }
        if destination.exists():
            raise FileExistsError("RRDB CURRENT destination already exists")
        os.replace(local, destination)
    receipt.write_text(json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                       encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, sort_keys=True))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--receipt", type=Path, required=True)
    args = ap.parse_args()
    fetch(args.output, args.receipt)


if __name__ == "__main__":
    main()
