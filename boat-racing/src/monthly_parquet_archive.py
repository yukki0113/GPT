#!/usr/bin/env python3
"""Lossless monthly CSV -> Parquet archival builder for boat-racing Drive data.

Input is an extracted, read-only snapshot laid out as ``<input>/<family>/*.csv``.
The command never deletes source files and never performs Drive I/O.  Upload, remote
verification, and cleanup are deliberately separate guarded operations owned by the
Chat/Work orchestration layer.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

FAMILIES = ("predictions", "prediction-rationales", "results", "sales-selection")
KEY_COLUMNS = {
    "predictions": ("日付", "会場", "R"),
    "results": ("日付", "会場", "R"),
    "sales-selection": ("日付", "会場", "R"),
    "prediction-rationales": ("日付", "会場", "R", "艇番"),
}


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def schema_hash(columns: list[str]) -> str:
    """Stable hash for an exact CSV schema (names and order), independent of types."""
    # Deliberately hashes the canonical JSON array used by the 2026-08 audit.
    return sha256_bytes(canonical_json(columns))[:10]


def find_column(columns: list[str], expected: str) -> str | None:
    if expected in columns:
        return expected
    # Backward-compatible English aliases; ambiguous data is never guessed.
    aliases = {"日付": ("date",), "会場": ("venue",), "R": ("race_no",), "艇番": ("boat_no",)}
    for alias in aliases.get(expected, ()):
        if alias in columns:
            return alias
    return None


def parse_csv(path: Path) -> tuple[list[str], list[list[str]], pa.Table, int]:
    # All CSV values remain UTF-8 strings.  This intentionally preserves leading
    # zeros, text dates, empty strings, NA and numeric-looking strings unchanged.
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        matrix = list(csv.reader(handle))
    if not matrix:
        raise ValueError(f"empty CSV: {path}")
    columns, rows = matrix[0], matrix[1:]
    if not columns or len(set(columns)) != len(columns):
        raise ValueError(f"invalid or duplicate headers: {path}")
    if any(len(row) < len(columns) for row in rows):
        raise ValueError(f"short CSV row (ambiguous missing column): {path}")
    # Historical July CSVs contain an undocumented trailing field on selected
    # rows.  Preserve it verbatim as an explicitly auxiliary string field; no
    # source value is discarded or shifted into a named source column.
    overflow = max((len(row) - len(columns) for row in rows), default=0)
    normalized = [row[:len(columns)] + row[len(columns):] + [""] * (overflow - (len(row) - len(columns))) for row in rows]
    names = columns + [f"__csv_overflow_{index}" for index in range(1, overflow + 1)]
    arrays = [pa.array([row[i] for row in normalized], type=pa.string()) for i in range(len(names))]
    return columns, rows, pa.Table.from_arrays(arrays, names=names), overflow


def hash_rows(rows: list[list[str]]) -> str:
    return sha256_bytes(canonical_json(rows))


def key_check(family: str, columns: list[str], rows: list[list[str]]) -> dict[str, Any]:
    wanted = KEY_COLUMNS[family]
    actual = [find_column(columns, item) for item in wanted]
    if any(item is None for item in actual):
        return {"status": "not_applicable", "expected": list(wanted), "actual": actual}
    indexes = [columns.index(item) for item in actual if item is not None]
    keys = [tuple(row[index] for index in indexes) for row in rows]
    key_set = sorted(set(keys))
    return {
        "status": "pass",
        "columns": actual,
        "key_rows": len(keys),
        "distinct_keys": len(key_set),
        "duplicate_rows": len(keys) - len(key_set),
        "missing_key_rows": sum(any(value == "" for value in key) for key in keys),
        "key_set_sha256": sha256_bytes(canonical_json(key_set)),
    }


def table_to_rows(table: pa.Table) -> list[list[str]]:
    return [list(row) for row in zip(*[column.to_pylist() for column in table.columns])]


def source_record(family: str, root: Path, path: Path) -> dict[str, Any]:
    columns, rows, table, overflow = parse_csv(path)
    return {
        "family": family,
        "source_csv": str(path.relative_to(root)).replace(os.sep, "/"),
        "source_sha256": sha256_bytes(path.read_bytes()),
        "rows": len(rows),
        "columns": columns,
        "column_count": len(columns),
        "csv_overflow_columns": overflow,
        "cell_values_sha256": hash_rows(rows),
        "key_validation": key_check(family, columns, rows),
        "table": table,
        "raw_rows": rows,
    }


def validate_source_piece(record: dict[str, Any], table: pa.Table) -> dict[str, Any]:
    full_rows = table_to_rows(table)
    # Drop only archive auxiliary overflow fields after preserving their values.
    source_rows = [row[:len(record["columns"])] + [value for value in row[len(record["columns"]):] if value != ""] for row in full_rows]
    base_rows = [row[:len(record["columns"])] for row in full_rows]
    key = key_check(record["family"], record["columns"], base_rows)
    passed = (
        table.column_names[:len(record["columns"])] == record["columns"]
        and table.num_rows == record["rows"]
        and hash_rows(source_rows) == record["cell_values_sha256"]
        and all(pa.types.is_string(field.type) for field in table.schema)
        and key == record["key_validation"]
    )
    return {
        "source_csv": record["source_csv"],
        "pass": passed,
        "header_equal": table.column_names[:len(record["columns"])] == record["columns"],
        "row_count_equal": table.num_rows == record["rows"],
        "cell_values_equal": hash_rows(source_rows) == record["cell_values_sha256"],
        "all_original_fields_string": all(pa.types.is_string(field.type) for field in table.schema),
        "key_validation": key,
    }


def build(input_root: Path, output_root: Path, month: str, generation: int, supersedes: int | None) -> Path:
    if len(month) != 6 or not month.isdigit():
        raise ValueError("month must be YYYYMM")
    records: list[dict[str, Any]] = []
    for family in FAMILIES:
        family_dir = input_root / family
        if not family_dir.exists():
            raise FileNotFoundError(f"family directory missing: {family_dir}")
        for path in sorted(family_dir.rglob("*.csv")):
            records.append(source_record(family, input_root, path))
    if not records:
        raise ValueError("no CSV input")

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["family"], schema_hash(record["columns"]))].append(record)

    groups: list[dict[str, Any]] = []
    for (family, sig), members in sorted(grouped.items()):
        max_overflow = max(member["csv_overflow_columns"] for member in members)
        tables = []
        for member in members:
            table = member["table"]
            for index in range(member["csv_overflow_columns"] + 1, max_overflow + 1):
                table = table.append_column(f"__csv_overflow_{index}", pa.array([""] * table.num_rows, type=pa.string()))
            tables.append(table.append_column("source_csv", pa.array([member["source_csv"]] * table.num_rows, type=pa.string())))
        merged = pa.concat_tables(tables)
        filename = f"{family}__{month}__schema_{sig}.parquet"
        target = output_root / filename
        pq.write_table(merged, target, compression="zstd", compression_level=3, use_dictionary=True, write_statistics=True)
        reread = pq.read_table(target)
        if "source_csv" not in reread.column_names or not pa.types.is_string(reread.schema.field("source_csv").type):
            raise AssertionError(f"source_csv missing/invalid: {filename}")
        validations = []
        for member in members:
            mask = pc.equal(reread["source_csv"], pa.scalar(member["source_csv"], type=pa.string()))
            piece = reread.filter(mask).drop_columns(["source_csv"])
            validations.append(validate_source_piece(member, piece))
        if not all(item["pass"] for item in validations):
            raise AssertionError(f"lossless validation failed: {filename}")
        groups.append({
            "family": family,
            "schema_hash": sig,
            "parquet_file": filename,
            "parquet_sha256": sha256_bytes(target.read_bytes()),
            "parquet_bytes": target.stat().st_size,
            "parquet_rows": reread.num_rows,
            "parquet_columns": reread.num_columns,
            "source_csv_present": True,
            "archive_auxiliary_columns": [f"__csv_overflow_{index}" for index in range(1, max_overflow + 1)],
            "source_csvs": [{key: value for key, value in member.items() if key not in {"table", "raw_rows"}} for member in members],
            "lossless_validation": validations,
            "key_validation": {"pass": all(item["key_validation"] == member["key_validation"] for item, member in zip(validations, members))},
            "upload": {"status": "pending"},
            "drive_retrieval": {"status": "pending"},
        })

    manifest = {
        "schema_version": 1,
        "month": month,
        "month_status": "closed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation": generation,
        "supersedes_generation": supersedes,
        "compression": "zstd",
        "compression_level": 3,
        "source_value_policy": "all original CSV fields are UTF-8 strings; no inference or normalization",
        "families": list(FAMILIES),
        "groups": groups,
        "source_csv_count": len(records),
        "source_row_count": sum(record["rows"] for record in records),
        "parquet_file_count": len(groups),
        "parquet_bytes": sum(group["parquet_bytes"] for group in groups),
        "cleanup_ready": False,
        "cleanup_conditions": {
            "parquet_generation": True,
            "manifest_generation": True,
            "lossless_validation": True,
            "key_validation": True,
            "parquet_sha256": True,
            "drive_upload": False,
            "drive_exists": False,
            "drive_retrieval": False,
            "reread_after_retrieval": False,
            "manifest_upload": False,
        },
    }
    manifest_path = output_root / f"{month}__parquet_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--month", required=True)
    parser.add_argument("--generation", type=int, default=1)
    parser.add_argument("--supersedes-generation", type=int)
    args = parser.parse_args()
    manifest = build(args.input_root, args.output_root, args.month, args.generation, args.supersedes_generation)
    print(manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
