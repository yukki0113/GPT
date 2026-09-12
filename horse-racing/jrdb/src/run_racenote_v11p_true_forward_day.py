#!/usr/bin/env python3
"""Build one RaceNote v1.1-P TRUE_FORWARD prediction freeze for a JRA date.

This driver is intentionally thin. It reuses the already validated v0.2 scorer
and v1.1-P race-record builder from ``run_racenote_v11p_blind_freeze`` while
replacing historical-only assumptions with genuine per-day TRUE_FORWARD input
validation.

The driver never acquires or reads HJC, SED, finish, payout, final odds, final
popularity, or later-dated history. The Edge input must already have passed the
canonical TRUE_FORWARD earliest-post guard.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import racenote_edge_prediction_policy as edge_policy
import racenote_v02_reconstructed as control
import run_racenote_v11p_blind_freeze as historical

VERSION = "racenote-v11p-true-forward-day-1.1"
FREEZE_STAGE = "TRUE_FORWARD_PRE_HJC"
ALLOWED_TEMPORAL_MODES = {"current", "future"}
EDGE_STANDARD_PROFILE = "STANDARD"
EDGE_STANDARD_PUBLICATION_FILE = "edge_serving_catalog_v0_2.jsonl"


def require(condition: bool, message: str) -> None:
    """Raise a domain validation error when an invariant is false."""
    if not condition:
        raise ValueError(message)


def compact_date(value: Any) -> str:
    """Normalize a date value to YYYYMMDD and validate the calendar date."""
    text = str(value).strip().replace("-", "").replace("/", "")
    require(len(text) == 8 and text.isdigit(), f"invalid date: {value}")
    date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    return text


def iso_date(value: Any) -> str:
    """Return YYYY-MM-DD for a validated date value."""
    text = compact_date(value)
    return f"{text[:4]}-{text[4:6]}-{text[6:]}"


def load_json(path: Path) -> Any:
    """Load one UTF-8 JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_request(raw: Any) -> dict[str, Any]:
    """Validate the compact TRUE_FORWARD day request contract."""
    require(isinstance(raw, dict), "request must be an object")
    request_id = str(raw.get("request_id") or "").strip()
    require(bool(request_id), "request_id is required")
    day = compact_date(raw.get("date"))

    racenote = raw.get("racenote")
    edge = raw.get("edge")
    require(isinstance(racenote, dict), "racenote object is required")
    require(isinstance(edge, dict), "edge object is required")

    for key in ("run_id", "artifact_name", "inner_zip_sha256"):
        require(racenote.get(key) not in (None, ""), f"racenote.{key} is required")
    require(len(str(racenote["inner_zip_sha256"])) == 64, "racenote.inner_zip_sha256 must be SHA-256")

    for key in ("run_id", "artifact_name", "analysis_sha256"):
        require(edge.get(key) not in (None, ""), f"edge.{key} is required")
    require(len(str(edge["analysis_sha256"])) == 64, "edge.analysis_sha256 must be SHA-256")

    publication_sha = edge.get("publication_sha256")
    registry_sha = edge.get("registry_sha256")
    require(
        publication_sha not in (None, "") or registry_sha not in (None, ""),
        "edge.publication_sha256 or edge.registry_sha256 is required",
    )
    if publication_sha not in (None, ""):
        for key in ("publication_run_id", "publication_artifact_name", "serving_profile"):
            require(edge.get(key) not in (None, ""), f"edge.{key} is required for publication input")
        require(len(str(publication_sha)) == 64, "edge.publication_sha256 must be SHA-256")
        require(edge.get("serving_profile") == EDGE_STANDARD_PROFILE, "edge.serving_profile must be STANDARD")
    if registry_sha not in (None, ""):
        require(len(str(registry_sha)) == 64, "edge.registry_sha256 must be SHA-256")

    for optional_sha in ("manifest_sha256", "matches_sha256", "paci_sha256"):
        value = edge.get(optional_sha)
        if value not in (None, ""):
            require(len(str(value)) == 64, f"edge.{optional_sha} must be SHA-256")

    normalized = dict(raw)
    normalized["request_id"] = request_id
    normalized["date"] = day
    normalized["racenote"] = dict(racenote)
    normalized["edge"] = dict(edge)
    return normalized


