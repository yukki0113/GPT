#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Immutable Parquet publication for JRDB Post-Race Review v0.1 snapshots.

The publisher accepts an already-built logical Review bundle, applies the
fail-closed audit, writes year-partitioned ZSTD Parquet objects, re-reads every
object for key/schema/count validation, then writes one immutable generation.

It does not fetch Drive data, parse fixed-width JRDB bytes, or build Review
features. Initial promotion is intentionally blocked unless the caller declares
the snapshot complete.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from audit_jrdb_postrace_review import audit_review_bundle
from jrdb_postrace_review import REVIEW_LOGIC_VERSION, REVIEW_SCHEMA_VERSION
from jrdb_postrace_review_standard import BASELINE_VERSION

ARTIFACT_TYPE = "jrdb_postrace_review"
STORAGE_VERSION = "1"
RELATIONS = (
    "fact_race_context",
    "fact_race_review",
    "fact_horse_performance",
    "fact_track_bias",
)
REQUIRED_RELATIONS = (
    "fact_race_context",
    "fact_race_review",
    "fact_horse_performance",
)
RELATION_KEYS = {
    "fact_race_context": ("race_key",),
    "fact_race_review": ("race_key",),
    "fact_horse_performance": ("race_horse_key",),
    "fact_track_bias": (
        "race_date",
        "venue_code",
        "surface_code",
        "bias_dimension",
        "bias_bucket",
    ),
}
RELATION_SORT = {
    "fact_race_context": ("race_date", "race_key"),
    "fact_race_review": ("race_date", "race_key"),
    "fact_horse_performance": ("race_date", "race_key", "horse_no"),
    "fact_track_bias": (
        "race_date",
        "venue_code",
        "surface_code",
        "bias_dimension",
        "bias_bucket",
    ),
}


class PostRaceReviewPublishError(RuntimeError):
    """Raised when an immutable Review generation cannot be safely published."""


def _sha256(path: Path) -> str:
    """Hash one file without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    """Read one JSON object or fail closed."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PostRaceReviewPublishError(
            f"unreadable Review JSON: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise PostRaceReviewPublishError(
            f"Review JSON object required: {path}"
        )
    return value


def _load_schema_sql() -> str:
    """Load the frozen v0.1 logical schema from the repository."""
    path = (
        Path(__file__).resolve().parents[1]
        / "schema"
        / "jrdb_postrace_review_schema_v0_1.sql"
    )
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PostRaceReviewPublishError(
            f"Review schema is unavailable: {path}"
        ) from exc


def _quote_identifier(value: str) -> str:
    """Return one DuckDB-safe quoted identifier."""
    return '"' + value.replace('"', '""') + '"'


def _relation_columns(connection: Any, relation: str) -> list[str]:
    """Return frozen schema column order."""
    rows = connection.execute(
        "SELECT column_name "
        "FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ? "
        "ORDER BY ordinal_position",
        [relation],
    ).fetchall()
    return [str(row[0]) for row in rows]


def _coerce_cell(value: object) -> object:
    """Reject non-finite values before handing data to DuckDB."""
    if isinstance(value, float) and not math.isfinite(value):
        raise PostRaceReviewPublishError(
            "non-finite value reached publisher after audit"
        )
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return value


def _insert_rows(
    connection: Any,
    relation: str,
    rows: list[Mapping[str, object]],
) -> None:
    """Insert rows against the frozen schema, ignoring no unknown columns."""
    columns = _relation_columns(connection, relation)
    allowed = set(columns)

    for row in rows:
        unknown = set(str(key) for key in row) - allowed
        if unknown:
            raise PostRaceReviewPublishError(
                f"{relation}: unknown persisted columns: {sorted(unknown)}"
            )

    if not rows:
        return

    quoted = ", ".join(_quote_identifier(column) for column in columns)
    marks = ", ".join("?" for _ in columns)
    values = [
        tuple(_coerce_cell(row.get(column)) for column in columns)
        for row in rows
    ]
    connection.executemany(
        f"INSERT INTO {_quote_identifier(relation)} ({quoted}) "
        f"VALUES ({marks})",
        values,
    )


