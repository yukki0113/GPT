#!/usr/bin/env python3
"""Build one reusable forward generation-set acceptance from verified producer data."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from racenote_forward_errors import DataInvalid, OrchestrationMissing, run_cli
from jrdb_race_lap_forward_current import validate as validate_lap
from racenote_forward_source_acceptance import (
    GENERATION_SCHEMA,
    PRODUCER_EVIDENCE_SCHEMA,
    HEX,
    _canonical_receipt,
    _course_fit,
    _date,
    _inspect_analysis,
    _inspect_rrdb,
    _load,
    _sha,
)


def _source_entry(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label}: producer evidence missing")
    if not isinstance(value.get("producer_acceptance_ref"), str) or len(value["producer_acceptance_ref"]) < 12:
        raise ValueError(f"{label}: producer acceptance reference missing")
    return value


def _source_identity(entry: dict, label: str) -> dict:
    parts = entry.get("source_parts")
    if parts is not None:
        if label != "course_fit" or not isinstance(parts, list) or not parts:
            raise ValueError(f"{label}: unsupported multipart source")
        checked = []
        for part in parts:
            if not isinstance(part, dict):
                raise ValueError(f"{label}: invalid source part")
            fid, digest = part.get("source_ref"), part.get("source_sha256")
            if not isinstance(fid, str) or len(fid) < 10 or not HEX.fullmatch(str(digest)):
                raise ValueError(f"{label}: unpinned source part")
            checked.append({
                "source_ref": fid,
                "source_sha256": digest,
                "archive_format": part.get("archive_format", "zip"),
            })
        return {"source_parts": checked}
    fid, digest = entry.get("source_ref"), entry.get("source_sha256")
    if not isinstance(fid, str) or len(fid) < 10 or not HEX.fullmatch(str(digest)):
        raise ValueError(f"{label}: unpinned source")
    return {
        "source_ref": fid,
        "source_sha256": digest,
        "archive_format": entry.get("archive_format", "zip"),
    }


def _course_fit_entry(root: Path, evidence: dict, cutoff: str) -> dict:
    root = root.resolve()
    if not root.is_dir() or any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("course_fit: invalid materialized root")
    assets = {
        path.relative_to(root).as_posix(): _sha(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() != "manifest.json"
    }
    if "fit/research/candidate_fit_view.parquet" not in assets:
        raise ValueError("course_fit: prediction view missing")
    mode = evidence.get("manifest_mode", "accepted_asset_manifest")
    generation = evidence.get("generation_id")
    as_of = evidence.get("as_of")
    if not isinstance(generation, str) or not generation:
        raise ValueError("course_fit: generation_id missing from producer evidence")
    _date(as_of, "course_fit as_of")
    if mode == "native":
        manifest = root / "manifest.json"
        if not manifest.is_file():
            raise ValueError("course_fit: native manifest missing")
        manifest_sha = _sha(manifest)
    elif mode == "accepted_asset_manifest":
        canonical = json.dumps(assets, sort_keys=True, separators=(",", ":")).encode("utf-8")
        manifest_sha = hashlib.sha256(canonical).hexdigest()
    else:
        raise ValueError("course_fit: unsupported manifest mode")
    accepted = {
        **evidence,
        "status": "ACCEPTED",
        "generation_id": generation,
        "manifest_mode": mode,
        "manifest_sha256": manifest_sha,
        "as_of": as_of,
        "assets": assets,
    }
    _course_fit(root, accepted, (dt.date.fromisoformat(cutoff) + dt.timedelta(days=1)).isoformat())
    return accepted


def build_generation_set(
    evidence_path: Path,
    *,
    repo_root: Path,
    materialization_receipt: Path,
    analysis_root: Path,
    rrdb_root: Path,
    rrdb_zip: Path,
    rrdb_receipt: Path,
    course_fit_root: Path,
    race_lap_root: Path,
) -> dict[str, Any]:
    if not evidence_path.is_file():
        raise OrchestrationMissing("reviewed producer evidence has not been committed")
    evidence_sha = _canonical_receipt(evidence_path, repo_root)
    evidence = _load(evidence_path)
    if (evidence.get("schema_version") != PRODUCER_EVIDENCE_SCHEMA
            or evidence.get("status") != "VERIFIED"):
        raise DataInvalid("producer evidence is not VERIFIED")
    completion = evidence.get("completion_evidence")
    if (not isinstance(completion, dict)
            or completion.get("status") != "PASS"
            or completion.get("source") not in ("DEDICATED_JRDB_RESULT_OPERATION", "DEDICATED_DATA_OPERATIONS")
            or not isinstance(completion.get("reference"), str)
            or len(completion["reference"]) < 8):
        raise OrchestrationMissing("authoritative completed-race acceptance is missing")
    cutoff = _date(completion.get("required_completed_through"), "completion cutoff").isoformat()

    materialized = _load(materialization_receipt)
    if (materialized.get("schema_version") != "racenote-forward-materialization-v2"
            or materialized.get("status") != "MATERIALIZED"
            or materialized.get("acceptance_sha256") != evidence_sha):
        raise ValueError("materialization is not bound to producer evidence")

    # Source pinning is the T1 acceptance boundary. Cross-generation equality
    # of all finalized SED fields is NOT an acceptance prerequisite: producer
    # revisions and differing null/sentinel representations must not block
    # an otherwise safe, as-of-sealed forward reader.
    expected_sed = evidence.get("finalized_sed")
    measured_sed = materialized.get("finalized_sed")
    if not isinstance(expected_sed, list) or not expected_sed:
        raise OrchestrationMissing("producer evidence has no finalized SED delivery")
    if not isinstance(measured_sed, list) or len(measured_sed) != len(expected_sed):
        raise DataInvalid("materialized finalized SED sources do not match evidence")
    def sed_index(rows: list, label: str) -> dict:
        indexed = {}
        for row in rows:
            if not isinstance(row, dict):
                raise DataInvalid(f"{label}: malformed finalized SED")
            day = _date(row.get("date"), f"{label}: date").isoformat()
            fid = row.get("source_ref")
            digest = row.get("source_sha256")
            if (day in indexed or not isinstance(fid, str) or len(fid) < 10
                    or not HEX.fullmatch(str(digest))):
                raise DataInvalid(f"{label}: invalid or duplicate finalized SED source")
            indexed[day] = (fid, digest)
        return indexed
    expected_sed_index = sed_index(expected_sed, "producer evidence")
    measured_sed_index = sed_index(measured_sed, "materialization")
    if expected_sed_index != measured_sed_index:
        raise DataInvalid("finalized SED file IDs or SHA differ from verified producer evidence")
    expected_dates = sorted(expected_sed_index)
    if max(expected_dates) != cutoff:
        raise DataInvalid("finalized SED coverage does not reach completion cutoff")
    source_receipt_sha = _sha(materialization_receipt)

    analysis = _inspect_analysis(analysis_root)
    rrdb = _inspect_rrdb(rrdb_root, rrdb_zip, rrdb_receipt)
    if _date(analysis["coverage_through"], "analysis coverage") < _date(cutoff, "cutoff"):
        raise ValueError("analysis coverage is stale")
    if _date(rrdb["coverage_through"], "rrdb coverage") < _date(cutoff, "cutoff"):
        raise ValueError("rrdb coverage is stale")

    source_entries = {
        name: _source_entry(evidence.get(name), name)
        for name in ("analysis", "rrdb", "course_fit", "race_lap")
    }
    if rrdb["file_id"] != source_entries["rrdb"].get("file_id"):
        raise ValueError("rrdb producer source file id mismatch")
    if rrdb["zip_sha256"] != source_entries["rrdb"].get("zip_sha256"):
        raise ValueError("rrdb producer transport SHA mismatch")

    course_fit = _course_fit_entry(course_fit_root, source_entries["course_fit"], cutoff)
    lap_manifest = race_lap_root / "manifest.json"
    lap_parquet = race_lap_root / "race_lap.parquet"
    synthetic_target = (dt.date.fromisoformat(cutoff) + dt.timedelta(days=1)).isoformat()
    lap = validate_lap(lap_parquet, lap_manifest, synthetic_target, cutoff)
    lap_entry = {
        **source_entries["race_lap"],
        "status": "ACCEPTED",
        "generation_id": lap["generation_id"],
        "manifest_sha256": _sha(lap_manifest),
        "parquet_sha256": _sha(lap_parquet),
        "period_to": lap["race_lap_period_to"],
    }

    analysis_entry = {
        **source_entries["analysis"],
        **_source_identity(source_entries["analysis"], "analysis"),
        "status": "ACCEPTED",
        "generation_id": analysis["generation_id"],
        "manifest_sha256": analysis["manifest_sha256"],
        "coverage_through": analysis["coverage_through"],
    }
    rrdb_entry = {
        **source_entries["rrdb"],
        "status": "ACCEPTED",
        "generation_id": rrdb["generation_id"],
        "manifest_sha256": rrdb["manifest_sha256"],
        "coverage_through": rrdb["coverage_through"],
        "file_id": rrdb["file_id"],
        "zip_sha256": rrdb["zip_sha256"],
    }
    course_fit_entry = {
        **course_fit,
        **_source_identity(source_entries["course_fit"], "course_fit"),
    }
    lap_entry.update(_source_identity(source_entries["race_lap"], "race_lap"))

    identity = {
        "cutoff": cutoff,
        "analysis": [analysis_entry["generation_id"], analysis_entry["manifest_sha256"]],
        "rrdb": [rrdb_entry["generation_id"], rrdb_entry["manifest_sha256"], rrdb_entry["zip_sha256"]],
        "course_fit": [course_fit_entry["generation_id"], course_fit_entry["manifest_sha256"]],
        "race_lap": [lap_entry["generation_id"], lap_entry["manifest_sha256"], lap_entry["parquet_sha256"]],
        "source_receipt": source_receipt_sha,
    }
    identity_sha = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    generation_set_id = f"forward-inputs-{cutoff.replace('-', '')}-{identity_sha[:12]}"
    return {
        "schema_version": GENERATION_SCHEMA,
        "status": "ACCEPTED",
        "generation_set_id": generation_set_id,
        "completion_evidence": completion,
        "producer_evidence_path": evidence_path.resolve().relative_to(repo_root.resolve()).as_posix(),
        "producer_evidence_sha256": evidence_sha,
        "producer_source_integrity": {
            "status": "VERIFIED",
            "materialization_receipt_sha256": source_receipt_sha,
            "finalized_sed_dates": expected_dates,
            "finalized_sed_file_sha256": {
                day: identity[1] for day, identity in sorted(measured_sed_index.items())
            },
            "semantic_cross_generation_comparison": "NOT_REQUIRED",
        },
        "analysis": analysis_entry,
        "rrdb": rrdb_entry,
        "course_fit": course_fit_entry,
        "race_lap": lap_entry,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--producer-evidence", type=Path, required=True)
    ap.add_argument("--repo-root", type=Path, default=Path("."))
    ap.add_argument("--materialization-receipt", type=Path, required=True)
    ap.add_argument("--analysis-root", type=Path, required=True)
    ap.add_argument("--rrdb-root", type=Path, required=True)
    ap.add_argument("--rrdb-zip", type=Path, required=True)
    ap.add_argument("--rrdb-receipt", type=Path, required=True)
    ap.add_argument("--course-fit-root", type=Path, required=True)
    ap.add_argument("--race-lap-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = build_generation_set(
        args.producer_evidence,
        repo_root=args.repo_root,
        materialization_receipt=args.materialization_receipt,
        analysis_root=args.analysis_root,
        rrdb_root=args.rrdb_root,
        rrdb_zip=args.rrdb_zip,
        rrdb_receipt=args.rrdb_receipt,
        course_fit_root=args.course_fit_root,
        race_lap_root=args.race_lap_root,
    )
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main, "GENERATION_SET_ACCEPTANCE"))
