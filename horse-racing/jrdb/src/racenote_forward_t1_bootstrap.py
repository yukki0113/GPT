#!/usr/bin/env python3
"""Resolve a single FORWARD T1 into accepted input reuse or producer acceptance.

This is a deterministic *control-plane* gate, not a replacement for producer
operations. A reviewed, committed evidence declaration is necessary whenever
no reusable generation-set has passed the existing acceptance checks.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re

from racenote_forward_errors import DataInvalid, OrchestrationMissing, run_cli
from racenote_forward_source_acceptance import (
    PRODUCER_EVIDENCE_SCHEMA, _canonical_receipt, _date, _load, HEX,
)
from racenote_forward_target_binding import select_generation_set

BASE = Path("horse-racing/jrdb/forward-acceptance")
DAILY = Path("horse-racing/jrdb/daily")
DRIVE_ID = re.compile(r"[A-Za-z0-9_-]{10,128}\Z")


def _date_before(value: str, target: date, label: str) -> date:
    try:
        parsed = _date(value, label)
    except (ValueError, TypeError) as exc:
        raise DataInvalid(f"{label}: invalid date") from exc
    if parsed >= target:
        raise DataInvalid(f"{label}: target/future information is not allowed")
    return parsed


def _validate_source(entry: object, label: str) -> None:
    if not isinstance(entry, dict) or entry.get("status") != "ACCEPTED":
        raise DataInvalid(f"{label}: independent producer acceptance missing")
    ref = entry.get("producer_acceptance_ref")
    if not isinstance(ref, str) or len(ref) < 12:
        raise DataInvalid(f"{label}: producer acceptance reference missing")
    if label == "rrdb":
        if (not DRIVE_ID.fullmatch(str(entry.get("file_id", "")))
                or not HEX.fullmatch(str(entry.get("zip_sha256", "")))):
            raise DataInvalid("rrdb: unpinned CURRENT")
        return
    parts = entry.get("source_parts")
    if parts is not None:
        if label != "course_fit" or not isinstance(parts, list) or not (2 <= len(parts) <= 4):
            raise DataInvalid("course_fit: invalid multipart source")
    else:
        parts = [entry]
    for part in parts:
        if (not isinstance(part, dict)
                or not DRIVE_ID.fullmatch(str(part.get("source_ref", "")))
                or not HEX.fullmatch(str(part.get("source_sha256", "")))):
            raise DataInvalid(f"{label}: unpinned source")


def _evidence_cutoff(record: dict, target: date) -> str | None:
    """Return eligible cutoff; malformed VERIFIED records fail closed."""
    if record.get("schema_version") != PRODUCER_EVIDENCE_SCHEMA:
        raise DataInvalid("unrecognized producer-evidence schema")
    if record.get("status") != "VERIFIED":
        return None
    completion = record.get("completion_evidence")
    if not isinstance(completion, dict):
        raise DataInvalid("missing producer completion evidence")
    cutoff = completion.get("required_completed_through")
    day = _date_before(cutoff, target, "producer cutoff")
    if (completion.get("status") != "PASS"
            or completion.get("source") not in ("DEDICATED_JRDB_RESULT_OPERATION", "DEDICATED_DATA_OPERATIONS")
            or not isinstance(completion.get("reference"), str)
            or len(completion["reference"]) < 8):
        raise DataInvalid("unverified completed-race cutoff")
    for label in ("analysis", "rrdb", "course_fit", "race_lap"):
        _validate_source(record.get(label), label)
    sed = record.get("finalized_sed")
    if not isinstance(sed, list) or not sed:
        raise DataInvalid("finalized SED delivery missing from VERIFIED evidence")
    sed_dates = set()
    for item in sed:
        if not isinstance(item, dict):
            raise DataInvalid("malformed finalized SED receipt")
        observed = _date_before(item.get("date"), target, "finalized SED date")
        if observed in sed_dates:
            raise DataInvalid("duplicate finalized SED date")
        sed_dates.add(observed)
        if (not DRIVE_ID.fullmatch(str(item.get("source_ref", "")))
                or not HEX.fullmatch(str(item.get("source_sha256", "")))):
            raise DataInvalid("finalized SED lacks immutable file identity")
    if max(sed_dates) != day:
        raise DataInvalid("finalized SED does not reach authoritative cutoff")
    return day.isoformat()


def select_producer_evidence(repo_root: Path, target_date: str) -> tuple[Path, str, str] | None:
    target = date.fromisoformat(target_date)
    directory = repo_root / BASE / "producer-evidence"
    if not directory.is_dir():
        return None
    records = []
    for path in sorted(directory.glob("*.json")):
        if path.is_symlink():
            raise DataInvalid("producer-evidence symlink is forbidden")
        try:
            record = _load(path)
            cutoff = _evidence_cutoff(record, target)
        except (OSError, ValueError) as exc:
            if isinstance(exc, DataInvalid):
                raise
            raise DataInvalid(f"invalid producer-evidence document: {path.name}") from exc
        if cutoff is None:
            continue
        digest = _canonical_receipt(path, repo_root)
        records.append((cutoff, digest, path))
    if not records:
        return None
    newest = max(item[0] for item in records)
    latest = [item for item in records if item[0] == newest]
    if len(latest) != 1:
        raise DataInvalid("ambiguous latest VERIFIED producer evidence; explicit reconciliation required")
    cutoff, digest, path = latest[0]
    return path, digest, cutoff


def _ready_day(repo_root: Path, target_date: str) -> bool:
    root = repo_root / DAILY / target_date.replace("-", "") / "v056_day"
    if not root.exists() and not root.is_symlink():
        return False
    if root.is_symlink() or not root.is_dir():
        raise DataInvalid("immutable forward T1 target is unsafe")
    op = root / "operation_handoff.json"
    manifest = root / "v056/authoring_bundle/manifest.json"
    if not op.is_file() or not manifest.is_file():
        raise DataInvalid("partial forward T1 target exists; do not overwrite")
    handoff = _load(op)
    authored = _load(manifest)
    if (handoff.get("target_date") != target_date
            or handoff.get("status") != "READY_FOR_V056_AUTHORING"
            or handoff.get("execution_mode") != "FORWARD"
            or handoff.get("result_opened") is not False
            or authored.get("status") != "READY_FOR_LLM_RACE_BY_RACE_REVIEW"
            or not (root / "v056/session.json").is_file()):
        raise DataInvalid("existing forward T1 is not an accepted immutable READY result")
    return True


def plan(repo_root: Path, target_date: str) -> dict:
    try:
        target = date.fromisoformat(target_date)
    except (ValueError, TypeError) as exc:
        raise DataInvalid("target_date must be a valid YYYY-MM-DD") from exc
    if target.isoformat() != target_date:
        raise DataInvalid("noncanonical target_date")
    if _ready_day(repo_root, target_date):
        return {"status": "ALREADY_READY", "target_date": target_date,
                "needs_acceptance": False, "producer_evidence_path": ""}
    evidence = select_producer_evidence(repo_root, target_date)
    try:
        generation_path, generation, digest = select_generation_set(repo_root, target_date)
        cutoff = generation["completion_evidence"]["required_completed_through"]
    except OrchestrationMissing:
        generation_path, generation, digest, cutoff = None, None, None, None
    if evidence and cutoff == evidence[2]:
        if generation.get("producer_evidence_sha256") != evidence[1]:
            raise DataInvalid("same-cutoff accepted generation and VERIFIED evidence disagree")
    if generation_path and (not evidence or cutoff >= evidence[2]):
        return {
            "status": "ACCEPTED_REUSE", "target_date": target_date,
            "needs_acceptance": False, "producer_evidence_path": "",
            "generation_set_path": generation_path.resolve().relative_to(repo_root.resolve()).as_posix(),
            "generation_set_sha256": digest, "cutoff": cutoff,
        }
    if evidence:
        return {
            "status": "ACCEPTANCE_REQUIRED", "target_date": target_date,
            "needs_acceptance": True,
            "producer_evidence_path": evidence[0].resolve().relative_to(repo_root.resolve()).as_posix(),
            "producer_evidence_sha256": evidence[1], "cutoff": evidence[2],
        }
    raise OrchestrationMissing(
        "neither an eligible accepted generation-set nor a committed VERIFIED "
        "producer-evidence record exists; resolve exact producer CURRENT receipts first"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = plan(args.repo_root, args.target_date)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main, "FORWARD_T1_BOOTSTRAP"))
