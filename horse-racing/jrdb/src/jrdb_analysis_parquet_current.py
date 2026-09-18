#!/usr/bin/env python3
"""Resolve and validate an immutable Analysis Parquet current generation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class AnalysisParquetCurrentError(RuntimeError):
    """Raised when a current pointer or generation fails a closed validation gate."""


FACT_TABLE = "fact_entry_result_lite"
CANONICAL_KEY = ["race_key", "horse_no"]
METADATA_TABLES = {"meta_analysis_build", "meta_analysis_ingest_batch"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisParquetCurrentError(f"Unreadable JSON: {path}") from error
    if not isinstance(value, dict):
        raise AnalysisParquetCurrentError(f"JSON object required: {path}")
    return value


def _relative(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise AnalysisParquetCurrentError(f"{label} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise AnalysisParquetCurrentError(f"Unsafe {label}: {value}")
    resolved_root = root.resolve()
    resolved = (root / path).resolve()
    if resolved_root not in (resolved, *resolved.parents):
        raise AnalysisParquetCurrentError(f"{label} escapes root: {value}")
    return resolved


def _validate_asset(
    root: Path, entry: dict[str, Any], label: str, *, allow_missing_size: bool = False
) -> dict[str, Any]:
    path = _relative(root, entry.get("relative_path"), f"{label}.relative_path")
    if not path.is_file():
        raise AnalysisParquetCurrentError(f"Missing {label}: {path}")
    size = entry.get("size_bytes")
    # The initial v1.3 Parquet migration omitted ``size_bytes`` for metadata
    # objects, while retaining their content SHA-256.  Accept that one
    # historical shape only: the file must still exist and match its declared
    # digest, and all newly-produced manifests must declare the byte size.
    if size is None and allow_missing_size:
        size = path.stat().st_size
    if not isinstance(size, int) or size < 0 or path.stat().st_size != size:
        raise AnalysisParquetCurrentError(f"Size mismatch: {label}")
    expected = entry.get("sha256")
    if not isinstance(expected, str) or len(expected) != 64 or _sha256(path) != expected:
        raise AnalysisParquetCurrentError(f"SHA-256 mismatch: {label}")
    return {
        "path": path,
        "rows": entry.get("rows"),
        "sha256": expected,
        "size_bytes": size,
    }


def validate_generation(root: Path, manifest_path: Path) -> dict[str, Any]:
    """Validate one immutable generation without changing any pointer."""
    manifest = _read_json(manifest_path)
    if manifest.get("artifact_type") != "jrdb_analysis":
        raise AnalysisParquetCurrentError("Unexpected artifact_type")
    if manifest.get("schema_version") != "v1.3" or manifest.get("storage_format") != "parquet":
        raise AnalysisParquetCurrentError("Unexpected Analysis storage contract")
    if manifest.get("validation_status") != "PASS":
        raise AnalysisParquetCurrentError("Generation is not PASS")

    fact = manifest.get("fact_table")
    if not isinstance(fact, dict) or fact.get("name") != FACT_TABLE:
        raise AnalysisParquetCurrentError("Unexpected fact table")
    if fact.get("canonical_key") != CANONICAL_KEY:
        raise AnalysisParquetCurrentError("Unexpected canonical key")
    partitions = fact.get("partitions")
    if not isinstance(partitions, list) or not partitions:
        raise AnalysisParquetCurrentError("No fact partitions")

    years: set[int] = set()
    rows = 0
    assets = []
    for partition in partitions:
        if not isinstance(partition, dict) or not isinstance(partition.get("year"), int):
            raise AnalysisParquetCurrentError("Invalid fact partition")
        if partition["year"] in years:
            raise AnalysisParquetCurrentError("Duplicate fact partition year")
        years.add(partition["year"])
        if not isinstance(partition.get("rows"), int) or partition["rows"] <= 0:
            raise AnalysisParquetCurrentError("Invalid fact partition row count")
        rows += partition["rows"]
        assets.append(_validate_asset(root, partition, f"fact[{partition['year']}]"))
    if rows != manifest.get("total_rows"):
        raise AnalysisParquetCurrentError("Fact total row count mismatch")

    metadata = manifest.get("metadata_tables")
    if not isinstance(metadata, dict) or set(metadata) != METADATA_TABLES:
        raise AnalysisParquetCurrentError("Unexpected metadata table set")
    legacy_v1 = manifest.get("storage_version") == "1"
    for name in sorted(METADATA_TABLES):
        entry = metadata[name]
        if not isinstance(entry, dict):
            raise AnalysisParquetCurrentError(f"Invalid metadata entry: {name}")
        assets.append(
            _validate_asset(
                root,
                entry,
                name,
                allow_missing_size=legacy_v1,
            )
        )
    return {"generation_id": manifest.get("generation_id"), "manifest": manifest_path, "rows": rows, "assets": assets}


def resolve_current(root: Path) -> dict[str, Any]:
    """Resolve ``current.json`` and fail closed before any materialization."""
    root = root.resolve()
    pointer = _read_json(root / "current.json")
    generation = pointer.get("generation_id")
    if pointer.get("status") != "CURRENT" or not isinstance(generation, str) or not generation:
        raise AnalysisParquetCurrentError("Invalid Analysis current pointer")
    expected = f"generations/{generation}/manifest.json"
    if pointer.get("manifest") != expected:
        raise AnalysisParquetCurrentError("Current pointer manifest does not match generation")
    report = validate_generation(root, _relative(root, expected, "current.manifest"))
    if report["generation_id"] != generation:
        raise AnalysisParquetCurrentError("Manifest generation_id does not match pointer")
    return {"pointer": pointer, **report}
