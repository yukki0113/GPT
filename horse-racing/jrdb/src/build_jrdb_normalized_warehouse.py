#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build immutable family/year JRDB Warehouse Parquet from frozen Raw ZIPs.

This is deliberately a Raw-to-Warehouse builder only.  It does not update a
Drive ``current.json``, alter Raw archives, or construct consumer marts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_DATA_STORAGE_ROOT = _REPOSITORY_ROOT / "tools" / "data-storage"
if str(_DATA_STORAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_DATA_STORAGE_ROOT))

try:  # The builder deliberately shares the project's optional data-storage runtime.
    import pyarrow as pa
    import pyarrow.parquet as pq
    from data_storage.common import sha256_file  # noqa: E402
    from data_storage.query import connect_parquet  # noqa: E402
except ModuleNotFoundError as exc:  # pragma: no cover - exercised in minimal runtimes.
    pa = None  # type: ignore[assignment]
    pq = None  # type: ignore[assignment]
    _STORAGE_IMPORT_ERROR: ModuleNotFoundError | None = exc
else:
    _STORAGE_IMPORT_ERROR = None
from jrdb_raw import ReaderAudit, canonical_members, read_fixed_records  # noqa: E402
from jrdb_warehouse_normalize import (  # noqa: E402
    CANONICAL_KEYS,
    IMPLEMENTED_FAMILIES,
    PROVENANCE_COLUMNS,
    RawProvenance,
    WAREHOUSE_NORMALIZER_VERSION,
    WAREHOUSE_SCHEMA_VERSION,
    canonical_key_columns,
    normalize_hjc_record,
    normalize_record,
)

ARTIFACT_TYPE = "jrdb_normalized_warehouse"
STORAGE_FORMAT = "parquet"
COMPRESSION = "zstd"
BUILDER_VERSION = "0.2.0"

# These checks are Warehouse-integrity evidence, not a consumer join contract.
# Raw deliveries can legitimately omit optional companion files or a race header;
# those cases are recorded as source-observed gaps rather than invented away.
_CROSS_FAMILY_CHECKS = (
    ("kyi_to_bac_race", "kyi", "bac", ("race_key_raw",), "SOURCE_CONDITIONAL_CONTEXT"),
    ("cha_to_kyi_runner", "cha", "kyi", ("race_horse_key",), "OPTIONAL_ENRICHMENT"),
    ("cyb_to_kyi_runner", "cyb", "kyi", ("race_horse_key",), "OPTIONAL_ENRICHMENT"),
    ("sed_to_kyi_runner", "sed", "kyi", ("race_key_raw", "horse_no"), "SETTLEMENT_COUNTERPART"),
    ("skb_to_sed_result", "skb", "sed", ("result_key",), "OPTIONAL_RESULT_EXTENSION"),
    (
        "zkb_to_zed_snapshot", "zkb", "zed",
        ("result_key", "source_member_date"), "OPTIONAL_HISTORY_EXTENSION",
    ),
)


def storage_runtime_available() -> bool:
    """Whether the shared ``tools/data-storage`` Parquet runtime is installed."""
    return _STORAGE_IMPORT_ERROR is None


def _require_storage_runtime() -> None:
    if _STORAGE_IMPORT_ERROR is not None:
        raise RuntimeError(
            "JRDB Warehouse requires tools/data-storage dependencies; install "
            "tools/data-storage/requirements.txt"
        ) from _STORAGE_IMPORT_ERROR


