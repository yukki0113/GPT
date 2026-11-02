#!/usr/bin/env python3
"""Fetch approved mutable RRDB CURRENT, sealing verified bytes and source ID.

No Drive REST/service-account API or dynamic folder listing is introduced.
Rotating the public Drive ID requires reviewed promotion of the JRDB source
contract; existing weekly in-place updates need no Git change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

from rrdb_current_source_contract import approved_source

CURRENT_MEMBER = "postrace_review/v0_1/current.json"
MAX_BYTES = 150_000_000
HEX64 = re.compile(r"[a-f0-9]{64}\Z")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _manifest_within_root(pointer: dict) -> str:
    if pointer.get("status") != "CURRENT" or pointer.get("artifact_type") != "jrdb_postrace_review":
        raise ValueError("RRDB CURRENT pointer status/artifact mismatch")
    generation = pointer.get("generation_id")
    ref = pointer.get("manifest")
    if not isinstance(generation, str) or not generation:
        raise ValueError("RRDB CURRENT generation ID missing")
    if not isinstance(ref, str) or not ref or ref.startswith("/") or "\\" in ref:
        raise ValueError("RRDB CURRENT manifest path invalid")
    parts = Path(ref).parts
    if ".." in parts or "." in parts:
        raise ValueError("RRDB CURRENT manifest path unsafe")
    return "postrace_review/v0_1/" + ref


def _inspect_zip(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        if len(names) != len(set(names)) or CURRENT_MEMBER not in names:
            raise ValueError("RRDB CURRENT invalid or duplicate archive members")
        for member in members:
            name = member.filename
            parts = Path(name).parts
            if (name.startswith("/") or "\\" in name or ".." in parts
                    or (member.is_dir() and not name.endswith("/"))):
                raise ValueError("RRDB CURRENT unsafe archive member")
        if archive.getinfo(CURRENT_MEMBER).file_size > 10_000_000:
            raise ValueError("RRDB CURRENT metadata too large")
        if archive.testzip() is not None:
            raise ValueError("RRDB CURRENT archive CRC failed")
        current = json.loads(archive.read(CURRENT_MEMBER))
        if not isinstance(current, dict):
            raise ValueError("RRDB CURRENT metadata must be an object")
        manifest_path = _manifest_within_root(current)
        if manifest_path not in names or archive.getinfo(manifest_path).file_size > 10_000_000:
            raise ValueError("RRDB CURRENT manifest missing or too large")
        raw_manifest = archive.read(manifest_path)
        manifest = json.loads(raw_manifest)
        if not isinstance(manifest, dict) or manifest.get("validation_status") != "PASS":
            raise ValueError("RRDB CURRENT manifest is not PASS")
        if manifest.get("generation_id") != current["generation_id"]:
            raise ValueError("RRDB CURRENT pointer/manifest generation mismatch")
        if not re.fullmatch(r"20\d{2}-\d\d-\d\d", str(manifest.get("period_to", ""))):
            raise ValueError("RRDB CURRENT manifest period_to invalid")
        return {
            "generation_id": current["generation_id"],
            "period_to": manifest["period_to"],
            "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        }


def fetch(destination: Path, receipt: Path, *, source_config: Path | None = None,
          expected_file_id: str | None = None, expected_sha256: str | None = None,
          downloader=None):
    source = approved_source(source_config)
    file_id = source["file_id"]
    if expected_file_id is not None and file_id != expected_file_id:
        raise ValueError("RRDB CURRENT requested ID differs from approved source")
    if expected_sha256 is not None and not HEX64.fullmatch(expected_sha256):
        raise ValueError("invalid RRDB expected SHA256")
    destination = Path(destination)
    receipt = Path(receipt)
    if destination.exists() or receipt.exists():
        raise FileExistsError("RRDB CURRENT destination or receipt already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    if downloader is None:
        import gdown
        downloader = lambda id, output: gdown.download(id=id, output=str(output), quiet=True)

    with tempfile.TemporaryDirectory(prefix="rrdb-current-", dir=destination.parent) as tmp:
        local = Path(tmp) / "rrdb.zip"
        downloaded = downloader(file_id, local)
        if downloaded is None or not local.is_file():
            raise ValueError("RRDB CURRENT download failed")
        size = local.stat().st_size
        if not (1024 < size <= MAX_BYTES):
            raise ValueError(f"RRDB CURRENT unexpected download size: {size}")
        meta = _inspect_zip(local)
        digest = sha256(local)
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError("RRDB CURRENT expected SHA mismatch")
        # A source promotion racing this run must never silently mix identities.
        if approved_source(source_config)["source_contract_sha256"] != source["source_contract_sha256"]:
            raise ValueError("RRDB CURRENT source pointer changed during download")
        record = {
            "schema_version": 1,
            "transport": "public_google_drive_current_verified_at_download",
            "artifact_id": "rrdb_current",
            "file_id": file_id,
            "destination": "rrdb.zip",
            "size": size,
            "sha256": digest,
            "verified": True,
            "validation": ["ZIP_CRC", "SAFE_ARCHIVE_MEMBERS",
                           "CURRENT_JSON_OBJECT", "MANIFEST_PASS", "GENERATION_MATCH"],
            "generation_id": meta["generation_id"],
            "period_to": meta["period_to"],
            "manifest_sha256": meta["manifest_sha256"],
            "source_contract_sha256": source["source_contract_sha256"],
            "source_revision": source["source_revision"],
            "canonical_folder_id": source["canonical_folder_id"],
            "file_name": source["file_name"],
            "approval_reference": source["approval_reference"],
        }
        staged_receipt = Path(tmp) / "receipt.json"
        staged_receipt.write_text(json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                                  encoding="utf-8")
        if destination.exists() or receipt.exists():
            raise FileExistsError("RRDB CURRENT destination or receipt created concurrently")
        os.replace(local, destination)
        os.replace(staged_receipt, receipt)
    print(json.dumps(record, ensure_ascii=False, sort_keys=True))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--source-config", type=Path, default=None,
                        help="Reviewed Git current source pointer; default canonical config")
    parser.add_argument("--expected-file-id", default=None)
    parser.add_argument("--expected-sha256", default=None)
    args = parser.parse_args()
    fetch(args.output, args.receipt, source_config=args.source_config,
          expected_file_id=args.expected_file_id, expected_sha256=args.expected_sha256)


if __name__ == "__main__":
    main()
