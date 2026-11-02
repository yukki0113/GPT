#!/usr/bin/env python3
"""Approved RRDB operational CURRENT pointer. Local JSON only, never Drive API.

Weekly updates change the bytes behind an approved stable file ID; calculate
new ZIP SHA per run. If the CURRENT file ID is replaced, an explicit reviewed
Git change is required to this pointer, not to immutable historical baselines.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

CANONICAL_FOLDER_ID = "13m2MGibjEHOvBY6LmENQat4PuTZGcdwc"
EXPECTED_NAME = "RaceReviewDB_CURRENT.zip"
VERSION = "jrdb-rrdb-current-source-v1"
DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "config/rrdb_current_source_v1.json"
_DRIVE_ID = re.compile(r"[A-Za-z0-9_-]{10,128}\Z")


class RRDBCurrentSourceError(ValueError):
    pass


def approved_source(config: Path | None = None) -> dict[str, Any]:
    path = Path(config) if config is not None else DEFAULT_SOURCE
    raw = path.read_bytes()
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise RRDBCurrentSourceError("RRDB CURRENT pointer JSON invalid") from exc
    if not isinstance(data, dict):
        raise RRDBCurrentSourceError("RRDB CURRENT pointer must be an object")
    if (data.get("schema_version") != VERSION or data.get("status") != "APPROVED"
            or data.get("source_mode") != "mutable_current_by_approved_drive_file_id"):
        raise RRDBCurrentSourceError("RRDB CURRENT pointer not approved")
    if data.get("canonical_folder_id") != CANONICAL_FOLDER_ID or data.get("file_name") != EXPECTED_NAME:
        raise RRDBCurrentSourceError("RRDB CURRENT pointer has invalid canonical folder/name")
    file_id = data.get("file_id")
    if not isinstance(file_id, str) or not _DRIVE_ID.fullmatch(file_id):
        raise RRDBCurrentSourceError("RRDB CURRENT pointer has invalid file ID")
    if type(data.get("source_revision")) is not int or data["source_revision"] <= 0:
        raise RRDBCurrentSourceError("RRDB CURRENT pointer revision invalid")
    if data.get("approval_method") != "native_google_drive_connector":
        raise RRDBCurrentSourceError("RRDB CURRENT pointer requires connector approval")
    if not isinstance(data.get("approval_reference"), str) or len(data["approval_reference"]) < 8:
        raise RRDBCurrentSourceError("RRDB CURRENT approval reference missing")
    if data.get("sha_policy") != "calculate_and_validate_actual_zip_each_execution":
        raise RRDBCurrentSourceError("RRDB CURRENT must not pin old weekly SHA")
    return {
        "file_id": file_id,
        "canonical_folder_id": CANONICAL_FOLDER_ID,
        "file_name": EXPECTED_NAME,
        "source_revision": data["source_revision"],
        "approval_reference": data["approval_reference"],
        "source_contract_sha256": hashlib.sha256(raw).hexdigest(),
    }