@dataclass(frozen=True)
class ArchiveSpec:
    """One inventoried immutable Raw archive assigned to its partition year."""

    family: str
    year: int
    path: Path

    def normalized_family(self) -> str:
        value = self.family.upper()
        if value not in (*IMPLEMENTED_FAMILIES, "HJC"):
            raise ValueError(f"unsupported Warehouse family: {self.family!r}")
        return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _schema_hash(schema: pa.Schema) -> str:
    fields = [{"name": field.name, "type": str(field.type), "nullable": field.nullable} for field in schema]
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _member_date(family: str, member: str, year: int) -> str | None:
    """Return a date only when the member and supplied partition agree exactly."""
    name = Path(member).name.upper()
    match = re.fullmatch(rf"{re.escape(family)}(\d{{6}}|\d{{8}})\.TXT", name)
    if not match:
        return None
    compact = match.group(1)
    if len(compact) == 8:
        candidate = compact
    elif int(compact[:2]) == year % 100:
        candidate = f"{year}{compact[2:]}"
    else:
        return None
    try:
        return datetime.strptime(candidate, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def _relation_name(family: str) -> str:
    return family.lower()


def _audit_rows(relation: str, rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    keys = canonical_key_columns(relation.upper())
    missing_provenance = {
        column: sum(1 for row in rows if row.get(column) in (None, ""))
        for column in PROVENANCE_COLUMNS
        if column not in {"source_archive_sha256", "source_member_sha256", "source_member_date"}
    }
    null_keys = {column: sum(1 for row in rows if row.get(column) is None) for column in keys}
    counter = Counter(tuple(row.get(column) for column in keys) for row in rows)
    duplicates = sum(count - 1 for count in counter.values() if count > 1)
    result = {
        "relation": relation,
        "row_count": len(rows),
        "canonical_key": list(keys),
        "duplicate_key_count": duplicates,
        "null_key_counts": null_keys,
        "missing_provenance_counts": missing_provenance,
        "passed": duplicates == 0 and not any(null_keys.values()) and not any(missing_provenance.values()),
    }
    if relation == "ukc_source_record_lineage":
        result["duplicate_class_counts"] = dict(sorted(Counter(
            row.get("duplicate_class") for row in rows
        ).items()))
    return result


def _normalize_ukc_duplicates(
    rows: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Collapse only byte-identical UKC rows while retaining source lineage.

    The UKC business grain remains ``horse_id + data_date``.  A collision at
    that grain is safe to collapse only when every source record has the same
    byte hash.  Each original Raw record is represented by one lineage row.
    """
    key_columns = canonical_key_columns("UKC")
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(column) for column in key_columns)].append(row)

    logical_rows: list[dict[str, Any]] = []
    lineage_rows: list[dict[str, Any]] = []
    exact_duplicate_count = 0
    for key, candidates in grouped.items():
        body_hashes = {row["source_record_sha256"] for row in candidates}
        if len(body_hashes) != 1:
            raise ValueError(
                "UKC business-key collision contains different Raw bodies: "
                f"key={key!r}, source_record_sha256={sorted(body_hashes)!r}"
            )
        logical = candidates[0]
        logical_rows.append(logical)
        for index, source in enumerate(candidates):
            lineage = {
                "horse_id": logical["horse_id"],
                "data_date": logical["data_date"],
                "logical_source_record_sha256": logical["source_record_sha256"],
                "duplicate_class": "CANONICAL" if index == 0 else "EXACT_SOURCE_DUPLICATE",
            }
            lineage.update({column: source.get(column) for column in PROVENANCE_COLUMNS})
            lineage_rows.append(lineage)
        exact_duplicate_count += len(candidates) - 1

    if len(lineage_rows) != len(rows):
        raise RuntimeError("UKC lineage count does not equal Raw source record count")
    if len(logical_rows) + exact_duplicate_count != len(rows):
        raise RuntimeError("UKC logical row plus exact duplicate count does not equal Raw source count")
    return logical_rows, lineage_rows, exact_duplicate_count


def _write_content_addressed(rows: Sequence[dict[str, Any]], output_root: Path, relation: str, year: int) -> dict[str, Any]:
    _require_storage_runtime()
    if not rows:
        raise ValueError(f"{relation}/{year} has no normalized rows")
    table = pa.Table.from_pylist(list(rows))
    schema_hash = _schema_hash(table.schema)
    temp_dir = output_root / ".partial"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{relation}-{year}-{os.getpid()}-{time.time_ns()}.parquet"
    try:
        pq.write_table(table, temp_path, compression=COMPRESSION, write_statistics=True)
        digest = sha256_file(temp_path)
        final_path = output_root / "objects" / relation / f"year={year}" / f"{digest}.parquet"
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if final_path.exists():
            if sha256_file(final_path) != digest:
                raise RuntimeError(f"content-address collision at {final_path}")
            temp_path.unlink()
        else:
            shutil.move(str(temp_path), str(final_path))
        connection = connect_parquet(final_path)
        try:
            parquet_rows = connection.execute("SELECT COUNT(*) FROM data").fetchone()[0]
            parquet_schema = connection.execute("DESCRIBE data").fetchall()
        finally:
            connection.close()
        if parquet_rows != len(rows):
            raise RuntimeError(f"Parquet row mismatch for {relation}/{year}: {parquet_rows} != {len(rows)}")
        return {
            "family": relation,
            "year": year,
            "relative_path": str(final_path.relative_to(output_root)).replace("\\", "/"),
            "sha256": digest,
            "size_bytes": final_path.stat().st_size,
            "row_count": parquet_rows,
            "schema_hash": schema_hash,
            "schema": [{"name": row[0], "type": row[1], "null": row[2]} for row in parquet_schema],
            "canonical_key": list(canonical_key_columns(relation.upper())),
        }
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _sql_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _parquet_list_literal(paths: Sequence[Path]) -> str:
    """Return a DuckDB list literal for immutable, local manifest assets."""
    return "[" + ", ".join(json.dumps(str(path)) for path in paths) + "]"


def _audit_cross_family_relations(
    manifest_entries: Sequence[dict[str, Any]], output_root: Path,
) -> dict[str, Any]:
    """Record Warehouse link coverage without inferring missing source data."""
    _require_storage_runtime()
    paths_by_relation: dict[str, list[Path]] = defaultdict(list)
    for entry in manifest_entries:
        paths_by_relation[str(entry["family"])].append(output_root / str(entry["relative_path"]))

    available = sorted(paths_by_relation)
    if not available:
        return {"status": "NOT_APPLICABLE", "checks": []}
    connection = connect_parquet(paths_by_relation[available[0]][0], view_name="warehouse_anchor")
    try:
        for relation, paths in paths_by_relation.items():
            connection.execute(
                f"CREATE VIEW {_sql_identifier(relation)} AS SELECT * FROM read_parquet("
                f"{_parquet_list_literal(paths)}, hive_partitioning=true, union_by_name=true)"
            )
        checks: list[dict[str, Any]] = []
        for name, child, parent, columns, availability_class in _CROSS_FAMILY_CHECKS:
            if child not in paths_by_relation or parent not in paths_by_relation:
                checks.append({
                    "name": name,
                    "child_relation": child,
                    "parent_relation": parent,
                    "key_columns": list(columns),
                    "availability_class": availability_class,
                    "status": "NOT_APPLICABLE",
                    "passed": True,
                    "reason": "relation_not_present_in_generation",
                })
                continue
            keys = ", ".join(_sql_identifier(column) for column in columns)
            predicates = " AND ".join(
                f"child.{_sql_identifier(column)} = parent.{_sql_identifier(column)}"
                for column in columns
            )
            non_null = " AND ".join(
                f"{_sql_identifier(column)} IS NOT NULL" for column in columns
            )
            child_key_count = connection.execute(
                f"SELECT COUNT(*) FROM (SELECT DISTINCT {keys} FROM {_sql_identifier(child)} WHERE {non_null})"
            ).fetchone()[0]
            parent_key_count = connection.execute(
                f"SELECT COUNT(*) FROM (SELECT DISTINCT {keys} FROM {_sql_identifier(parent)} WHERE {non_null})"
            ).fetchone()[0]
            child_keys = ", ".join(f"child.{_sql_identifier(column)}" for column in columns)
            unmatched_sql = (
                f"SELECT {child_keys} FROM (SELECT DISTINCT {keys} FROM {_sql_identifier(child)} WHERE {non_null}) child "
                f"LEFT JOIN (SELECT DISTINCT {keys} FROM {_sql_identifier(parent)} WHERE {non_null}) parent "
                f"ON {predicates} WHERE parent.{_sql_identifier(columns[0])} IS NULL"
            )
            unmatched_count = connection.execute(f"SELECT COUNT(*) FROM ({unmatched_sql})").fetchone()[0]
            samples = [list(row) for row in connection.execute(
                f"{unmatched_sql} ORDER BY {child_keys} LIMIT 10"
            ).fetchall()]
            checks.append({
                "name": name,
                "child_relation": child,
                "parent_relation": parent,
                "key_columns": list(columns),
                "availability_class": availability_class,
                "child_distinct_key_count": child_key_count,
                "parent_distinct_key_count": parent_key_count,
                "unmatched_child_key_count": unmatched_count,
                "sample_unmatched_child_keys": samples,
                "status": "PASS" if unmatched_count == 0 else "OBSERVED_SOURCE_GAP",
                "passed": True,
            })
    finally:
        connection.close()
    has_gap = any(item["status"] == "OBSERVED_SOURCE_GAP" for item in checks)
    return {"status": "PASS_WITH_REPORTED_SOURCE_GAPS" if has_gap else "PASS", "checks": checks}


def _normalize_partition(specs: Sequence[ArchiveSpec], ingested_at: str) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    family = specs[0].normalized_family()
    year = specs[0].year
    relations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_member_count = 0
    source_record_count = 0
    record_length_errors: Counter[str] = Counter()
    for spec in sorted(specs, key=lambda item: item.path.name):
        if spec.normalized_family() != family or spec.year != year:
            raise ValueError("partition specs must share family and year")
        if not spec.path.is_file():
            raise FileNotFoundError(spec.path)
        archive_sha256 = sha256_file(spec.path)
        with zipfile.ZipFile(spec.path) as zipped:
            members = canonical_members(zipped, family)
            if not members:
                raise ValueError(f"no canonical {family} members in {spec.path.name}")
            for member in members:
                source_member_count += 1
                member_data = zipped.read(member)
                member_sha256 = hashlib.sha256(member_data).hexdigest()
                reader_audit = ReaderAudit()
                records = read_fixed_records(zipped, member, family, reader_audit)
                record_length_errors.update(reader_audit.record_length_errors)
                for ordinal, record in enumerate(records, start=1):
                    source_record_count += 1
                    provenance = RawProvenance(
                        source_archive_name=spec.path.name,
                        source_archive_sha256=archive_sha256,
                        source_member=member,
                        source_member_date=_member_date(family, member, year),
                        source_member_sha256=member_sha256,
                        source_record_ordinal=ordinal,
                        warehouse_ingested_at=ingested_at,
                    )
                    if family == "HJC":
                        race, payouts = normalize_hjc_record(record, provenance)
                        relations["hjc_race"].append(race)
                        relations["hjc_payout"].extend(payouts)
                    else:
                        relations[_relation_name(family)].append(normalize_record(family, record, provenance))
    if record_length_errors:
        raise ValueError(f"fixed-record length errors: {dict(record_length_errors)}")
    if source_record_count == 0:
        raise ValueError(f"{family}/{year} contained no records")
    source_counts = {
        "source_archive_count": len(specs),
        "source_member_count": source_member_count,
        "source_record_count": source_record_count,
    }
    if family == "UKC":
        logical, lineage, exact_duplicates = _normalize_ukc_duplicates(relations["ukc"])
        relations["ukc"] = logical
        relations["ukc_source_record_lineage"] = lineage
        source_counts.update({
            "ukc_logical_row_count": len(logical),
            "ukc_lineage_row_count": len(lineage),
            "exact_source_duplicate_count": exact_duplicates,
        })
    return relations, source_counts


def build_generation(
    specs: Iterable[ArchiveSpec],
    output_root: Path,
    generation_id: str,
    source_git_commit: str,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build one local immutable generation; publication remains a later gate."""
    if not generation_id:
        raise ValueError("generation_id is required")
    if not source_git_commit:
        raise ValueError("source_git_commit is required")
    _require_storage_runtime()
    grouped: dict[tuple[str, int], list[ArchiveSpec]] = defaultdict(list)
    for spec in specs:
        grouped[(spec.normalized_family(), spec.year)].append(spec)
    if not grouped:
        raise ValueError("at least one archive spec is required")
    output_root = output_root.resolve()
    ingested_at = created_at or _utc_now()
    manifest_entries: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for (_, year), partition_specs in sorted(grouped.items()):
        relations, source_counts = _normalize_partition(partition_specs, ingested_at)
        for relation, rows in sorted(relations.items()):
            audit = _audit_rows(relation, rows)
            audit.update(source_counts)
            if not audit["passed"]:
                raise ValueError(f"Warehouse audit failed before Parquet write: {audit}")
            entry = _write_content_addressed(rows, output_root, relation, year)
            date_values = [value for row in rows for value in (row.get("race_date"), row.get("data_date_iso"), row.get("result_date")) if value]
            entry.update(source_counts)
            entry["period_from"] = min(date_values) if date_values else None
            entry["period_to"] = max(date_values) if date_values else None
            manifest_entries.append(entry)
            audits.append(audit)
    status = "PASS" if all(item["passed"] for item in audits) else "FAILED"
    cross_family = _audit_cross_family_relations(manifest_entries, output_root)
    manifest = {
        "artifact_type": ARTIFACT_TYPE,
        "warehouse_schema_version": WAREHOUSE_SCHEMA_VERSION,
        "storage_format": STORAGE_FORMAT,
        "storage_version": "v1",
        "generation_id": generation_id,
        "builder_version": BUILDER_VERSION,
        "normalizer_version": WAREHOUSE_NORMALIZER_VERSION,
        "source_git_commit": source_git_commit,
        "created_at": ingested_at,
        "status": status,
        "assets": manifest_entries,
    }
    audit = {
        "artifact_type": f"{ARTIFACT_TYPE}_audit",
        "generation_id": generation_id,
        "created_at": ingested_at,
        "status": status,
        "relations": audits,
        "cross_family": cross_family,
        "current_updated": False,
    }
    generation_dir = output_root / "generations" / generation_id
    if generation_dir.exists():
        raise FileExistsError(generation_dir)
    generation_dir.mkdir(parents=True)
    (generation_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (generation_dir / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"manifest": manifest, "audit": audit, "generation_dir": str(generation_dir)}


def _parse_archive_spec(value: str) -> ArchiveSpec:
    try:
        family, year, raw_path = value.split(":", 2)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--archive must be FAMILY:YEAR:/path/archive.zip") from exc
    if not year.isdigit() or len(year) != 4:
        raise argparse.ArgumentTypeError("archive year must be YYYY")
    return ArchiveSpec(family=family, year=int(year), path=Path(raw_path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local immutable JRDB normalized Warehouse generation")
    parser.add_argument("--archive", action="append", type=_parse_archive_spec, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--source-git-commit", required=True)
    args = parser.parse_args()
    result = build_generation(args.archive, args.output_root, args.generation_id, args.source_git_commit)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