def validate_racenote_manifest(manifest: Mapping[str, Any], day: str) -> None:
    """Validate that a RaceNote artifact is a pre-race current/future request."""
    request = manifest.get("request")
    require(isinstance(request, Mapping), "RaceNote manifest.request is missing")
    target_iso = iso_date(day)
    require(request.get("target_date") == target_iso, "RaceNote target_date mismatch")
    require(request.get("temporal_mode") in ALLOWED_TEMPORAL_MODES, "RaceNote temporal_mode must be current/future")
    require(request.get("base_backend") == "paci", "RaceNote current/future backend must be paci")

    enrichment = request.get("enrichment")
    require(isinstance(enrichment, Mapping), "RaceNote enrichment is missing")
    require(enrichment.get("analysis") is True, "RaceNote analysis enrichment is required")
    require(enrichment.get("stats_mart") is True, "RaceNote stats_mart enrichment is required")
    require(enrichment.get("as_of_exclusive") == target_iso, "RaceNote as_of_exclusive mismatch")

    bundle_count = int(manifest.get("bundle_count", -1))
    bundles = manifest.get("bundles")
    require(bundle_count > 0, "RaceNote bundle_count must be positive")
    require(isinstance(bundles, list), "RaceNote bundles list is missing")
    require(len(bundles) == bundle_count, "RaceNote bundle_count/list mismatch")


def load_racenote_day(root: Path, day: str, spec: Mapping[str, Any]) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any], str]]]:
    """Load and hash-verify one current/future RaceNote daily artifact."""
    outer_manifest_path = root / "request_manifest.json"
    inner_zip_path = root / f"RaceNote_{day}.zip"
    require(outer_manifest_path.is_file(), "RaceNote outer request_manifest.json is missing")
    require(inner_zip_path.is_file(), f"RaceNote_{day}.zip is missing")

    actual_zip_sha = historical.sha256_file(inner_zip_path)
    require(actual_zip_sha == str(spec["inner_zip_sha256"]), "RaceNote inner ZIP SHA mismatch")

    outer_manifest = load_json(outer_manifest_path)
    require(isinstance(outer_manifest, dict), "RaceNote outer manifest must be object")
    validate_racenote_manifest(outer_manifest, day)

    loaded: list[tuple[str, dict[str, Any], str]] = []
    with zipfile.ZipFile(inner_zip_path) as archive:
        names = set(archive.namelist())
        require("request_manifest.json" in names, "RaceNote inner request_manifest.json is missing")
        inner_manifest = json.loads(archive.read("request_manifest.json").decode("utf-8"))
        require(isinstance(inner_manifest, dict), "RaceNote inner manifest must be object")
        validate_racenote_manifest(inner_manifest, day)
        require(inner_manifest.get("request") == outer_manifest.get("request"), "RaceNote outer/inner request mismatch")

        expected_names = list(inner_manifest["bundles"])
        for name in expected_names:
            require(name in names, f"RaceNote bundle missing: {name}")
            raw_bytes = archive.read(name)
            bundle = json.loads(raw_bytes.decode("utf-8"))
            require(isinstance(bundle, dict), f"RaceNote bundle must be object: {name}")
            require(bundle.get("race", {}).get("date") == iso_date(day), f"RaceNote bundle date mismatch: {name}")
            loaded.append((name, bundle, historical.sha256_bytes(raw_bytes)))

    require(len(loaded) == int(inner_manifest["bundle_count"]), "RaceNote loaded bundle count mismatch")
    return outer_manifest, loaded


