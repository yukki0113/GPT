"""Deterministic D2 publication guards. Drive I/O is performed by the authenticated caller.

This module never modifies MD_CURRENT_HEAD, inventory, or the live Drive catalog.
Callers must independently fetch/verify an uploaded immutable snapshot, back up
the current catalog, re-read it immediately before its non-CAS replacement, and
verify the independently fetched replacement after the update.
"""
from __future__ import annotations

import copy
import json
from typing import Any

from .__main__ import check as check_snapshot
from .catalog import canonical, sha256, validate, validate_snapshot_pointer


class PublicationConflict(ValueError):
    """Snapshot/catalog content or generation differs from the pinned state."""


def verify_uploaded_snapshot(expected_snapshot: dict, uploaded_raw: bytes, db_path: str | None = None) -> dict:
    """Validate independently downloaded bytes after immutable Drive upload.

    Validation is not a license to use unverified card IDs: confirmed real
    decks require a real read-only master DB path.
    """
    report = check_snapshot(expected_snapshot, db_path)
    if expected_snapshot["state"] == "CONFIRMED" and db_path is None:
        raise ValueError("CONFIRMED snapshot requires read-only card master lookup")
    expected = canonical(expected_snapshot)
    if not isinstance(uploaded_raw, bytes) or uploaded_raw != expected:
        raise PublicationConflict("uploaded snapshot raw bytes differ from expected canonical content")
    reloaded = json.loads(uploaded_raw)
    if sha256(reloaded) != report["sha256"]:
        raise PublicationConflict("uploaded snapshot SHA mismatch")
    return report


def prepare_catalog_update(
    base_catalog: dict,
    expected_base_sha256: str,
    snapshot: dict,
    uploaded_raw: bytes,
    uploaded_drive_file_id: str,
    timestamp_utc: str,
    db_path: str | None = None,
    variant: str | None = None,
) -> dict:
    """Propose next catalog generation; never write the live catalog."""
    base_report = validate(base_catalog)
    if base_report["sha256"] != expected_base_sha256:
        raise PublicationConflict("stale or mismatched base catalog SHA")
    if not isinstance(uploaded_drive_file_id, str) or not uploaded_drive_file_id.strip():
        raise ValueError("Drive file ID required")
    report = verify_uploaded_snapshot(snapshot, uploaded_raw, db_path)
    candidate = copy.deepcopy(base_catalog)
    deck_id, version = snapshot["deck_id"], snapshot["version"]
    found = next((d for d in candidate["decks"] if d["deck_id"] == deck_id), None)
    if found is None:
        if version != 1 or snapshot.get("supersedes") is not None:
            raise ValueError("new deck must begin at version 1")
        found = {"deck_id": deck_id, "name": snapshot["name"],
                 "aliases": list(snapshot.get("aliases", [])),
                 "variant": variant, "versions": []}
        candidate["decks"].append(found)
    else:
        if version != len(found["versions"]) + 1:
            raise PublicationConflict("version is not next consecutive version")
        if snapshot["supersedes"] != found["versions"][-1]["snapshot_sha256"]:
            raise PublicationConflict("supersedes does not match prior stored snapshot")
        if snapshot["name"] != found["name"]:
            raise PublicationConflict("deck name changed without explicit catalog rename migration")
        if list(snapshot.get("aliases", [])) != found["aliases"]:
            raise PublicationConflict("aliases changed without explicit catalog rename migration")
        if variant is not None and variant != found.get("variant"):
            raise PublicationConflict("deck variant changed without explicit catalog rename migration")
    if any(uploaded_drive_file_id == v["drive_file_id"] for d in candidate["decks"] for v in d["versions"]):
        raise PublicationConflict("Drive file ID reused")
    pointer = {"version": version, "state": snapshot["state"],
               "snapshot_sha256": report["sha256"],
               "drive_file_id": uploaded_drive_file_id,
               "supersedes": snapshot.get("supersedes")}
    found["versions"].append(pointer)
    candidate["generation"] += 1
    candidate["updated_at"] = timestamp_utc
    validate(candidate)
    validate_snapshot_pointer(candidate, snapshot, deck_id, version)
    return candidate


def verify_base_before_activation(
    expected_base: dict,
    reread_raw: bytes,
) -> dict:
    """Fail closed when catalog changed between preview and activation."""
    report = validate(expected_base)
    if not isinstance(reread_raw, bytes) or reread_raw != canonical(expected_base):
        raise PublicationConflict("catalog changed since base was read")
    reread = json.loads(reread_raw)
    if sha256(reread) != report["sha256"]:
        raise PublicationConflict("base catalog hash does not match readback")
    return report


def verify_activated_catalog(candidate: dict, reread_raw: bytes) -> dict:
    """Verify post-activation raw catalog bytes, not update response metadata."""
    report = validate(candidate)
    if not isinstance(reread_raw, bytes) or reread_raw != canonical(candidate):
        raise PublicationConflict("activated catalog differs from the proposed bytes")
    return report
