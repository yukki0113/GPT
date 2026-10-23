#!/usr/bin/env python3
"""Build a reproducible inline Drive manifest request from GPT connector snapshots.

The native ChatGPT Google Drive connector performs discovery/metadata/download.
This stdlib-only helper validates those observations and pins actual local bytes.
It performs no authenticated network calls and makes no GitHub writes.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys

from dynamic_public_drive_inputs import validate_dynamic_inputs


class SourceError(ValueError):
    pass


def _error(code: str, detail: str) -> None:
    raise SourceError(f"{code}: {detail}")


def _safe_date(target: str) -> date:
    try:
        value = date.fromisoformat(target)
        if value.isoformat() != target:
            raise ValueError()
        return value
    except ValueError:
        _error("INVALID_REQUEST", "date must be YYYY-MM-DD")


def expected_name(config: dict, day: date) -> str:
    fmt = config.get("name_template") or config.get("exact_name")
    if not isinstance(fmt, str):
        _error("INVALID_REQUEST", "source registry requires a filename rule")
    return fmt.replace("{yyyymmdd}", day.strftime("%Y%m%d")).replace("{yymmdd}", day.strftime("%y%m%d"))


def _metadata_id(row: dict) -> str:
    return row.get("id", row.get("file_id", ""))


def _metadata_name(row: dict) -> str:
    return row.get("name", row.get("title", ""))


def _metadata_size(row: dict) -> int:
    value = row.get("size")
    try:
        out = int(value)
        if out <= 0:
            raise ValueError()
        return out
    except (ValueError, TypeError):
        _error("INVALID_REQUEST", "metadata size must be positive")


def _fingerprint(row: dict) -> tuple:
    return (
        _metadata_id(row),
        _metadata_name(row),
        _metadata_size(row),
        row.get("modified_time", row.get("modifiedTime")),
        row.get("revision", row.get("version")),
    )


def resolve_source(config: dict, observation: dict, day: date) -> tuple[dict, dict]:
    name = expected_name(config, day)
    folder = config["folder_id"]
    candidates = observation.get("candidates")
    if not isinstance(candidates, list):
        _error("INVALID_REQUEST", "candidates must be a list")
    exact = []
    for row in candidates:
        if not isinstance(row, dict):
            _error("INVALID_REQUEST", "candidate metadata must be an object")
        if _metadata_name(row) == name and folder in row.get("parent_ids", row.get("parents", [])):
            exact.append(row)
    if not exact:
        _error("SOURCE_NOT_FOUND", f"{config['key']} / {name}")
    if len(exact) != 1:
        _error("SOURCE_AMBIGUOUS", f"{config['key']} / {name} matched {len(exact)} records")
    before = exact[0]
    after = observation.get("metadata_after")
    if not isinstance(after, dict):
        _error("INVALID_REQUEST", "metadata_after must be provided by the Drive connector")
    if _fingerprint(before) != _fingerprint(after):
        _error("SOURCE_CHANGED", f"{config['key']} changed during byte acquisition")
    if folder not in after.get("parent_ids", after.get("parents", [])):
        _error("SOURCE_CHANGED", f"{config['key']} moved during acquisition")
    if not _metadata_id(before):
        _error("INVALID_REQUEST", "missing Drive file id")
    accepted_mimes = config.get("expected_mime_types", [])
    mime = before.get("mime_type", before.get("mimeType"))
    if mime and accepted_mimes and mime not in accepted_mimes:
        _error("INVALID_REQUEST", f"unexpected source mime type for {config['key']}")
    raw_path = Path(observation["download_path"])
    if raw_path.is_symlink() or not raw_path.is_file():
        _error("INVALID_REQUEST", "download_path must be a regular local file")
    binary = raw_path.read_bytes()
    size = _metadata_size(before)
    if size != len(binary):
        _error("SOURCE_CHANGED", f"{config['key']} metadata size != downloaded bytes")
    digest = hashlib.sha256(binary).hexdigest()
    logical = config["key"]
    row = {
        "artifact_id": config["artifact_id_template"].replace("{yyyymmdd}", day.strftime("%Y%m%d")),
        "file_id": _metadata_id(before),
        "destination": name,
        "expected_name": name,
        "expected_size": size,
        "sha256": digest,
    }
    provenance = {"source": logical, "file_id": _metadata_id(before), "name": name,
                  "size": size, "modified_time": before.get("modified_time", before.get("modifiedTime")),
                  "revision": before.get("revision", before.get("version")),
                  "sha256": digest}
    return row, provenance


def build_request(registry: dict, snapshots: dict, template: dict, target_date: str) -> dict:
    day = _safe_date(target_date)
    if registry.get("schema_version") != 1 or not isinstance(registry.get("sources"), list):
        _error("INVALID_REQUEST", "invalid source registry")
    if not isinstance(snapshots, dict) or not isinstance(snapshots.get("sources"), dict):
        _error("INVALID_REQUEST", "snapshots must contain sources mapping")
    if not isinstance(template, dict) or not isinstance(template.get("steps"), list):
        _error("INVALID_REQUEST", "request template must contain steps")
    if "dynamic_public_drive_inputs" in template:
        _error("INVALID_REQUEST", "template cannot override dynamically pinned inputs")
    groups, provenance = [], []
    for config in registry["sources"]:
        source = config["key"]
        observation = snapshots["sources"].get(source)
        if observation is None:
            if config.get("required", False):
                _error("SOURCE_NOT_FOUND", f"snapshot missing for {source}")
            continue
        row, record = resolve_source(config, observation, day)
        groups.append({"label": config["label"], "artifacts": [row]})
        provenance.append(record)
    reserved = {r["label"] for k in ("public_drive_inputs", "input_artifacts", "staged_inputs")
                for r in template.get(k, [])}
    validate_dynamic_inputs(groups, reserved)
    result = dict(template)
    result["dynamic_public_drive_inputs"] = groups
    result["source_fingerprints"] = provenance
    result.setdefault("request_id", "dynamic-drive-" + day.strftime("%Y%m%d"))
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--snapshots", type=Path, required=True, help="GPT Drive metadata before/after, and local download paths")
    p.add_argument("--template", type=Path, required=True, help="Reviewed repository entrypoint/argument template")
    p.add_argument("--date", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        registry = json.loads(a.registry.read_text("utf-8"))
        snapshots = json.loads(a.snapshots.read_text("utf-8"))
        template = json.loads(a.template.read_text("utf-8"))
        result = build_request(registry, snapshots, template, a.date)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "PASS", "output": str(a.output),
                          "source_count": len(result["dynamic_public_drive_inputs"])}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