def _partition_years(
    rows: list[Mapping[str, object]],
) -> dict[int, list[Mapping[str, object]]]:
    """Split rows by race_date year without accepting malformed dates."""
    result: dict[int, list[Mapping[str, object]]] = {}
    for row in rows:
        raw = str(row.get("race_date") or "").strip()
        digits = "".join(character for character in raw if character.isdigit())
        if len(digits) != 8:
            raise PostRaceReviewPublishError(
                f"invalid persisted race_date: {raw!r}"
            )
        try:
            year = int(digits[:4])
            dt.date(year, int(digits[4:6]), int(digits[6:8]))
        except ValueError as exc:
            raise PostRaceReviewPublishError(
                f"invalid persisted race_date: {raw!r}"
            ) from exc
        result.setdefault(year, []).append(row)
    return result


def _key_duplicate_count(connection: Any, relation: str) -> int:
    """Count duplicate canonical keys in one staged relation."""
    keys = RELATION_KEYS[relation]
    group = ", ".join(_quote_identifier(key) for key in keys)
    value = connection.execute(
        "SELECT COUNT(*) FROM ("
        f"SELECT {group}, COUNT(*) AS n "
        f"FROM {_quote_identifier(relation)} "
        f"GROUP BY {group} HAVING COUNT(*) > 1"
        ")"
    ).fetchone()[0]
    return int(value)


def _write_parquet(
    connection: Any,
    relation: str,
    year: int,
    path: Path,
) -> None:
    """Write one deterministic year partition with a stable row ordering."""
    order = ", ".join(
        _quote_identifier(column)
        for column in RELATION_SORT[relation]
    )
    safe_path = str(path).replace("'", "''")
    connection.execute(
        "COPY ("
        f"SELECT * FROM {_quote_identifier(relation)} "
        f"WHERE EXTRACT(YEAR FROM race_date) = {int(year)} "
        f"ORDER BY {order}"
        ") "
        f"TO '{safe_path}' "
        "(FORMAT PARQUET, COMPRESSION ZSTD)"
    )


def _parquet_validation(
    connection: Any,
    relation: str,
    path: Path,
    expected_rows: int,
) -> dict[str, object]:
    """Re-read one object and validate row count, schema and unique keys."""
    safe_path = str(path).replace("'", "''")
    description = connection.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{safe_path}', hive_partitioning=false)"
    ).fetchall()
    parquet_columns = [str(row[0]) for row in description]
    schema_columns = _relation_columns(connection, relation)
    if parquet_columns != schema_columns:
        raise PostRaceReviewPublishError(
            f"{relation}: Parquet schema mismatch"
        )

    row_count = int(
        connection.execute(
            f"SELECT COUNT(*) FROM read_parquet('{safe_path}', hive_partitioning=false)"
        ).fetchone()[0]
    )
    if row_count != expected_rows:
        raise PostRaceReviewPublishError(
            f"{relation}: Parquet row count mismatch"
        )

    keys = RELATION_KEYS[relation]
    group = ", ".join(_quote_identifier(key) for key in keys)
    duplicate_count = int(
        connection.execute(
            "SELECT COUNT(*) FROM ("
            f"SELECT {group}, COUNT(*) AS n "
            f"FROM read_parquet('{safe_path}', hive_partitioning=false) "
            f"GROUP BY {group} HAVING COUNT(*) > 1"
            ")"
        ).fetchone()[0]
    )
    if duplicate_count:
        raise PostRaceReviewPublishError(
            f"{relation}: duplicate key in Parquet object"
        )

    return {
        "rows": row_count,
        "schema_columns": parquet_columns,
        "duplicate_key_groups": duplicate_count,
    }


def _load_current_manifest(root: Path) -> dict[str, Any] | None:
    """Load the existing accepted Review manifest when present."""
    current = root / "current.json"
    if not current.is_file():
        return None

    pointer = _read_json(current)
    if pointer.get("status") != "CURRENT":
        raise PostRaceReviewPublishError(
            "existing Review current pointer is not CURRENT"
        )
    manifest_ref = pointer.get("manifest")
    if not isinstance(manifest_ref, str):
        raise PostRaceReviewPublishError(
            "existing Review current has no manifest"
        )

    manifest = _read_json(root / manifest_ref)
    if (
        manifest.get("artifact_type") != ARTIFACT_TYPE
        or manifest.get("validation_status") != "PASS"
    ):
        raise PostRaceReviewPublishError(
            "existing Review manifest is not accepted"
        )
    return manifest


