#!/usr/bin/env python3
"""A05: fail-closed preflight binding dedicated Analysis/RRDB acceptance to real inputs.

No Drive API, no freshness inference from wall clock, no rebuild/re-download.
An owner-supplied acceptance from dedicated operations names the last completed
race day and exact accepted bytes. This module checks the already materialized
inputs before a FORWARD RaceNote T1 may be built.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from jrdb_analysis_parquet_current import resolve_current as resolve_analysis_current

SCHEMA = "racenote-forward-analysis-rrdb-acceptance-v1"
RESULT_SCHEMA = "racenote-forward-analysis-rrdb-freshness-v1"
HEX = re.compile(r"[0-9a-f]{64}\Z")
GEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{3,127}\Z")
ID = re.compile(r"[1-9][0-9]{6,19}\Z")
DRIVE_ID = re.compile(r"[A-Za-z0-9_-]{10,128}\Z")


class ForwardFreshnessError(ValueError):
    """Input is valid-looking but is not accepted/current enough for the target."""


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ForwardFreshnessError(f"unreadable freshness input: {path}") from exc
    if not isinstance(data, dict):
        raise ForwardFreshnessError("freshness input must be a JSON object")
    return data


def _date(text: object, name: str) -> date:
    if not isinstance(text, str):
        raise ForwardFreshnessError(f"{name} must be ISO YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ForwardFreshnessError(f"invalid {name}") from exc
    if parsed.isoformat() != text:
        raise ForwardFreshnessError(f"{name} must be ISO YYYY-MM-DD")
    return parsed


def _race_day(value: object) -> str:
    if isinstance(value, (date, datetime)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    text = str(value)
    if re.fullmatch(r"20\d{6}", text):
        return date(int(text[:4]), int(text[4:6]), int(text[6:8])).isoformat()
    if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", text):
        return _date(text, "Analysis max_race_date").isoformat()
    raise ForwardFreshnessError(f"unsupported Analysis race_date: {text!r}")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha_approved(value: object, key: str) -> str:
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ForwardFreshnessError(f"invalid {key}")
    return value


def _inspect_analysis(root: Path) -> dict[str, Any]:
    """Use canonical resolver for manifest+all Parquet SHA, query actual race-date extent."""
    report = resolve_analysis_current(Path(root))
    manifest_path = Path(report["manifest"])
    manifest = _read(manifest_path)
    partitions = manifest["fact_table"]["partitions"]
    paths = [str((Path(root) / part["relative_path"]).resolve()) for part in partitions]
    try:
        import duckdb
    except ImportError as exc:
        raise ForwardFreshnessError("DuckDB required for Analysis coverage validation") from exc
    conn = duckdb.connect(":memory:")
    try:
        r = conn.execute(
            "SELECT max(race_date), count(*) FROM read_parquet(?, union_by_name=true)",
            [paths],
        ).fetchone()
    finally:
        conn.close()
    if not r or r[0] is None or int(r[1]) != report["rows"]:
        raise ForwardFreshnessError("Analysis actual row count/coverage mismatch")
    return {
        "generation_id": report["generation_id"],
        "manifest_sha256": _sha(manifest_path),
        "coverage_through": _race_day(r[0]),
        "rows": int(r[1]),
        "storage": "ANALYSIS_PARQUET_GENERATION",
    }


def _inspect_rrdb(root: Path, zip_path: Path, receipt_path: Path) -> dict[str, Any]:
    """Bind mutable RRDB ZIP transport SHA to extracted immutable manifest generation."""
    receipt = _read(receipt_path)
    if (receipt.get("schema_version") != 1
            or receipt.get("transport") != "public_google_drive_current_verified_at_download"
            or receipt.get("artifact_id") != "rrdb_current"
            or receipt.get("verified") is not True
            or not DRIVE_ID.fullmatch(str(receipt.get("file_id", "")))):
        raise ForwardFreshnessError("RRDB download receipt is not verified CURRENT")
    zip_path = Path(zip_path)
    if (not zip_path.is_file()
            or zip_path.stat().st_size != receipt.get("size")
            or _sha(zip_path) != _sha_approved(receipt.get("sha256"), "rrdb receipt.sha256")):
        raise ForwardFreshnessError("RRDB downloaded ZIP does not match transport receipt")
    root = Path(root)
    pointer = _read(root / "current.json")
    if pointer.get("status") != "CURRENT" or pointer.get("artifact_type") != "jrdb_postrace_review":
        raise ForwardFreshnessError("RRDB current pointer invalid")
    manifest_ref = pointer.get("manifest")
    if not isinstance(manifest_ref, str) or Path(manifest_ref).is_absolute() or ".." in Path(manifest_ref).parts:
        raise ForwardFreshnessError("RRDB current manifest path unsafe")
    manifest_path = (root / manifest_ref).resolve()
    if not manifest_path.is_relative_to(root.resolve()):
        raise ForwardFreshnessError("RRDB manifest escapes root")
    manifest = _read(manifest_path)
    if (manifest.get("validation_status") != "PASS"
            or manifest.get("generation_id") != pointer.get("generation_id")):
        raise ForwardFreshnessError("RRDB generation manifest invalid")
    return {
        "generation_id": manifest["generation_id"],
        "manifest_sha256": _sha(manifest_path),
        "coverage_through": _date(manifest.get("period_to"), "RRDB period_to").isoformat(),
        "period_from": manifest.get("period_from"),
        "zip_sha256": receipt["sha256"],
        "file_id": receipt["file_id"],
        "storage": "DRIVE_RRDB_CURRENT_VERIFIED_ZIP",
    }


def validate(
    acceptance_path: Path, *,
    target_date: str, analysis_root: Path, rrdb_root: Path,
    rrdb_zip: Path, rrdb_receipt: Path,
    analysis_artifact_id: str, analysis_generation_id: str,
) -> dict[str, Any]:
    acceptance = _read(acceptance_path)
    if acceptance.get("schema_version") != SCHEMA or acceptance.get("status") != "ACCEPTED":
        raise ForwardFreshnessError("missing accepted dedicated-operations freshness receipt")
    if acceptance.get("target_date") != target_date:
        raise ForwardFreshnessError("freshness acceptance target_date mismatch")
    target = _date(target_date, "target_date")
    required = _date(acceptance.get("required_completed_through"), "required_completed_through")
    if required >= target:
        raise ForwardFreshnessError("required completed date must precede target")
    authority = acceptance.get("completion_evidence")
    if (not isinstance(authority, dict)
            or authority.get("status") != "PASS"
            or authority.get("source") not in ("DEDICATED_JRDB_RESULT_OPERATION", "DEDICATED_DATA_OPERATIONS")
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{7,255}", str(authority.get("reference", "")))):
        raise ForwardFreshnessError("missing verified latest-completed-race source")
    observed = authority.get("verified_at_utc")
    try:
        when = datetime.fromisoformat(str(observed).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ForwardFreshnessError("invalid completion verification time") from exc
    if when.tzinfo is None or when.astimezone(timezone.utc) > datetime.now(timezone.utc):
        raise ForwardFreshnessError("completion verification time is missing or future")
    if not ID.fullmatch(str(analysis_artifact_id)) or not GEN.fullmatch(analysis_generation_id):
        raise ForwardFreshnessError("invalid Analysis artifact identity")
    analysis_expected = acceptance.get("analysis")
    rrdb_expected = acceptance.get("rrdb")
    if not isinstance(analysis_expected, dict) or not isinstance(rrdb_expected, dict):
        raise ForwardFreshnessError("both dedicated Analysis and RRDB receipts are required")
    if (analysis_expected.get("status") != "ACCEPTED"
            or rrdb_expected.get("status") != "ACCEPTED"):
        raise ForwardFreshnessError("one dedicated operation has not accepted its generation")
    if (str(analysis_expected.get("artifact_id")) != str(analysis_artifact_id)
            or analysis_expected.get("generation_id") != analysis_generation_id):
        raise ForwardFreshnessError("Analysis receipt does not match requested artifact/generation")
    if not DRIVE_ID.fullmatch(str(rrdb_expected.get("file_id", ""))):
        raise ForwardFreshnessError("invalid RRDB acceptance file identity")
    expected = {
        "analysis": analysis_expected,
        "rrdb": rrdb_expected,
    }
    for label, att in expected.items():
        if not isinstance(att.get("acceptance_reference"), str) or len(att["acceptance_reference"]) < 8:
            raise ForwardFreshnessError(f"{label} has no dedicated operation evidence reference")
        _sha_approved(att.get("manifest_sha256"), f"{label} manifest_sha256")
        cutoff = _date(att.get("coverage_through"), f"{label} accepted coverage_through")
        if not required <= cutoff < target:
            raise ForwardFreshnessError(f"{label} accepted coverage insufficient or future-contaminated")
    _sha_approved(rrdb_expected.get("zip_sha256"), "RRDB accepted ZIP sha256")
    measured = {
        "analysis": _inspect_analysis(analysis_root),
        "rrdb": _inspect_rrdb(rrdb_root, rrdb_zip, rrdb_receipt),
    }
    for label, actual in measured.items():
        att = expected[label]
        for field in ("generation_id", "manifest_sha256", "coverage_through"):
            if actual[field] != att.get(field):
                raise ForwardFreshnessError(f"{label} {field} does not match accepted/current input")
        if not required <= _date(actual["coverage_through"], label+" actual coverage") < target:
            raise ForwardFreshnessError(f"{label} actual coverage is stale or includes target")
    if measured["analysis"]["generation_id"] != analysis_generation_id:
        raise ForwardFreshnessError("Analysis current pointer differs from selected generation")
    if (measured["rrdb"]["zip_sha256"] != rrdb_expected["zip_sha256"]
            or measured["rrdb"]["file_id"] != rrdb_expected["file_id"]):
        raise ForwardFreshnessError("RRDB current transport differs from accepted generation")
    return {
        "schema_version": RESULT_SCHEMA,
        "status": "PASS",
        "target_date": target_date,
        "required_completed_through": required.isoformat(),
        "completion_evidence": authority,
        "acceptance_sha256": _sha(acceptance_path),
        "analysis": {**measured["analysis"], "artifact_id": str(analysis_artifact_id),
                     "acceptance_reference": analysis_expected["acceptance_reference"]},
        "rrdb": {**measured["rrdb"],
                 "acceptance_reference": rrdb_expected["acceptance_reference"]},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--acceptance", type=Path, required=True)
    ap.add_argument("--target-date", required=True)
    ap.add_argument("--analysis-root", type=Path, required=True)
    ap.add_argument("--analysis-artifact-id", required=True)
    ap.add_argument("--analysis-generation-id", required=True)
    ap.add_argument("--rrdb-root", type=Path, required=True)
    ap.add_argument("--rrdb-zip", type=Path, required=True)
    ap.add_argument("--rrdb-receipt", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    report = validate(
        args.acceptance, target_date=args.target_date,
        analysis_root=args.analysis_root, analysis_artifact_id=args.analysis_artifact_id,
        analysis_generation_id=args.analysis_generation_id,
        rrdb_root=args.rrdb_root, rrdb_zip=args.rrdb_zip,
        rrdb_receipt=args.rrdb_receipt,
    )
    if args.output.exists():
        raise FileExistsError("freshness report must not overwrite accepted evidence")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)+"\n",
                           encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
