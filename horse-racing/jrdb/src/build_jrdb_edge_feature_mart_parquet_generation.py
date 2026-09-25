#!/usr/bin/env python3
"""Build one immutable Edge Feature Mart Parquet generation from the existing SQLite mart.

The conversion itself is delegated to tools/data-storage. This module owns only
Edge-specific generation metadata, canonical-key contract, and immutable output layout.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from data_storage.convert import convert
from data_storage.validate import validate

ARTIFACT_TYPE = "jrdb_edge_feature_mart"
SCHEMA_VERSION = "v0.2"
STORAGE_FORMAT = "parquet"
CANONICAL_KEY = ["race_key", "horse_no"]
SORT_BY = ["race_date", "race_key", "horse_no"]


class EdgeFeatureMartGenerationError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _schema_hash(schema: list[dict[str, Any]]) -> str:
    payload = json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_generation(
    *,
    sqlite_path: Path,
    output_root: Path,
    generation_id: str,
    source_generation_id: str | None = None,
    source_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    if not sqlite_path.is_file():
        raise EdgeFeatureMartGenerationError(f"SQLite mart missing: {sqlite_path}")
    if not generation_id:
        raise EdgeFeatureMartGenerationError("generation_id is required")

    generation_dir = output_root / "generations" / generation_id
    if generation_dir.exists():
        raise FileExistsError(generation_dir)
    generation_dir.mkdir(parents=True)
    parquet_path = generation_dir / "edge_runner_fact.parquet"
    audit_path = generation_dir / "audit.json"
    manifest_path = generation_dir / "manifest.json"

    config = {
        "source": {
            "format": "sqlite",
            "path": str(sqlite_path),
            "table": "edge_runner_fact",
            "batch_size": 50000,
        },
        "target": {
            "path": str(parquet_path),
            "compression": "zstd",
            "partition_by": [],
        },
        "keys": {"canonical": CANONICAL_KEY},
        "sort_by": SORT_BY,
        "validation": {"require_row_count_match": True},
    }
    conversion = convert(config)
    validation = validate(config, conversion)
    if validation.get("status") != "success" or validation.get("passed") is not True:
        audit_path.write_text(
            json.dumps({"status": "FAIL", "conversion": conversion, "validation": validation},
                       ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        raise EdgeFeatureMartGenerationError("tools/data-storage validation failed")

    schema = conversion.get("schema")
    if not isinstance(schema, list) or not schema:
        raise EdgeFeatureMartGenerationError("conversion schema missing")
    audit = {
        "status": "PASS",
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "generation_id": generation_id,
        "conversion": conversion,
        "validation": validation,
        "canonical_key": CANONICAL_KEY,
        "sort_by": SORT_BY,
    }
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    row_count = int(conversion["row_count_source"])
    manifest = {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "storage_format": STORAGE_FORMAT,
        "storage_version": "1",
        "generation_id": generation_id,
        "validation_status": "PASS",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "canonical_key": CANONICAL_KEY,
        "sort_by": SORT_BY,
        "row_count": row_count,
        "schema_hash": _schema_hash(schema),
        "source_sqlite_sha256": _sha256(sqlite_path),
        "source_generation_id": source_generation_id,
        "source_manifest_sha256": source_manifest_sha256,
        "fact_asset": {
            "name": "edge_runner_fact",
            "relative_path": f"generations/{generation_id}/edge_runner_fact.parquet",
            "rows": row_count,
            "size_bytes": parquet_path.stat().st_size,
            "sha256": _sha256(parquet_path),
        },
        "audit": {
            "relative_path": f"generations/{generation_id}/audit.json",
            "size_bytes": audit_path.stat().st_size,
            "sha256": _sha256(audit_path),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "status": "PASS",
        "generation_id": generation_id,
        "row_count": row_count,
        "parquet": str(parquet_path),
        "parquet_sha256": manifest["fact_asset"]["sha256"],
        "manifest": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "audit": str(audit_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--source-generation-id")
    parser.add_argument("--source-manifest-sha256")
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()
    result = build_generation(
        sqlite_path=args.sqlite,
        output_root=args.output_root,
        generation_id=args.generation_id,
        source_generation_id=args.source_generation_id,
        source_manifest_sha256=args.source_manifest_sha256,
    )
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