def _promote_current(
    root: Path,
    manifest: Mapping[str, object],
    previous: Mapping[str, object] | None,
) -> dict[str, object]:
    """Atomically advance current after a completely validated generation."""
    generation_id = str(manifest["generation_id"])
    pointer = {
        "status": "CURRENT",
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": REVIEW_SCHEMA_VERSION,
        "review_logic_version": REVIEW_LOGIC_VERSION,
        "baseline_version": BASELINE_VERSION,
        "generation_id": generation_id,
        "manifest": f"generations/{generation_id}/manifest.json",
        "previous_generation_id": (
            previous.get("generation_id")
            if previous is not None
            else None
        ),
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    pending = root / "current.json.pending"
    pending.write_text(
        json.dumps(pointer, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    pending.replace(root / "current.json")
    return pointer


def publish_snapshot(
    bundle: Mapping[str, object],
    root: Path,
    generation_id: str,
    *,
    source_provenance: Mapping[str, object],
    promote: bool = False,
    complete_snapshot: bool = False,
) -> dict[str, object]:
    """Publish one complete logical snapshot as immutable year Parquet objects.

    promote=True requires complete_snapshot=True. This blocks accidental
    promotion of a one-day development bundle as the canonical history.
    """
    try:
        import duckdb
    except ImportError as exc:
        raise PostRaceReviewPublishError(
            "Review Parquet publisher requires duckdb"
        ) from exc

    if promote and not complete_snapshot:
        raise PostRaceReviewPublishError(
            "canonical promotion requires complete_snapshot=True"
        )

    root = Path(root).resolve()
    generation_dir = root / "generations" / generation_id
    if generation_dir.exists():
        raise FileExistsError(generation_dir)

    day_audit = audit_review_bundle(
        bundle,
        require_single_target_date=False,
    )
    if day_audit["status"] != "PASS":
        raise PostRaceReviewPublishError(
            "Review bundle failed pre-publication audit"
        )

    previous = _load_current_manifest(root)
    generation_dir.mkdir(parents=True)
    schema_sql = _load_schema_sql()

    try:
        relation_manifest: dict[str, object] = {}
        partition_audits: list[dict[str, object]] = []

        with tempfile.TemporaryDirectory(
            prefix="jrdb_postrace_review_"
        ) as temporary:
            temp_root = Path(temporary)
            connection = duckdb.connect(":memory:")
            try:
                connection.execute(schema_sql)

                for relation in RELATIONS:
                    raw_rows = bundle.get(relation)
                    if raw_rows is None:
                        if relation in REQUIRED_RELATIONS:
                            raise PostRaceReviewPublishError(
                                f"required relation missing: {relation}"
                            )
                        continue
                    if not isinstance(raw_rows, list):
                        raise PostRaceReviewPublishError(
                            f"{relation} must be a list"
                        )

                    rows: list[Mapping[str, object]] = []
                    for row in raw_rows:
                        if not isinstance(row, Mapping):
                            raise PostRaceReviewPublishError(
                                f"{relation} has a non-mapping row"
                            )
                        rows.append(row)

                    _insert_rows(connection, relation, rows)
                    duplicate_count = _key_duplicate_count(
                        connection,
                        relation,
                    )
                    if duplicate_count:
                        raise PostRaceReviewPublishError(
                            f"{relation}: duplicate staged key"
                        )

                    partitions: list[dict[str, object]] = []
                    by_year = _partition_years(rows)
                    for year in sorted(by_year):
                        expected_rows = len(by_year[year])
                        candidate = temp_root / f"{relation}-{year}.parquet"
                        _write_parquet(
                            connection,
                            relation,
                            year,
                            candidate,
                        )
                        validation = _parquet_validation(
                            connection,
                            relation,
                            candidate,
                            expected_rows,
                        )
                        digest = _sha256(candidate)
                        destination = (
                            root
                            / "objects"
                            / relation
                            / f"year={year}"
                            / f"{digest}.parquet"
                        )
                        destination.parent.mkdir(
                            parents=True,
                            exist_ok=True,
                        )
                        if destination.exists():
                            if _sha256(destination) != digest:
                                raise PostRaceReviewPublishError(
                                    f"content-address collision: {destination}"
                                )
                        else:
                            shutil.copy2(candidate, destination)

                        object_validation = _parquet_validation(
                            connection,
                            relation,
                            destination,
                            expected_rows,
                        )
                        if object_validation != validation:
                            raise PostRaceReviewPublishError(
                                f"{relation}/{year}: copy re-read mismatch"
                            )

                        part = {
                            "year": year,
                            "rows": expected_rows,
                            "sha256": digest,
                            "size_bytes": destination.stat().st_size,
                            "relative_path": str(
                                destination.relative_to(root)
                            ),
                        }
                        partitions.append(part)
                        partition_audits.append(
                            {
                                "relation": relation,
                                "year": year,
                                "status": "PASS",
                                **validation,
                                "sha256": digest,
                            }
                        )

                    relation_manifest[relation] = {
                        "canonical_key": list(RELATION_KEYS[relation]),
                        "sort_by": list(RELATION_SORT[relation]),
                        "total_rows": len(rows),
                        "partitions": partitions,
                    }
            finally:
                connection.close()

        race_dates = [
            str(row.get("race_date"))
            for relation in REQUIRED_RELATIONS
            for row in bundle[relation]
            if isinstance(row, Mapping) and row.get("race_date") is not None
        ]
        if not race_dates:
            raise PostRaceReviewPublishError(
                "Review snapshot has no persisted race dates"
            )

        created_at = dt.datetime.now(dt.timezone.utc).isoformat()
        manifest = {
            "artifact_type": ARTIFACT_TYPE,
            "schema_version": REVIEW_SCHEMA_VERSION,
            "review_logic_version": REVIEW_LOGIC_VERSION,
            "baseline_version": BASELINE_VERSION,
            "storage_format": "parquet",
            "compression": "zstd",
            "storage_version": STORAGE_VERSION,
            "generation_id": generation_id,
            "created_at": created_at,
            "complete_snapshot": bool(complete_snapshot),
            "source_provenance": dict(source_provenance),
            "period_from": min(race_dates),
            "period_to": max(race_dates),
            "relations": relation_manifest,
            "logical_bundle_hash": day_audit["canonical_bundle_hash"],
            "validation_status": "PASS",
        }
        generation_audit = {
            "status": "PASS",
            "review_schema_version": REVIEW_SCHEMA_VERSION,
            "review_logic_version": REVIEW_LOGIC_VERSION,
            "baseline_version": BASELINE_VERSION,
            "prepublication_audit": day_audit,
            "partition_audits": partition_audits,
        }

        manifest_path = generation_dir / "manifest.json"
        audit_path = generation_dir / "audit.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        audit_path.write_text(
            json.dumps(generation_audit, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        pointer: dict[str, object]
        if promote:
            pointer = _promote_current(root, manifest, previous)
        else:
            pointer = {
                "status": "SHADOW_PASS",
                "artifact_type": ARTIFACT_TYPE,
                "generation_id": generation_id,
                "manifest": str(manifest_path.relative_to(root)),
            }
            (root / "shadow_current.json").write_text(
                json.dumps(pointer, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        return {
            "manifest": manifest,
            "audit": generation_audit,
            "pointer": pointer,
        }
    except Exception:
        shutil.rmtree(generation_dir, ignore_errors=True)
        raise



def _database_relation_schema(connection: Any, relation: str) -> list[tuple[str, str]]:
    """Return ordered physical column name/type pairs for one relation."""
    rows = connection.execute(
        "SELECT column_name, data_type "
        "FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ? "
        "ORDER BY ordinal_position",
        [relation],
    ).fetchall()
    return [(str(row[0]), str(row[1]).upper()) for row in rows]


def _reference_relation_schemas(duckdb_module: Any) -> dict[str, list[tuple[str, str]]]:
    """Build the frozen v0.1 relation schemas from the canonical SQL."""
    connection = duckdb_module.connect(":memory:")
    try:
        connection.execute(_load_schema_sql())
        return {
            relation: _database_relation_schema(connection, relation)
            for relation in RELATIONS
        }
    finally:
        connection.close()


def _database_snapshot_audit(connection: Any, duckdb_module: Any) -> dict[str, object]:
    """Audit one staged full snapshot before immutable publication."""
    hard_errors: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    row_counts: dict[str, int] = {}
    expected_schemas = _reference_relation_schemas(duckdb_module)

    for relation in RELATIONS:
        actual_schema = _database_relation_schema(connection, relation)
        expected_schema = expected_schemas[relation]
        if actual_schema != expected_schema:
            hard_errors.append(
                {
                    "code": "SCHEMA_MISMATCH",
                    "relation": relation,
                    "expected": expected_schema,
                    "actual": actual_schema,
                }
            )
            continue

        count = int(
            connection.execute(
                f"SELECT COUNT(*) FROM {_quote_identifier(relation)}"
            ).fetchone()[0]
        )
        row_counts[relation] = count
        if relation in REQUIRED_RELATIONS and count == 0:
            hard_errors.append(
                {
                    "code": "EMPTY_REQUIRED_RELATION",
                    "relation": relation,
                }
            )

        duplicate_count = _key_duplicate_count(connection, relation)
        if duplicate_count:
            hard_errors.append(
                {
                    "code": "DUPLICATE_KEY",
                    "relation": relation,
                    "count": duplicate_count,
                }
            )

        required_keys = RELATION_KEYS[relation]
        missing_expression = " OR ".join(
            f"{_quote_identifier(column)} IS NULL"
            for column in required_keys
        )
        missing_count = int(
            connection.execute(
                f"SELECT COUNT(*) FROM {_quote_identifier(relation)} "
                f"WHERE {missing_expression}"
            ).fetchone()[0]
        )
        if missing_count:
            hard_errors.append(
                {
                    "code": "MISSING_KEY",
                    "relation": relation,
                    "count": missing_count,
                }
            )

        version_count = int(
            connection.execute(
                f"SELECT COUNT(*) FROM {_quote_identifier(relation)} "
                "WHERE review_schema_version <> ? "
                "OR review_logic_version <> ?",
                [REVIEW_SCHEMA_VERSION, REVIEW_LOGIC_VERSION],
            ).fetchone()[0]
        ) if "review_schema_version" in {
            item[0] for item in actual_schema
        } else 0
        if version_count:
            hard_errors.append(
                {
                    "code": "VERSION_CONTRACT_MISMATCH",
                    "relation": relation,
                    "count": version_count,
                }
            )

        if "baseline_version" in {item[0] for item in actual_schema}:
            baseline_count = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {_quote_identifier(relation)} "
                    "WHERE baseline_version <> ?",
                    [BASELINE_VERSION],
                ).fetchone()[0]
            )
            if baseline_count:
                hard_errors.append(
                    {
                        "code": "BASELINE_VERSION_MISMATCH",
                        "relation": relation,
                        "count": baseline_count,
                    }
                )

        numeric_columns = [
            name
            for name, data_type in actual_schema
            if data_type in {
                "DOUBLE",
                "FLOAT",
                "REAL",
                "DECIMAL",
            }
        ]
        nonfinite_count = 0
        for column in numeric_columns:
            value = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {_quote_identifier(relation)} "
                    f"WHERE {_quote_identifier(column)} IS NOT NULL "
                    f"AND NOT isfinite({_quote_identifier(column)})"
                ).fetchone()[0]
            )
            nonfinite_count += value
        if nonfinite_count:
            hard_errors.append(
                {
                    "code": "NONFINITE_NUMERIC",
                    "relation": relation,
                    "count": nonfinite_count,
                }
            )

    if not hard_errors:
        context_only = int(
            connection.execute(
                "SELECT COUNT(*) FROM ("
                "SELECT race_key FROM fact_race_context "
                "EXCEPT SELECT race_key FROM fact_race_review"
                ")"
            ).fetchone()[0]
        )
        review_only = int(
            connection.execute(
                "SELECT COUNT(*) FROM ("
                "SELECT race_key FROM fact_race_review "
                "EXCEPT SELECT race_key FROM fact_race_context"
                ")"
            ).fetchone()[0]
        )
        if context_only or review_only:
            hard_errors.append(
                {
                    "code": "RACE_RELATION_KEY_MISMATCH",
                    "context_only_count": context_only,
                    "review_only_count": review_only,
                }
            )

        orphan_count = int(
            connection.execute(
                "SELECT COUNT(*) "
                "FROM fact_horse_performance h "
                "LEFT JOIN fact_race_review r USING (race_key) "
                "WHERE r.race_key IS NULL"
            ).fetchone()[0]
        )
        if orphan_count:
            hard_errors.append(
                {
                    "code": "ORPHAN_HORSE_RACE",
                    "count": orphan_count,
                }
            )

        leakage_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM fact_race_review "
                "WHERE standard_sample_end_date IS NOT NULL "
                "AND standard_sample_end_date >= race_date"
            ).fetchone()[0]
        )
        if leakage_count:
            hard_errors.append(
                {
                    "code": "STANDARD_FUTURE_LEAKAGE",
                    "count": leakage_count,
                }
            )

    missing_standard = int(
        connection.execute(
            "SELECT COUNT(*) FROM fact_race_review "
            "WHERE historical_standard_time_sec IS NULL"
        ).fetchone()[0]
    ) if row_counts.get("fact_race_review", 0) else 0
    if missing_standard:
        warnings.append(
            {
                "code": "MISSING_TIME_STANDARD",
                "count": missing_standard,
            }
        )

    no_day_adjustment = int(
        connection.execute(
            "SELECT COUNT(*) FROM fact_race_review "
            "WHERE NOT day_adjustment_applied"
        ).fetchone()[0]
    ) if row_counts.get("fact_race_review", 0) else 0
    if no_day_adjustment:
        warnings.append(
            {
                "code": "DAY_ADJUSTMENT_NOT_APPLIED",
                "count": no_day_adjustment,
            }
        )

    no_pace = int(
        connection.execute(
            "SELECT COUNT(*) FROM fact_race_context "
            "WHERE pace_shape IS NULL"
        ).fetchone()[0]
    ) if row_counts.get("fact_race_context", 0) else 0
    if no_pace:
        warnings.append(
            {
                "code": "PACE_CLASSIFICATION_UNAVAILABLE",
                "count": no_pace,
            }
        )

    period = connection.execute(
        "SELECT MIN(race_date), MAX(race_date) FROM fact_race_review"
    ).fetchone()
    period_from = period[0].isoformat() if period and period[0] is not None else None
    period_to = period[1].isoformat() if period and period[1] is not None else None

    return {
        "status": "PASS" if not hard_errors else "FAIL",
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "review_logic_version": REVIEW_LOGIC_VERSION,
        "baseline_version": BASELINE_VERSION,
        "period_from": period_from,
        "period_to": period_to,
        "row_counts": row_counts,
        "hard_error_count": len(hard_errors),
        "warning_count": len(warnings),
        "hard_errors": hard_errors,
        "warnings": warnings,
    }


