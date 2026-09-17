from __future__ import annotations

from pathlib import Path

from .schema import TABLE_SPECS, TableSpec


def make_storage_config(csv_path: Path, target_root: Path, audit_root: Path, spec: TableSpec) -> dict:
    target = target_root / spec.relative_path
    audit = audit_root / (spec.name + ".audit.json")
    return {
        "dataset": {"name": f"local-horse-racing.{spec.name}"},
        "source": {
            "format": "csv",
            "path": str(csv_path),
            "encoding": "utf-8-sig",
            "delimiter": ",",
            "schema": dict(spec.schema),
        },
        "target": {
            "format": "parquet",
            "path": str(target),
            "compression": "zstd",
            "partition_by": list(spec.partition_by),
        },
        "keys": {"canonical": list(spec.canonical_key)},
        "sort_by": [],
        "validation": {
            "require_unique_key": True,
            "require_row_count_match": True,
            "non_null_columns": list(spec.non_null_columns),
            "expected_columns": list(spec.schema),
        },
        "audit": {"path": str(audit)},
    }


def materialize_parquet(staging_dir: Path, target_root: Path, audit_root: Path) -> dict[str, dict]:
    """Convert staging CSVs via the repository-shared tools/data-storage package.

    Caller must expose tools/data-storage on PYTHONPATH or install the package.
    This module intentionally does not reimplement Parquet writing or validation.
    """
    try:
        from data_storage.runner import run_config
    except ImportError as exc:
        raise RuntimeError(
            "shared data_storage package is unavailable; add repository tools/data-storage to PYTHONPATH"
        ) from exc

    results: dict[str, dict] = {}
    for name, spec in TABLE_SPECS.items():
        csv_path = staging_dir / f"{name}.csv"
        if not csv_path.is_file():
            raise FileNotFoundError(csv_path)
        config = make_storage_config(csv_path, target_root, audit_root, spec)
        result = run_config(config)
        results[name] = result
        if result.get("status") != "success":
            raise RuntimeError(f"data_storage failed for {name}: {result}")
    return results