def _validate_edge_source_contract(
    result: Mapping[str, Any],
    manifest: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> None:
    """Validate either the current STANDARD publication source or legacy registry source."""
    publication_sha = spec.get("publication_sha256")
    if publication_sha not in (None, ""):
        require(result.get("serving_profile") == EDGE_STANDARD_PROFILE, "Edge serving_profile is not STANDARD")
        require(result.get("publication_file") == EDGE_STANDARD_PUBLICATION_FILE, "Edge publication_file mismatch")
        require(result.get("publication_sha256") == publication_sha, "Edge publication SHA mismatch")
        require(
            int(result.get("publication_run_id", -1)) == int(spec["publication_run_id"]),
            "Edge publication_run_id mismatch",
        )
        require(
            result.get("publication_artifact_name") == spec["publication_artifact_name"],
            "Edge publication_artifact_name mismatch",
        )
        require(manifest.get("serving_profile") == EDGE_STANDARD_PROFILE, "Edge manifest serving_profile mismatch")
        provenance = manifest.get("provenance")
        require(isinstance(provenance, Mapping), "Edge manifest provenance is missing")
        require(provenance.get("serving_profile") == EDGE_STANDARD_PROFILE, "Edge provenance serving_profile mismatch")
        input_sha = provenance.get("input_sha256")
        require(isinstance(input_sha, Mapping), "Edge provenance input_sha256 is missing")
        require(input_sha.get("publication_sha256") == publication_sha, "Edge manifest publication SHA mismatch")
        return

    registry_sha = spec.get("registry_sha256")
    require(registry_sha not in (None, ""), "legacy Edge registry SHA is missing")
    require(result.get("registry_sha256") == registry_sha, "Edge registry SHA mismatch")


def validate_edge_artifact(root: Path, day: str, spec: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate one canonical Edge TRUE_FORWARD freeze artifact."""
    result_path = root / "result.json"
    manifest_path = root / "manifest.json"
    facts_path = root / "current_facts.jsonl"
    matches_path = root / "edge_matches.jsonl"
    require(result_path.is_file(), "Edge result.json is missing")
    require(manifest_path.is_file(), "Edge manifest.json is missing")
    require(facts_path.is_file(), "Edge current_facts.jsonl is missing")
    require(matches_path.is_file(), "Edge edge_matches.jsonl is missing")

    result = load_json(result_path)
    require(isinstance(result, dict), "Edge result must be object")
    require(result.get("status") == "success", "Edge TRUE_FORWARD status is not success")
    require(result.get("evaluation_mode") == "TRUE_FORWARD", "Edge artifact is not TRUE_FORWARD")
    require(result.get("pre_race_guard") == "PASS", "Edge pre-race guard is not PASS")
    require(str(result.get("date")) == day, "Edge compact date mismatch")
    require(result.get("race_date") == iso_date(day), "Edge race_date mismatch")
    require(int(result.get("run_id", -1)) == int(spec["run_id"]), "Edge run_id mismatch")
    require(result.get("artifact_name") == spec["artifact_name"], "Edge artifact_name mismatch")
    require(result.get("analysis_sha256") == spec["analysis_sha256"], "Edge Analysis SHA mismatch")

    manifest_sha = historical.sha256_file(manifest_path)
    matches_sha = historical.sha256_file(matches_path)
    if spec.get("manifest_sha256") not in (None, ""):
        require(manifest_sha == spec["manifest_sha256"], "Edge manifest SHA mismatch")
    if spec.get("matches_sha256") not in (None, ""):
        require(matches_sha == spec["matches_sha256"], "Edge matches SHA mismatch")
    if spec.get("paci_sha256") not in (None, ""):
        require(result.get("paci_sha256") == spec["paci_sha256"], "Edge PACI SHA mismatch")

    require(result.get("manifest_sha256") == manifest_sha, "Edge result/manifest SHA mismatch")
    require(result.get("matches_sha256") == matches_sha, "Edge result/matches SHA mismatch")

    manifest = load_json(manifest_path)
    require(isinstance(manifest, dict), "Edge manifest must be object")
    require(manifest.get("evaluation_mode") == "TRUE_FORWARD", "Edge manifest evaluation_mode mismatch")
    require(manifest.get("pre_race_guard") == "PASS", "Edge manifest pre-race guard mismatch")
    require(manifest.get("race_date") == iso_date(day), "Edge manifest race_date mismatch")
    require(manifest.get("frozen_at_utc") == result.get("frozen_at_utc"), "Edge frozen_at mismatch")
    require(manifest.get("earliest_post_time_jst") == result.get("earliest_post_time_jst"), "Edge earliest-post mismatch")
    _validate_edge_source_contract(result, manifest, spec)

    facts = historical.load_jsonl(facts_path)
    match_rows = historical.load_jsonl(matches_path)
    require(len(facts) == int(result.get("runner_rows", -1)), "Edge runner_rows mismatch")
    require(len(match_rows) == len(facts), "Edge facts/matches membership count mismatch")
    matched_runners = sum(1 for row in match_rows if row.get("edge_matches"))
    total_matches = sum(len(row.get("edge_matches") or []) for row in match_rows)
    require(matched_runners == int(result.get("matched_runners", -1)), "Edge matched_runners mismatch")
    require(total_matches == int(result.get("matches", -1)), "Edge match count mismatch")
    return result, facts, match_rows


def edge_source_provenance(edge_result: Mapping[str, Any]) -> dict[str, Any]:
    """Return the immutable Edge source identity without changing scoring semantics."""
    provenance = {
        "edge_run_id": int(edge_result["run_id"]),
        "edge_artifact_name": edge_result["artifact_name"],
        "edge_manifest_sha256": edge_result["manifest_sha256"],
        "edge_matches_sha256": edge_result["matches_sha256"],
        "paci_sha256": edge_result["paci_sha256"],
        "analysis_sha256": edge_result["analysis_sha256"],
        "edge_frozen_at_utc": edge_result["frozen_at_utc"],
        "earliest_post_time_jst": edge_result["earliest_post_time_jst"],
        "pre_race_guard": edge_result["pre_race_guard"],
    }
    publication_sha = edge_result.get("publication_sha256")
    if publication_sha not in (None, ""):
        provenance["serving_profile"] = edge_result["serving_profile"]
        provenance["publication_file"] = edge_result["publication_file"]
        provenance["publication_sha256"] = publication_sha
        provenance["publication_run_id"] = int(edge_result["publication_run_id"])
        provenance["publication_artifact_name"] = edge_result["publication_artifact_name"]
    else:
        provenance["registry_sha256"] = edge_result["registry_sha256"]
    return provenance


def add_audit(target: Counter[str], values: Mapping[str, int]) -> None:
    """Accumulate integer race audit counters."""
    for key, value in values.items():
        target[key] += int(value)


def run(args: argparse.Namespace) -> dict[str, Any]:
    """Create one deterministic TRUE_FORWARD v1.1-P prediction freeze."""
    request = normalize_request(load_json(Path(args.request_json).resolve()))
    day = request["date"]
    racenote_root = Path(args.racenote_root).resolve()
    edge_root = Path(args.edge_root).resolve()
    output_dir = Path(args.output_dir).resolve()

    racenote_manifest, bundles = load_racenote_day(racenote_root, day, request["racenote"])
    edge_result, facts, match_rows = validate_edge_artifact(edge_root, day, request["edge"])

    fact_groups = historical.group_facts_by_race(facts)
    matches_by_key = historical.match_map(match_rows)
    race_audit: Counter[str] = Counter()
    races: list[dict[str, Any]] = []
    source_provenance = {
        "racenote_run_id": int(request["racenote"]["run_id"]),
        "racenote_artifact_name": request["racenote"]["artifact_name"],
        "racenote_inner_zip_sha256": request["racenote"]["inner_zip_sha256"],
        **edge_source_provenance(edge_result),
        "as_of_exclusive": iso_date(day),
    }

    for bundle_name, bundle, bundle_sha in bundles:
        record, audit = historical.build_race_record(
            day=day,
            bundle_name=bundle_name,
            bundle_sha256=bundle_sha,
            bundle=bundle,
            fact_groups=fact_groups,
            matches_by_key=matches_by_key,
            source_provenance=source_provenance,
        )
        races.append(record)
        add_audit(race_audit, audit)

    races.sort(key=lambda row: (str(row["race"]["venue_code"]), int(row["race"]["race_no"])))
    require(bool(races), "TRUE_FORWARD prediction freeze has no races")
    require(len(races) == int(racenote_manifest["bundle_count"]), "RaceNote race count changed during scoring")
    require(sum(len(rows) for rows in fact_groups.values()) == len(facts), "Edge fact grouping lost runners")

    edge_freeze = edge_source_provenance(edge_result)
    day_payload = {
        "schema_version": VERSION,
        "freeze_stage": FREEZE_STAGE,
        "evaluation_mode": "TRUE_FORWARD",
        "result_data_used": False,
        "date": iso_date(day),
        "control_version": control.VERSION,
        "policy_version": edge_policy.VERSION,
        "edge_freeze": edge_freeze,
        "racenote": {
            "run_id": int(request["racenote"]["run_id"]),
            "artifact_name": request["racenote"]["artifact_name"],
            "inner_zip_sha256": request["racenote"]["inner_zip_sha256"],
            "temporal_mode": racenote_manifest["request"]["temporal_mode"],
            "as_of_exclusive": racenote_manifest["request"]["enrichment"]["as_of_exclusive"],
        },
        "race_count": len(races),
        "races": races,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    day_file = output_dir / f"RaceNote_v1_1_Polarity_Gated_{day}_TRUE_FORWARD_PRE_HJC.json"
    day_sha = historical.write_json(day_file, day_payload)
    canonical_sha = historical.sha256_bytes(historical.canonical_bytes(day_payload))
    source_hashes = {
        "true_forward_runner_sha256": historical.sha256_file(Path(__file__).resolve()),
        "historical_builder_sha256": historical.sha256_file(HERE / "run_racenote_v11p_blind_freeze.py"),
        "control_source_sha256": historical.sha256_file(HERE / "racenote_v02_reconstructed.py"),
        "policy_source_sha256": historical.sha256_file(HERE / "racenote_edge_prediction_policy.py"),
    }
    manifest = {
        "schema_version": VERSION,
        "status": "success",
        "freeze_stage": FREEZE_STAGE,
        "evaluation_mode": "TRUE_FORWARD",
        "result_data_used": False,
        "request_id": request["request_id"],
        "run_id": int(args.run_id),
        "head_sha": args.head_sha,
        "date": day,
        "race_count": len(races),
        "control_version": control.VERSION,
        "policy_version": edge_policy.VERSION,
        "source_hashes": source_hashes,
        "prediction_file": day_file.name,
        "prediction_file_sha256": day_sha,
        "canonical_payload_sha256": canonical_sha,
        "edge_freeze": day_payload["edge_freeze"],
        "racenote": day_payload["racenote"],
        "audit": {"races": len(races), **dict(sorted(race_audit.items()))},
        "leakage_guard": {
            "allowed": [
                "pre-race PACI",
                "as-of-exclusive RaceNote history",
                "fixed Edge TRUE_FORWARD freeze from STANDARD serving catalog",
                "ACTIVE-only mark-changing policy within v1.1-P",
            ],
            "forbidden_and_not_read": ["HJC", "SED", "finish", "payout", "final odds", "final popularity", "later-dated history"],
        },
    }
    manifest_path = output_dir / f"RaceNote_v1_1_Polarity_Gated_{day}_TRUE_FORWARD_MANIFEST.json"
    manifest_sha = historical.write_json(manifest_path, manifest)

    result = {
        "status": "success",
        "freeze_stage": FREEZE_STAGE,
        "evaluation_mode": "TRUE_FORWARD",
        "result_data_used": False,
        "request_id": request["request_id"],
        "run_id": int(args.run_id),
        "head_sha": args.head_sha,
        "date": day,
        "race_count": len(races),
        "axis_changes": int(race_audit["axis_changed"]),
        "prediction_file": day_file.name,
        "prediction_file_sha256": day_sha,
        "canonical_payload_sha256": canonical_sha,
        "manifest_file": manifest_path.name,
        "manifest_sha256": manifest_sha,
        "edge_frozen_at_utc": edge_result["frozen_at_utc"],
        "earliest_post_time_jst": edge_result["earliest_post_time_jst"],
        "pre_race_guard": edge_result["pre_race_guard"],
        "source_hashes": source_hashes,
        "audit": manifest["audit"],
    }
    historical.write_json(output_dir / "result.json", result)
    return result


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--racenote-root", required=True)
    parser.add_argument("--edge-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as exc:
        print(
            json.dumps(
                {"status": "failure", "failure_class": "DOMAIN_VALIDATION_FAILED", "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())