def publish_database_snapshot(
    database_path: Path,
    root: Path,
    generation_id: str,
    *,
    source_provenance: Mapping[str, object],
    promote: bool = False,
    complete_snapshot: bool = False,
) -> dict[str, object]:
    """Publish a pre-staged Review DuckDB without loading the snapshot in memory."""
    try:
        import duckdb
    except ImportError as exc:
        raise PostRaceReviewPublishError(
            "Review database publisher requires duckdb"
        ) from exc

    if promote and not complete_snapshot:
        raise PostRaceReviewPublishError(
            "canonical promotion requires complete_snapshot=True"
        )

    database_path = Path(database_path).resolve()
    if not database_path.is_file():
        raise FileNotFoundError(database_path)

    root = Path(root).resolve()
    generation_dir = root / "generations" / generation_id
    if generation_dir.exists():
        raise FileExistsError(generation_dir)

    previous = _load_current_manifest(root)
    generation_dir.mkdir(parents=True)

    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        database_audit = _database_snapshot_audit(connection, duckdb)
        if database_audit["status"] != "PASS":
            raise PostRaceReviewPublishError(
                "Review database failed pre-publication audit"
            )

        relation_manifest: dict[str, object] = {}
        partition_audits: list[dict[str, object]] = []

        with tempfile.TemporaryDirectory(
            prefix="jrdb_postrace_review_publish_"
        ) as temporary:
            temp_root = Path(temporary)

            for relation in RELATIONS:
                total_rows = int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {_quote_identifier(relation)}"
                    ).fetchone()[0]
                )
                years = [
                    int(row[0])
                    for row in connection.execute(
                        f"SELECT DISTINCT EXTRACT(YEAR FROM race_date)::INTEGER "
                        f"FROM {_quote_identifier(relation)} "
                        "WHERE race_date IS NOT NULL ORDER BY 1"
                    ).fetchall()
                ]

                partitions: list[dict[str, object]] = []
                for year in years:
                    expected_rows = int(
                        connection.execute(
                            f"SELECT COUNT(*) FROM {_quote_identifier(relation)} "
                            f"WHERE EXTRACT(YEAR FROM race_date) = {year}"
                        ).fetchone()[0]
                    )
                    candidate = temp_root / f"{relation}-{year}.parquet"
                    _write_parquet(
                        connection,
                        relation,
                        year,
                        candidate,
                    )
                    validation = _parquet_validation(
                        connection,
                        relation,
                        candidate,
                        expected_rows,
                    )
                    digest = _sha256(candidate)
                    destination = (
                        root
                        / "objects"
                        / relation
                        / f"year={year}"
                        / f"{digest}.parquet"
                    )
                    destination.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    if destination.exists():
                        if _sha256(destination) != digest:
                            raise PostRaceReviewPublishError(
                                f"content-address collision: {destination}"
                            )
                    else:
                        shutil.copy2(candidate, destination)

                    copied_validation = _parquet_validation(
                        connection,
                        relation,
                        destination,
                        expected_rows,
                    )
                    if copied_validation != validation:
                        raise PostRaceReviewPublishError(
                            f"{relation}/{year}: copied object re-read mismatch"
                        )

                    partition = {
                        "year": year,
                        "rows": expected_rows,
                        "sha256": digest,
                        "size_bytes": destination.stat().st_size,
                        "relative_path": str(
                            destination.relative_to(root)
                        ),
                    }
                    partitions.append(partition)
                    partition_audits.append(
                        {
                            "relation": relation,
                            "year": year,
                            "status": "PASS",
                            **validation,
                            "sha256": digest,
                        }
                    )

                relation_manifest[relation] = {
                    "canonical_key": list(RELATION_KEYS[relation]),
                    "sort_by": list(RELATION_SORT[relation]),
                    "total_rows": total_rows,
                    "partitions": partitions,
                }

        hash_material = [
            f"{item['relation']}|{item['year']}|{item['sha256']}"
            for item in sorted(
                partition_audits,
                key=lambda item: (
                    str(item["relation"]),
                    int(item["year"]),
                ),
            )
        ]
        snapshot_object_hash = hashlib.sha256(
            ("\n".join(hash_material) + "\n").encode("utf-8")
        ).hexdigest()

        created_at = dt.datetime.now(dt.timezone.utc).isoformat()
        manifest = {
            "artifact_type": ARTIFACT_TYPE,
            "schema_version": REVIEW_SCHEMA_VERSION,
            "review_logic_version": REVIEW_LOGIC_VERSION,
            "baseline_version": BASELINE_VERSION,
            "storage_format": "parquet",
            "compression": "zstd",
            "storage_version": STORAGE_VERSION,
            "generation_id": generation_id,
            "created_at": created_at,
            "complete_snapshot": bool(complete_snapshot),
            "source_provenance": dict(source_provenance),
            "period_from": database_audit["period_from"],
            "period_to": database_audit["period_to"],
            "relations": relation_manifest,
            "snapshot_object_hash": snapshot_object_hash,
            "validation_status": "PASS",
        }
        generation_audit = {
            "status": "PASS",
            "review_schema_version": REVIEW_SCHEMA_VERSION,
            "review_logic_version": REVIEW_LOGIC_VERSION,
            "baseline_version": BASELINE_VERSION,
            "database_audit": database_audit,
            "partition_audits": partition_audits,
        }

        manifest_path = generation_dir / "manifest.json"
        audit_path = generation_dir / "audit.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        audit_path.write_text(
            json.dumps(generation_audit, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        pointer: dict[str, object]
        if promote:
            pointer = _promote_current(root, manifest, previous)
        else:
            pointer = {
                "status": "SHADOW_PASS",
                "artifact_type": ARTIFACT_TYPE,
                "generation_id": generation_id,
                "manifest": str(manifest_path.relative_to(root)),
            }
            (root / "shadow_current.json").write_text(
                json.dumps(pointer, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        return {
            "manifest": manifest,
            "audit": generation_audit,
            "pointer": pointer,
        }
    except Exception:
        shutil.rmtree(generation_dir, ignore_errors=True)
        raise
    finally:
        connection.close()
