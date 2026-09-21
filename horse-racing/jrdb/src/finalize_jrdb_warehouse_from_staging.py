#!/usr/bin/env python3
"""Finalize the JRDB normalized Warehouse from immutable family staging evidence.

The final generation only references existing staged Parquet objects; it never
rewrites, copies, or re-uploads them.  The caller supplies a connector-derived
snapshot JSON so the finalizer has no Drive credentials or side effects.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

FAMILIES = ("BAC", "KYI", "CHA", "CYB", "SED", "SKB", "ZED", "ZKB", "UKC", "HJC")
YEARS = tuple(range(2010, 2026))
REQUIRED_SIDECARS = {"manifest.json", "audit.json", "build.json", "raw_receipt.json", "publish_request.json", "completion_marker.json"}
PROVENANCE_COLUMNS = {"source_archive_name", "source_archive_sha256", "source_member", "source_member_date", "source_member_sha256", "source_record_ordinal"}


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _fail(message: str) -> None:
    raise ValueError(message)


def _schema_names(asset: dict[str, Any]) -> set[str]:
    return {str(column["name"]) for column in asset.get("schema", []) if isinstance(column, dict) and column.get("name")}


def finalize(snapshot: dict[str, Any], generation_id: str) -> dict[str, Any]:
    staged = snapshot.get("families")
    if not isinstance(staged, list):
        _fail("snapshot.families must be a list")
    found = {str(item.get("family", "")).upper(): item for item in staged}
    if set(found) != set(FAMILIES):
        _fail(f"family set mismatch: expected={FAMILIES}, actual={sorted(found)}")

    all_assets: list[dict[str, Any]] = []
    family_refs: list[dict[str, Any]] = []
    relation_specs: dict[str, dict[str, set[Any]]] = {}
    errors: list[str] = []
    for family in FAMILIES:
        item = found[family]
        marker = item.get("completion_marker", {})
        manifest = item.get("manifest", {})
        audit = item.get("audit", {})
        sidecars = set(item.get("sidecars", []))
        listed_assets = item.get("listed_assets", [])
        if marker.get("status") != "PASS / published / refetch_verified":
            errors.append(f"{family}: completion marker is not PASS/published/refetch_verified")
        if manifest.get("status") != "PASS" or audit.get("status") != "PASS":
            errors.append(f"{family}: manifest/audit status is not PASS")
        missing_sidecars = REQUIRED_SIDECARS - sidecars
        if missing_sidecars:
            errors.append(f"{family}: missing sidecars {sorted(missing_sidecars)}")
        assets = manifest.get("assets")
        if not isinstance(assets, list) or not assets:
            errors.append(f"{family}: manifest assets missing")
            continue
        expected_relations = marker.get("relations", {})
        counts = Counter(str(asset.get("family")) for asset in assets)
        if expected_relations and counts != Counter({str(k): int(v) for k, v in expected_relations.items()}):
            errors.append(f"{family}: marker relation counts disagree with manifest")
        years_by_relation: dict[str, set[int]] = defaultdict(set)
        listed = {(str(a.get("relative_path")), str(a.get("sha256")), int(a.get("size_bytes", -1))) for a in listed_assets}
        for asset in assets:
            relation = str(asset.get("family", ""))
            year = asset.get("year")
            digest = str(asset.get("sha256", ""))
            size = asset.get("size_bytes")
            path = str(asset.get("relative_path", ""))
            if not relation or year not in YEARS or len(digest) != 64 or not isinstance(size, int) or size < 1:
                errors.append(f"{family}: malformed asset metadata {asset!r}")
                continue
            if not path.endswith(f"/{digest}.parquet"):
                errors.append(f"{family}: content-addressed path mismatch for {relation}/{year}")
            if listed and (path, digest, size) not in listed:
                errors.append(f"{family}: Drive listing mismatch for {relation}/{year}")
            years_by_relation[relation].add(year)
            names = _schema_names(asset)
            if not PROVENANCE_COLUMNS <= names:
                errors.append(f"{family}: provenance columns missing for {relation}/{year}")
            key = tuple(str(x) for x in asset.get("canonical_key", []))
            schema_hash = str(asset.get("schema_hash", ""))
            spec = relation_specs.setdefault(relation, {"schema_hashes": set(), "canonical_keys": set()})
            spec["schema_hashes"].add(schema_hash)
            spec["canonical_keys"].add(key)
        for relation, years in years_by_relation.items():
            if years != set(YEARS):
                errors.append(f"{family}: year coverage mismatch for {relation}: {sorted(years)}")
        all_assets.extend(assets)
        family_refs.append({
            "family": family,
            "staging_generation_id": manifest.get("generation_id"),
            "staging_folder_id": item.get("staging_folder_id"),
            "completion_marker_sha256": _sha(marker),
            "manifest_sha256": _sha(manifest),
            "audit_sha256": _sha(audit),
            "asset_count": len(assets),
        })
    duplicates = [key for key, count in Counter((a.get("relative_path"), a.get("sha256")) for a in all_assets).items() if count != 1]
    if duplicates:
        errors.append(f"duplicate object references: {duplicates[:5]}")
    for relation, spec in relation_specs.items():
        if len(spec["canonical_keys"]) != 1:
            errors.append(f"canonical key drift in relation {relation}: {sorted(spec['canonical_keys'])}")
    if errors:
        _fail("finalization failed: " + "; ".join(errors))
    manifest = {
        "artifact_type": "jrdb_normalized_warehouse_final_generation",
        "warehouse_schema_version": "v1",
        "storage_format": "parquet",
        "storage_version": "v1",
        "generation_id": generation_id,
        "status": "PASS",
        "asset_reference_mode": "staging_immutable_reference",
        "families": family_refs,
        "assets": all_assets,
    }
    audit = {
        "artifact_type": "jrdb_normalized_warehouse_final_audit",
        "generation_id": generation_id,
        "status": "PASS",
        "family_count": len(family_refs),
        "asset_count": len(all_assets),
        "duplicate_object_count": 0,
        "year_coverage": [YEARS[0], YEARS[-1]],
        "relation_specs": {
            key: {
                "schema_hashes": sorted(value["schema_hashes"]),
                "canonical_key": list(next(iter(value["canonical_keys"]))),
                "schema_variant_count": len(value["schema_hashes"]),
            }
            for key, value in sorted(relation_specs.items())
        },
        "cross_family_audit": {"status": "PASS", "checks": ["family set", "year coverage", "content-addressed asset uniqueness", "schema/canonical-key consistency", "provenance", "family audit evidence"]},
        "manifest_sha256": _sha(manifest),
    }
    current = {
        "artifact_type": "jrdb_normalized_warehouse_current",
        "warehouse_schema_version": "v1",
        "status": "accepted",
        "generation_id": generation_id,
        "manifest": f"generations/{generation_id}/manifest.json",
        "audit": f"generations/{generation_id}/audit.json",
        "manifest_sha256": audit["manifest_sha256"],
        "final_audit_sha256": _sha(audit),
        "asset_reference_mode": "staging_immutable_reference",
    }
    return {"manifest": manifest, "audit": audit, "current": current}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = finalize(json.loads(args.snapshot.read_text()), args.generation_id)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for name in ("manifest", "audit", "current"):
        (args.output_dir / f"{name}.json").write_text(json.dumps(result[name], ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "generation_id": args.generation_id, "asset_count": len(result["manifest"]["assets"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
