"""Validate ephemeral public Google Drive manifests carried by fallback Issues.

This extends the request transport only. Actual download and SHA verification are
delegated to the existing tools/gpt_io/public_drive/fetch.py implementation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

MAX_GROUPS = 8
MAX_FILES = 32
MAX_TOTAL_BYTES = 1024 ** 3
LABEL = re.compile(r"[A-Za-z0-9_-]{1,40}")
ARTIFACT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
FILE_ID = re.compile(r"[A-Za-z0-9_-]{10,128}")
SHA = re.compile(r"[a-f0-9]{64}")
GROUP_FIELDS = frozenset(("label", "artifacts"))
ROW_FIELDS = frozenset(("artifact_id", "file_id", "destination", "expected_name", "expected_size", "sha256"))


class DynamicInputError(ValueError):
    """Invalid dynamic source declaration. No network request may be executed."""


def _validate_destination(value: str, name: str) -> None:
    if not isinstance(value, str) or not isinstance(name, str):
        raise DynamicInputError("INVALID_MANIFEST: non-string destination/name")
    if not value or value.startswith("/") or "\\" in value or "\x00" in value:
        raise DynamicInputError("INVALID_MANIFEST: unsafe destination")
    parts = value.split("/")
    if any(part in ("", ".", "..") or ":" in part for part in parts):
        raise DynamicInputError("INVALID_MANIFEST: unsafe destination")
    if parts[-1] != name or name in ("", ".", ".."):
        raise DynamicInputError("INVALID_MANIFEST: expected_name mismatch")


def validate_dynamic_inputs(groups, reserved_labels: set[str] | None = None) -> set[str]:
    if not isinstance(groups, list) or len(groups) > MAX_GROUPS:
        raise DynamicInputError("INVALID_MANIFEST: dynamic_public_drive_inputs must be 0..8 groups")
    reserved_labels = set() if reserved_labels is None else reserved_labels
    labels, file_ids = set(), set()
    file_count, total_bytes = 0, 0
    for group in groups:
        if not isinstance(group, dict) or set(group) != GROUP_FIELDS:
            raise DynamicInputError("INVALID_MANIFEST: group fields")
        label, rows = group["label"], group["artifacts"]
        if not isinstance(label, str) or not LABEL.fullmatch(label) or label in labels | reserved_labels:
            raise DynamicInputError("INVALID_MANIFEST: invalid or duplicate dynamic label")
        if not isinstance(rows, list) or not rows:
            raise DynamicInputError("INVALID_MANIFEST: empty dynamic input group")
        labels.add(label)
        destinations, artifact_ids = set(), set()
        for row in rows:
            file_count += 1
            if file_count > MAX_FILES:
                raise DynamicInputError("INVALID_MANIFEST: too many dynamic source files")
            if not isinstance(row, dict) or set(row) != ROW_FIELDS:
                raise DynamicInputError("INVALID_MANIFEST: unexpected/missing artifact fields")
            artifact_id, file_id = row["artifact_id"], row["file_id"]
            if not isinstance(artifact_id, str) or not ARTIFACT_ID.fullmatch(artifact_id) or artifact_id in artifact_ids:
                raise DynamicInputError("INVALID_MANIFEST: invalid or duplicate artifact_id")
            if not isinstance(file_id, str) or not FILE_ID.fullmatch(file_id) or file_id in file_ids:
                raise DynamicInputError("INVALID_MANIFEST: invalid or duplicate Drive file_id")
            if not isinstance(row["sha256"], str) or not SHA.fullmatch(row["sha256"]):
                raise DynamicInputError("INVALID_MANIFEST: invalid sha256")
            size = row["expected_size"]
            if type(size) is not int or size <= 0:
                raise DynamicInputError("INVALID_MANIFEST: expected_size must be positive integer")
            total_bytes += size
            if total_bytes > MAX_TOTAL_BYTES:
                raise DynamicInputError("INVALID_MANIFEST: total file size limit exceeded")
            _validate_destination(row["destination"], row["expected_name"])
            if row["destination"] in destinations:
                raise DynamicInputError("INVALID_MANIFEST: duplicate destination")
            destinations.add(row["destination"])
            artifact_ids.add(artifact_id)
            file_ids.add(file_id)
    return labels


def canonical_manifest(group: dict) -> dict:
    return {
        "schema_version": 1,
        "transport": "public_google_drive",
        "artifacts": group["artifacts"],
    }


def build_ephemeral_manifests(groups: list[dict], directory: Path, reserved_labels: set[str] | None = None) -> list[dict]:
    """Write checked manifests under the ephemeral Actions runner working directory."""
    validate_dynamic_inputs(groups, reserved_labels)
    directory.mkdir(parents=True, exist_ok=True)
    results = []
    for group in groups:
        label = group["label"]
        payload = canonical_manifest(group)
        raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        path = directory / f"{label}.json"
        with path.open("xb") as f:
            f.write(raw)
        results.append({
            "label": label,
            "manifest_path": str(path),
            "manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "artifacts": [{"artifact_id": r["artifact_id"], "file_id": r["file_id"],
                           "destination": r["destination"], "expected_size": r["expected_size"],
                           "sha256": r["sha256"]} for r in group["artifacts"]],
        })
    return results
