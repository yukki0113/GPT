#!/usr/bin/env python3
"""v2 forward source acceptance; transport-agnostic, fail-closed.

All input paths are already materialized. No network, ingestion or prediction.
Producer acceptance is an independently reviewed, committed record. The caller
must supply its repository-relative path; this module binds it to git HEAD.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import re

from racenote_v056_forward_freshness import (
    _inspect_analysis, _inspect_rrdb, _date, _sha,
    ForwardFreshnessError,
)
from jrdb_race_lap_forward_current import validate as validate_lap

SCHEMA = "racenote-forward-source-acceptance-v2"
GENERATION_SCHEMA = "racenote-forward-generation-set-v1"
BINDING_SCHEMA = "racenote-forward-target-binding-v1"
PRODUCER_EVIDENCE_SCHEMA = "racenote-forward-producer-evidence-v1"
LOCK_SCHEMA = "racenote-forward-source-lock-v2"
SAFE_REF = re.compile(r"horse-racing/jrdb/forward-acceptance/[A-Za-z0-9_./-]+\.json\Z")
HEX = re.compile(r"[a-f0-9]{64}\Z")


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("acceptance must be a JSON object")
    return value


def _canonical_receipt(path: Path, repo_root: Path) -> str:
    """Prevent a self-signed local acceptance being mistaken for producer approval."""
    resolved = path.resolve()
    base = repo_root.resolve()
    if not resolved.is_relative_to(base):
        raise ValueError("acceptance must be a committed repository file")
    rel = resolved.relative_to(base).as_posix()
    if not SAFE_REF.fullmatch(rel) or ".." in Path(rel).parts:
        raise ValueError("acceptance path not in reviewed forward-acceptance directory")
    stored = subprocess.run(
        ["git", "-C", str(base), "show", f"HEAD:{rel}"],
        capture_output=True, check=True,
    ).stdout
    if stored != path.read_bytes():
        raise ValueError("acceptance differs from committed HEAD")
    return hashlib.sha256(stored).hexdigest()



def _resolve_target_acceptance(
    path: Path, repo_root: Path, target_date: str
) -> tuple[dict, dict]:
    """Resolve legacy target acceptance or a target binding to one generation set."""
    primary_sha = _canonical_receipt(path, repo_root)
    data = _load(path)
    schema = data.get("schema_version")
    if schema == SCHEMA:
        if data.get("status") != "ACCEPTED" or data.get("target_date") != target_date:
            raise ValueError("v2 producer acceptance missing or target mismatch")
        return data, {
            "mode": "legacy_target_acceptance",
            "record_sha256": primary_sha,
        }
    if schema != BINDING_SCHEMA or data.get("status") != "BOUND":
        raise ValueError("forward source record is neither accepted v2 nor target binding")
    if data.get("target_date") != target_date:
        raise ValueError("target binding date mismatch")
    generation_ref = data.get("generation_set_path")
    if (not isinstance(generation_ref, str)
            or not generation_ref.startswith("horse-racing/jrdb/forward-acceptance/generation-sets/")
            or not SAFE_REF.fullmatch(generation_ref)
            or ".." in Path(generation_ref).parts):
        raise ValueError("target binding generation_set_path is not reviewed")
    generation_path = repo_root / generation_ref
    generation_sha = _canonical_receipt(generation_path, repo_root)
    generation = _load(generation_path)
    if (generation.get("schema_version") != GENERATION_SCHEMA
            or generation.get("status") != "ACCEPTED"):
        raise ValueError("target binding generation set is not ACCEPTED")
    generation_id = generation.get("generation_set_id")
    if not isinstance(generation_id, str) or not generation_id:
        raise ValueError("generation set has no stable id")
    if data.get("generation_set_id") != generation_id:
        raise ValueError("target binding generation_set_id mismatch")
    consistency = generation.get("consumed_field_consistency")
    if (not isinstance(consistency, dict)
            or consistency.get("status") != "PASS"
            or not HEX.fullmatch(str(consistency.get("report_sha256", "")))):
        raise ValueError("generation set has no PASS consumed-field consistency evidence")
    completion = generation.get("completion_evidence")
    if not isinstance(completion, dict):
        raise ValueError("generation set completion evidence missing")
    cutoff = completion.get("required_completed_through")
    if data.get("required_completed_through") != cutoff:
        raise ValueError("target binding cutoff differs from generation set")
    if _date(cutoff, "generation-set cutoff") >= _date(target_date, "target date"):
        raise ValueError("target binding includes target/future results")
    effective = {
        "schema_version": SCHEMA,
        "status": "ACCEPTED",
        "target_date": target_date,
        "completion_evidence": completion,
        "analysis": generation.get("analysis"),
        "rrdb": generation.get("rrdb"),
        "course_fit": generation.get("course_fit"),
        "race_lap": generation.get("race_lap"),
    }
    return effective, {
        "mode": "generation_set_binding",
        "record_sha256": primary_sha,
        "generation_set_id": generation_id,
        "generation_set_sha256": generation_sha,
        "generation_set_path": generation_ref,
        "consumed_field_consistency": consistency,
    }


def _resolve_materialization_record(path: Path, repo_root: Path) -> tuple[dict, dict]:
    """Resolve any reviewed record that is allowed to name transport bytes."""
    primary_sha = _canonical_receipt(path, repo_root)
    data = _load(path)
    schema = data.get("schema_version")
    if schema == BINDING_SCHEMA:
        target = data.get("target_date")
        if not isinstance(target, str):
            raise ValueError("target binding has no target_date")
        return _resolve_target_acceptance(path, repo_root, target)
    allowed = {
        SCHEMA: "ACCEPTED",
        GENERATION_SCHEMA: "ACCEPTED",
        PRODUCER_EVIDENCE_SCHEMA: "VERIFIED",
    }
    expected_status = allowed.get(schema)
    if expected_status is None or data.get("status") != expected_status:
        raise ValueError("unaccepted forward source declaration")
    return data, {
        "mode": str(schema),
        "record_sha256": primary_sha,
        "generation_set_id": data.get("generation_set_id"),
    }

def _expected(entry: object, label: str) -> dict:
    if not isinstance(entry, dict) or entry.get("status") != "ACCEPTED":
        raise ValueError(f"{label}: accepted producer receipt missing")
    if not isinstance(entry.get("producer_acceptance_ref"), str) or len(entry["producer_acceptance_ref"]) < 12:
        raise ValueError(f"{label}: independent producer reference missing")
    for field in ("generation_id", "manifest_sha256"):
        value = entry.get(field)
        if field.endswith("sha256") and (not isinstance(value, str) or not HEX.fullmatch(value)):
            raise ValueError(f"{label}: invalid {field}")
        if field == "generation_id" and (not isinstance(value, str) or not value):
            raise ValueError(f"{label}: missing generation")
    return entry


def _match(actual: dict, accepted: dict, keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        if str(actual.get(key)) != str(accepted.get(key)):
            raise ValueError(f"{label}: {key} differs from accepted producer generation")


def _course_fit(root: Path, accepted: dict, target_date: str) -> dict:
    """Validate all published Course Fit files; support legacy manifestless ZIP."""
    as_of = accepted.get("as_of")
    if _date(as_of, "course_fit as_of") >= _date(target_date, "target"):
        raise ValueError("course_fit: target/future leakage")
    assets = accepted.get("assets")
    if not isinstance(assets, dict) or not assets:
        raise ValueError("course_fit: missing independently accepted asset hashes")
    if "fit/research/candidate_fit_view.parquet" not in assets:
        raise ValueError("course_fit: prediction input not in accepted asset manifest")
    root = root.resolve()
    manifest_path = root / "manifest.json"
    has_manifest = manifest_path.is_file()
    mode = accepted.get("manifest_mode", "native")
    if has_manifest:
        if mode != "native":
            raise ValueError("course_fit: source/manifest mode mismatch")
        manifest = _load(manifest_path)
        if (manifest.get("validation_status") != "PASS"
                or manifest.get("as_of") != as_of
                or manifest.get("generation_id") != accepted.get("generation_id")):
            raise ValueError("course_fit: manifest status, as-of or generation mismatch")
        manifest_sha = _sha(manifest_path)
    elif mode == "accepted_asset_manifest":
        # Legacy producer ZIP had no machine-readable CURRENT manifest.
        # The independently committed accepted asset list becomes the binding.
        canonical = json.dumps(assets, sort_keys=True, separators=(",", ":")).encode("utf-8")
        manifest_sha = hashlib.sha256(canonical).hexdigest()
    else:
        raise ValueError("course_fit: neither native manifest nor accepted asset manifest")
    if manifest_sha != accepted.get("manifest_sha256"):
        raise ValueError("course_fit: manifest digest differs from producer receipt")
    actual_files = {
        file.relative_to(root).as_posix() for file in root.rglob("*") if file.is_file()
    }
    if actual_files != set(assets) | ({"manifest.json"} if has_manifest else set()):
        raise ValueError("course_fit: unapproved or missing staged asset")
    if any(file.is_symlink() for file in root.rglob("*")):
        raise ValueError("course_fit: symlink asset")
    for name, digest in assets.items():
        relative = Path(name)
        if (not name or relative.is_absolute() or ".." in relative.parts or
                not isinstance(digest, str) or not HEX.fullmatch(digest)):
            raise ValueError("course_fit: unsafe asset")
        file = (root / relative).resolve()
        if not file.is_relative_to(root) or not file.is_file() or _sha(file) != digest:
            raise ValueError(f"course_fit: asset digest mismatch: {name}")
    return {"generation_id": accepted["generation_id"], "manifest_sha256": manifest_sha,
            "manifest_mode": mode, "as_of": as_of, "assets": assets}


def accept(
    acceptance_path: Path, *, repo_root: Path, target_date: str,
    analysis_root: Path, rrdb_root: Path, rrdb_zip: Path, rrdb_receipt: Path,
    course_fit_root: Path, race_lap_current_bundle: Path,
    paci_sha256: str, output: Path,
) -> dict:
    a, contract = _resolve_target_acceptance(acceptance_path, repo_root, target_date)
    committed_digest = contract["record_sha256"]
    completion = a.get("completion_evidence")
    if (not isinstance(completion, dict) or completion.get("status") != "PASS"
            or completion.get("source") not in ("DEDICATED_JRDB_RESULT_OPERATION", "DEDICATED_DATA_OPERATIONS")
            or not isinstance(completion.get("reference"), str)
            or len(completion["reference"]) < 8):
        raise ValueError("verified completed-results source missing")
    try:
        verified = datetime.fromisoformat(completion["verified_at_utc"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError) as exc:
        raise ValueError("missing completed-results verification time") from exc
    if verified.tzinfo is None or verified.astimezone(timezone.utc) > datetime.now(timezone.utc):
        raise ValueError("invalid completed-results verification time")
    cutoff = _date(completion.get("required_completed_through"), "completion cutoff")
    target = _date(target_date, "target date")
    if cutoff >= target:
        raise ValueError("cutoff includes target day")
    if not isinstance(paci_sha256, str) or not HEX.fullmatch(paci_sha256):
        raise ValueError("invalid PACI content hash")
    expected = {name: _expected(a.get(name), name) for name in ("analysis", "rrdb", "course_fit", "race_lap")}
    measured_analysis = _inspect_analysis(analysis_root)
    measured_rrdb = _inspect_rrdb(rrdb_root, rrdb_zip, rrdb_receipt)
    for key, actual in (("analysis", measured_analysis), ("rrdb", measured_rrdb)):
        _match(actual, expected[key], ("generation_id", "manifest_sha256", "coverage_through"), key)
        if not cutoff <= _date(actual["coverage_through"], key + " coverage") < target:
            raise ValueError(key + ": stale or future coverage")
    _match(measured_rrdb, expected["rrdb"], ("zip_sha256", "file_id"), "rrdb")
    # Only approved source identities, never an arbitrary local copy.
    for name in ("analysis", "course_fit", "race_lap"):
        entry = expected[name]
        if entry.get("source_mode") not in ("drive_current", "data_storage_handoff"):
            raise ValueError(name + ": unsupported source mode")
        parts = entry.get("source_parts")
        if parts is not None:
            if name != "course_fit" or not isinstance(parts, list) or not (2 <= len(parts) <= 4):
                raise ValueError(name + ": unexpected multipart source")
            sources = parts
        else:
            sources = [entry]
        ids = set()
        for source in sources:
            if not isinstance(source, dict) or not source.get("source_ref") or not source.get("source_sha256"):
                raise ValueError(name + ": source provenance missing")
            if not HEX.fullmatch(str(source["source_sha256"])):
                raise ValueError(name + ": source digest invalid")
            if source["source_ref"] in ids:
                raise ValueError(name + ": repeated multipart source")
            ids.add(source["source_ref"])
    course_fit = _course_fit(course_fit_root, expected["course_fit"], target_date)
    lap_root = race_lap_current_bundle
    lap_manifest = lap_root / "manifest.json"
    lap_parquet = lap_root / "race_lap.parquet"
    lap = validate_lap(lap_parquet, lap_manifest, target_date, cutoff.isoformat())
    lap_actual = {
        "generation_id": lap["generation_id"],
        "manifest_sha256": _sha(lap_manifest),
        "parquet_sha256": _sha(lap_parquet),
        "period_to": lap["race_lap_period_to"],
    }
    _match(lap_actual, expected["race_lap"], tuple(lap_actual), "race_lap")
    # All source transport hashes are independently accepted and must be checked by
    # the materializer before this gate. This lock alone cannot attest acquisition.
    receipt = {
        "schema_version": LOCK_SCHEMA, "status": "READY_FOR_T1",
        "target_date": target_date, "required_completed_through": cutoff.isoformat(),
        "acceptance_sha256": committed_digest, "paci_sha256": paci_sha256,
        "source_contract_mode": contract["mode"],
        "generation_set_id": contract.get("generation_set_id"),
        "generation_set_sha256": contract.get("generation_set_sha256"),
        "completion_evidence": completion,
        "analysis": {**measured_analysis, "source_mode": expected["analysis"]["source_mode"],
                     "source_ref": expected["analysis"]["source_ref"]},
        "rrdb": measured_rrdb,
        "course_fit": course_fit,
        "race_lap": lap_actual,
        "source_provenance": {
            name: {
                "source_mode": expected[name]["source_mode"],
                "producer_acceptance_ref": expected[name]["producer_acceptance_ref"],
                **({"source_parts": expected[name]["source_parts"]}
                   if expected[name].get("source_parts") is not None else {
                       "source_ref": expected[name]["source_ref"],
                       "source_sha256": expected[name]["source_sha256"],
                       "archive_format": expected[name].get("archive_format", "zip"),
                   }),
            }
            for name in ("analysis", "course_fit", "race_lap")
        },
    }
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
