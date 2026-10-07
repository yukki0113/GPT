#!/usr/bin/env python3
"""Seal one clean RaceNote preparation and derive a separate v0.5 normal Reader."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from racenote_reader_v050 import DEFAULT_BINDING, VERSION as V050, load_binding, transform, validate_policy_binding
from racenote_reader_v051 import VERSION as V051
from racenote_reader_v052 import VERSION as V052
from racenote_save_venue_batch_v046 import LOGIC as V046, RRDB, load_clean

SESSION_VERSION = "racenote-ab-session-0.1"
MANIFEST_VERSION = "racenote-ab-reader-manifest-0.1"
DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "docs" / "racenote" / "research-work" / "results" / "stage_c" / "reader_feature_policy_v0_5_candidate.json"


def encoded(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value) + b"\n")


def read_json(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"expected JSON object: {path}")
    return result


def race_roster(readers: dict) -> list[dict[str, Any]]:
    rows = []
    for (venue, race_no), item in sorted(readers.items()):
        horse_nos = [int(h["basic"]["horse_no"]) for h in item["reader"]["horses"]]
        if not horse_nos or len(horse_nos) != len(set(horse_nos)):
            raise ValueError(f"invalid horse roster: {venue}{race_no}R")
        rows.append({
            "venue": venue,
            "race_no": race_no,
            "file": item["file"],
            "horse_nos": sorted(horse_nos),
        })
    return rows


def session_identity_fields(session: dict[str, Any]) -> dict[str, Any]:
    return {
        key: session[key]
        for key in (
            "ab_session_version", "selection_id", "target_date", "base_main_sha",
            "source_prepare_request_identity", "clean_reader_manifest_sha256",
            "race_roster", "expected_venues", "rrdb_contract", "v050_binding_sha256",
            "stage_c_policy_sha256",
        )
    } | ({
        "v051_enabled": session["v051_enabled"],
        "v051_contract_version": session["v051_contract_version"],
    } if session.get("v051_enabled") else {})


def expected_session_id(session: dict[str, Any]) -> str:
    return "AB-" + digest(encoded(session_identity_fields(session)))[:20]


def init_session(
    prep_root: Path,
    request_path: Path,
    ab_root: Path,
    base_main_sha: str,
    binding_path: Path = DEFAULT_BINDING,
    policy_path: Path = DEFAULT_POLICY,
    include_v051: bool = False,
    pair_v051_v052: bool = False,
) -> dict[str, Any]:
    if ab_root.exists():
        raise FileExistsError(f"A/B session already exists: {ab_root}")
    if include_v051 and pair_v051_v052:
        raise ValueError("include_v051 and pair_v051_v052 are mutually exclusive")
    if len(base_main_sha) != 40 or any(c not in "0123456789abcdef" for c in base_main_sha):
        raise ValueError("base_main_sha must be a full lowercase commit SHA")
    handoff, clean_manifest, readers = load_clean(prep_root)
    if handoff.get("main_sha") != base_main_sha:
        raise ValueError("A/B base SHA must equal the clean prepare base SHA")
    if handoff.get("stripped_at_input_bind") is not True:
        raise ValueError("clean Reader input bind is not sealed")
    request_raw = request_path.read_bytes()
    request = json.loads(request_raw)
    if not isinstance(request, dict):
        raise ValueError("prepare request must be an object")
    if request.get("selection_id") != handoff["selection_id"] or request.get("target_date") != handoff["target_date"]:
        raise ValueError("prepare request identity mismatch")
    for key in ("paci_file_id", "analysis_artifact_run_id", "analysis_artifact_name", "analysis_generation_id"):
        if not request.get(key):
            raise ValueError(f"prepare request missing {key}")
    binding = load_binding(binding_path)
    validate_policy_binding(binding, read_json(policy_path))
    roster = race_roster(readers)
    expected_venues = sorted({row["venue"] for row in roster})
    clean_manifest_sha = digest((prep_root / "reader_stripped_manifest.json").read_bytes())
    if clean_manifest_sha != handoff["reader_stripped_manifest_sha256"]:
        raise ValueError("clean manifest SHA mismatch")
    original_hashes = {item["file"]: item["sha256"] for item in readers.values()}
    if original_hashes != clean_manifest.get("reader_sha256"):
        raise ValueError("original clean Reader hash set mismatch")
    session: dict[str, Any] = {
        "ab_session_version": SESSION_VERSION,
        "selection_id": handoff["selection_id"],
        "target_date": handoff["target_date"],
        "base_main_sha": base_main_sha,
        "source_prepare_request_identity": {
            "filename": request_path.name,
            "sha256": digest(request_raw),
            "paci_file_id": request["paci_file_id"],
            "analysis_artifact_run_id": request["analysis_artifact_run_id"],
            "analysis_artifact_name": request["analysis_artifact_name"],
            "analysis_generation_id": request["analysis_generation_id"],
        },
        "clean_reader_manifest_sha256": clean_manifest_sha,
        "race_roster": roster,
        "original_clean_reader_sha256": original_hashes,
        "expected_venues": expected_venues,
        "rrdb_contract": RRDB,
        "v050_binding_sha256": digest(binding_path.read_bytes()),
        "stage_c_policy_sha256": digest(policy_path.read_bytes()),
        "market_blind": True,
        "target_market_opened": False,
        "result_opened": False,
        "sibling_forecast_input_forbidden": True,
        "lane_definitions": (
            {
                "v051": {"logic_version": V051, "reader": "derived_normal_view_only"},
                "v052": {"logic_version": V052, "reader": "derived_normal_view_only"},
            }
            if pair_v051_v052
            else {
                "v046": {"logic_version": V046, "reader": "canonical_clean"},
                "v050": {"logic_version": V050, "reader": "derived_normal_view_only"},
                **({"v051": {"logic_version": V051, "reader": "derived_normal_view_only"}} if include_v051 else {}),
            }
        ),
        "v051_enabled": include_v051 or pair_v051_v052,
        "v051_contract_version": "racenote-decision-core-0.5.1" if (include_v051 or pair_v051_v052) else None,
        "v052_enabled": pair_v051_v052,
        "v052_contract_version": "racenote-decision-core-0.5.2" if pair_v051_v052 else None,
        **({"ab_profile": "v051_v052"} if pair_v051_v052 else {}),
        "source_prep_root": os.path.relpath(prep_root.resolve(), ab_root.resolve()),
        "status": "SESSION_SEALED",
    }
    session["session_id"] = expected_session_id(session)
    ab_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{ab_root.name}.build-", dir=ab_root.parent) as temp:
        staging = Path(temp)
        shared = {
            "manifest_version": MANIFEST_VERSION,
            "session_id": session["session_id"],
            "selection_id": session["selection_id"],
            "target_date": session["target_date"],
            "clean_reader_manifest_sha256": clean_manifest_sha,
            "race_roster": roster,
            "reader_sha256": original_hashes,
        }
        write_json(staging / "shared" / "reader_manifest.json", shared)
        write_json(staging / "v046" / "reader_manifest.json", {
            **shared, "logic_version": V046, "reader_reference": session["source_prep_root"] + "/reader",
        })
        derived_entries = []
        for row in roster:
            filename = row["file"]
            source = readers[(row["venue"], row["race_no"])]["reader"]
            candidate = transform(source, binding)
            normal_path = staging / "v050" / "reader" / filename
            write_json(normal_path, candidate["normal_view"])
            derived_entries.append({
                "venue": row["venue"],
                "race_no": row["race_no"],
                "original_clean_reader_filename": filename,
                "original_clean_reader_sha256": original_hashes[filename],
                "source_semantic_sha256": source["source_semantic_sha256"],
                "derived_normal_filename": filename,
                "derived_normal_sha256": digest(normal_path.read_bytes()),
                "candidate_version": V050,
                "horse_nos": row["horse_nos"],
            })
        derived_manifest = {
            "manifest_version": MANIFEST_VERSION,
            "session_id": session["session_id"],
            "selection_id": session["selection_id"],
            "target_date": session["target_date"],
            "clean_reader_manifest_sha256": clean_manifest_sha,
            "logic_version": V050,
            "model_input": "normal_view_only",
            "entries": derived_entries,
        }
        derived_path = staging / "v050" / "reader_manifest.json"
        write_json(derived_path, derived_manifest)
        session["v050_reader_manifest_sha256"] = digest(derived_path.read_bytes())
        if include_v051 or pair_v051_v052:
            v051_entries = []
            for entry in derived_entries:
                source_path = staging / "v050" / "reader" / entry["derived_normal_filename"]
                target_path = staging / "v051" / "reader" / entry["derived_normal_filename"]
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(source_path.read_bytes())
                v051_entries.append({
                    **entry,
                    "candidate_version": V051,
                    "derived_normal_sha256": digest(target_path.read_bytes()),
                })
            v051_manifest = {
                "manifest_version": MANIFEST_VERSION,
                "session_id": session["session_id"],
                "selection_id": session["selection_id"],
                "target_date": session["target_date"],
                "clean_reader_manifest_sha256": clean_manifest_sha,
                "logic_version": V051,
                "model_input": "normal_view_only",
                "projection_equivalent_to": V050,
                "entries": v051_entries,
            }
            v051_path = staging / "v051" / "reader_manifest.json"
            write_json(v051_path, v051_manifest)
            session["v051_reader_manifest_sha256"] = digest(v051_path.read_bytes())
            if pair_v051_v052:
                v052_entries = []
                for entry in derived_entries:
                    source_path = staging / "v050" / "reader" / entry["derived_normal_filename"]
                    target_path = staging / "v052" / "reader" / entry["derived_normal_filename"]
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    target_path.write_bytes(source_path.read_bytes())
                    v052_entries.append({
                        **entry,
                        "candidate_version": V052,
                        "derived_normal_sha256": digest(target_path.read_bytes()),
                    })
                v052_manifest = {
                    "manifest_version": MANIFEST_VERSION,
                    "session_id": session["session_id"],
                    "selection_id": session["selection_id"],
                    "target_date": session["target_date"],
                    "clean_reader_manifest_sha256": clean_manifest_sha,
                    "logic_version": V052,
                    "model_input": "normal_view_only",
                    "projection_equivalent_to": V050,
                    "entries": v052_entries,
                }
                v052_path = staging / "v052" / "reader_manifest.json"
                write_json(v052_path, v052_manifest)
                session["v052_reader_manifest_sha256"] = digest(v052_path.read_bytes())
        write_json(staging / "ab_session.json", session)
        staging.rename(ab_root)
    return session


def load_session(
    ab_root: Path,
    binding_path: Path = DEFAULT_BINDING,
    policy_path: Path = DEFAULT_POLICY,
) -> tuple[dict[str, Any], dict, dict]:
    session = read_json(ab_root / "ab_session.json")
    if (
        session.get("ab_session_version") != SESSION_VERSION
        or session.get("status") != "SESSION_SEALED"
        or session.get("market_blind") is not True
        or session.get("target_market_opened") is not False
        or session.get("result_opened") is not False
        or session.get("sibling_forecast_input_forbidden") is not True
        or session.get("session_id") != expected_session_id(session)
    ):
        raise ValueError("A/B session seal invalid")
    if digest(binding_path.read_bytes()) != session.get("v050_binding_sha256"):
        raise ValueError("v0.5 binding changed after session seal")
    if digest(policy_path.read_bytes()) != session.get("stage_c_policy_sha256"):
        raise ValueError("Stage C policy changed after session seal")
    prep_root = (ab_root / session["source_prep_root"]).resolve()
    handoff, manifest, readers = load_clean(prep_root)
    if (
        handoff.get("selection_id") != session["selection_id"]
        or handoff.get("target_date") != session["target_date"]
        or handoff.get("main_sha") != session["base_main_sha"]
        or handoff.get("rrdb_contract") != session["rrdb_contract"]
        or handoff.get("stripped_at_input_bind") is not True
        or handoff.get("target_market_opened") is not False
        or digest((prep_root / "reader_stripped_manifest.json").read_bytes()) != session["clean_reader_manifest_sha256"]
    ):
        raise ValueError("A/B session clean source changed")
    roster = race_roster(readers)
    if roster != session["race_roster"] or sorted({x["venue"] for x in roster}) != session["expected_venues"]:
        raise ValueError("A/B session race roster changed")
    if manifest.get("reader_sha256") != session["original_clean_reader_sha256"]:
        raise ValueError("A/B session original Reader hashes changed")
    shared = read_json(ab_root / "shared" / "reader_manifest.json")
    if shared.get("session_id") != session["session_id"] or shared.get("reader_sha256") != session["original_clean_reader_sha256"] or shared.get("race_roster") != roster:
        raise ValueError("shared Reader manifest mismatch")
    v046_manifest = read_json(ab_root / "v046" / "reader_manifest.json")
    if v046_manifest.get("logic_version") != V046 or v046_manifest.get("reader_sha256") != session["original_clean_reader_sha256"]:
        raise ValueError("v0.4.6 Reader reference mismatch")
    derived_path = ab_root / "v050" / "reader_manifest.json"
    if digest(derived_path.read_bytes()) != session["v050_reader_manifest_sha256"]:
        raise ValueError("v0.5 Reader manifest digest mismatch")
    derived = read_json(derived_path)
    if (
        derived.get("session_id") != session["session_id"]
        or derived.get("logic_version") != V050
        or derived.get("model_input") != "normal_view_only"
        or derived.get("clean_reader_manifest_sha256") != session["clean_reader_manifest_sha256"]
        or len(derived.get("entries", [])) != len(roster)
    ):
        raise ValueError("v0.5 Reader manifest identity mismatch")
    binding = load_binding(binding_path)
    validate_policy_binding(binding, read_json(policy_path))
    entries = {(x["venue"], x["race_no"]): x for x in derived["entries"]}
    if set(entries) != set(readers):
        raise ValueError("v0.5 Reader roster mismatch")
    expected_files = {x["derived_normal_filename"] for x in entries.values()}
    actual_files = {p.name for p in (ab_root / "v050" / "reader").glob("*.json")}
    if actual_files != expected_files:
        raise ValueError("v0.5 Reader file set mismatch")
    if session.get("v051_enabled"):
        if session.get("v051_contract_version") != "racenote-decision-core-0.5.1":
            raise ValueError("v0.5.1 Decision Core contract mismatch")
        if session.get("lane_definitions", {}).get("v051") != {
            "logic_version": V051, "reader": "derived_normal_view_only"
        }:
            raise ValueError("v0.5.1 lane definition mismatch")
        v051_path = ab_root / "v051" / "reader_manifest.json"
        if digest(v051_path.read_bytes()) != session.get("v051_reader_manifest_sha256"):
            raise ValueError("v0.5.1 Reader manifest digest mismatch")
        v051_manifest = read_json(v051_path)
        if (
            v051_manifest.get("session_id") != session["session_id"]
            or v051_manifest.get("logic_version") != V051
            or v051_manifest.get("model_input") != "normal_view_only"
            or v051_manifest.get("projection_equivalent_to") != V050
            or v051_manifest.get("clean_reader_manifest_sha256") != session["clean_reader_manifest_sha256"]
            or len(v051_manifest.get("entries", [])) != len(roster)
        ):
            raise ValueError("v0.5.1 Reader manifest identity mismatch")
        v051_entries = {(x["venue"], x["race_no"]): x for x in v051_manifest["entries"]}
        if set(v051_entries) != set(readers):
            raise ValueError("v0.5.1 Reader roster mismatch")
        for key, entry in v051_entries.items():
            source_entry = entries[key]
            if (
                entry.get("candidate_version") != V051
                or entry.get("original_clean_reader_filename") != source_entry["original_clean_reader_filename"]
                or entry.get("original_clean_reader_sha256") != source_entry["original_clean_reader_sha256"]
                or entry.get("source_semantic_sha256") != source_entry["source_semantic_sha256"]
                or entry.get("horse_nos") != source_entry["horse_nos"]
            ):
                raise ValueError(f"v0.5.1 Reader source binding mismatch: {key}")
            path = ab_root / "v051" / "reader" / entry["derived_normal_filename"]
            v050_path = ab_root / "v050" / "reader" / source_entry["derived_normal_filename"]
            if digest(path.read_bytes()) != entry["derived_normal_sha256"] or path.read_bytes() != v050_path.read_bytes():
                raise ValueError(f"v0.5.1 normal_view must equal v0.5.0 normal_view: {key}")
        actual_v051 = {p.name for p in (ab_root / "v051" / "reader").glob("*.json")}
        if actual_v051 != expected_files:
            raise ValueError("v0.5.1 Reader file set mismatch")
    if session.get("v052_enabled"):
        if session.get("v052_contract_version") != "racenote-decision-core-0.5.2":
            raise ValueError("v0.5.2 Decision Core contract mismatch")
        if session.get("ab_profile") != "v051_v052":
            raise ValueError("v0.5.2 session profile mismatch")
        if set(session.get("lane_definitions", {})) != {"v051", "v052"}:
            raise ValueError("v0.5.1/v0.5.2 pair must enable exactly two authoring lanes")
        if session.get("lane_definitions", {}).get("v052") != {
            "logic_version": V052, "reader": "derived_normal_view_only"
        }:
            raise ValueError("v0.5.2 lane definition mismatch")
        v052_path = ab_root / "v052" / "reader_manifest.json"
        if digest(v052_path.read_bytes()) != session.get("v052_reader_manifest_sha256"):
            raise ValueError("v0.5.2 Reader manifest digest mismatch")
        v052_manifest = read_json(v052_path)
        if (
            v052_manifest.get("session_id") != session["session_id"]
            or v052_manifest.get("logic_version") != V052
            or v052_manifest.get("model_input") != "normal_view_only"
            or v052_manifest.get("projection_equivalent_to") != V050
            or v052_manifest.get("clean_reader_manifest_sha256") != session["clean_reader_manifest_sha256"]
            or len(v052_manifest.get("entries", [])) != len(roster)
        ):
            raise ValueError("v0.5.2 Reader manifest identity mismatch")
        v052_entries = {(x["venue"], x["race_no"]): x for x in v052_manifest["entries"]}
        if set(v052_entries) != set(readers):
            raise ValueError("v0.5.2 Reader roster mismatch")
        for key, entry in v052_entries.items():
            source_entry = entries[key]
            if (
                entry.get("candidate_version") != V052
                or entry.get("original_clean_reader_filename") != source_entry["original_clean_reader_filename"]
                or entry.get("original_clean_reader_sha256") != source_entry["original_clean_reader_sha256"]
                or entry.get("source_semantic_sha256") != source_entry["source_semantic_sha256"]
                or entry.get("horse_nos") != source_entry["horse_nos"]
            ):
                raise ValueError(f"v0.5.2 Reader source binding mismatch: {key}")
            path = ab_root / "v052" / "reader" / entry["derived_normal_filename"]
            v050_path = ab_root / "v050" / "reader" / source_entry["derived_normal_filename"]
            v051_path = ab_root / "v051" / "reader" / source_entry["derived_normal_filename"]
            if (
                digest(path.read_bytes()) != entry["derived_normal_sha256"]
                or path.read_bytes() != v050_path.read_bytes()
                or path.read_bytes() != v051_path.read_bytes()
            ):
                raise ValueError(f"v0.5.2 normal_view must equal v0.5.0/v0.5.1 normal_view: {key}")
        actual_v052 = {p.name for p in (ab_root / "v052" / "reader").glob("*.json")}
        if actual_v052 != expected_files:
            raise ValueError("v0.5.2 Reader file set mismatch")

    for key, source in readers.items():
        entry = entries[key]
        if (
            entry.get("candidate_version") != V050
            or entry.get("original_clean_reader_filename") != source["file"]
            or entry.get("original_clean_reader_sha256") != source["sha256"]
            or entry.get("source_semantic_sha256") != source["reader"]["source_semantic_sha256"]
            or entry.get("horse_nos") != next(x["horse_nos"] for x in roster if (x["venue"], x["race_no"]) == key)
        ):
            raise ValueError(f"v0.5 Reader source binding mismatch: {key}")
        path = ab_root / "v050" / "reader" / entry["derived_normal_filename"]
        if digest(path.read_bytes()) != entry["derived_normal_sha256"]:
            raise ValueError(f"v0.5 Reader digest mismatch: {key}")
        normal = read_json(path)
        if "provenance" in normal or normal != transform(source["reader"], binding)["normal_view"]:
            raise ValueError(f"v0.5 model input is not deterministic normal_view: {key}")
    return session, readers, entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prep-root", type=Path, required=True)
    ap.add_argument("--request", type=Path, required=True)
    ap.add_argument("--ab-root", type=Path, required=True)
    ap.add_argument("--base-main-sha", required=True)
    ap.add_argument("--binding", type=Path, default=DEFAULT_BINDING)
    ap.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    ap.add_argument("--include-v051", action="store_true", help="seal a third v0.5.1 clean-blind lane using the same normal_view as v0.5.0")
    ap.add_argument("--pair-v051-v052", action="store_true", help="seal the prospective two-lane v0.5.1 vs v0.5.2 clean-blind profile")
    args = ap.parse_args()
    session = init_session(
        args.prep_root, args.request, args.ab_root, args.base_main_sha,
        args.binding, args.policy, args.include_v051, args.pair_v051_v052
    )
    print(json.dumps({"status": session["status"], "session_id": session["session_id"], "race_count": len(session["race_roster"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
