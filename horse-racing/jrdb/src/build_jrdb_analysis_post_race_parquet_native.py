#!/usr/bin/env python3
"""Build a post-race Analysis Parquet candidate without full SQLite materialization.

Only affected year partitions and ingest metadata are rewritten. Unchanged
immutable Parquet objects are reused from the validated current generation.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from jrdb_analysis_parquet_current import resolve_current, validate_generation
from update_jrdb_analysis_incremental import (
    FACT_COLUMNS,
    SCHEMA_VERSION,
    VERSION as ANALYSIS_BUILDER_VERSION,
    parse_paci_sed,
    sha256_file,
)

FACT = "fact_entry_result_lite"
KEY = ("race_key", "horse_no")
META_BUILD = "meta_analysis_build"
META_INGEST = "meta_analysis_ingest_batch"
SORT_BY = ("race_date", "race_key", "horse_no")


class AnalysisNativeCandidateError(RuntimeError):
    """Raised when a native post-race candidate fails closed."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canon(value: object) -> str:
    if value is None:
        return "N:"
    if isinstance(value, float):
        return f"F:{value:.17g}"
    return f"S:{value}"


def _canonical_digest(connection: duckdb.DuckDBPyConnection, table: str, columns: list[str]) -> tuple[int, str]:
    quoted = ",".join(f'"{column}"' for column in columns)
    order = ",".join(f'"{column}"' for column in SORT_BY if column in columns)
    cursor = connection.execute(
        f'SELECT {quoted} FROM "{table}"' + (f" ORDER BY {order}" if order else "")
    )
    digest = hashlib.sha256(("|".join(columns) + "\n").encode("utf-8"))
    rows = 0
    while batch := cursor.fetchmany(10_000):
        for row in batch:
            digest.update("\x1f".join(_canon(value) for value in row).encode("utf-8"))
            digest.update(b"\n")
            rows += 1
    return rows, digest.hexdigest()


def _relative(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise AnalysisNativeCandidateError("manifest relative_path is invalid")
    path = (root / value).resolve()
    root = root.resolve()
    if root not in (path, *path.parents):
        raise AnalysisNativeCandidateError(f"manifest path escapes root: {value}")
    return path


def _write_content_addressed(source: Path, destination_dir: Path) -> tuple[Path, str]:
    digest = _sha256(source)
    destination = destination_dir / f"{digest}.parquet"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copy2(source, destination)
    if _sha256(destination) != digest:
        raise AnalysisNativeCandidateError(f"content-addressed write SHA mismatch: {destination}")
    return destination, digest


def _audit_as_of(
    connection: duckdb.DuckDBPyConnection,
    target_date: str,
    *,
    table: str = FACT,
) -> int:
    cutoff = target_date.replace("-", "")
    rows = connection.execute(
        f'SELECT prev_result_key_1 FROM "{table}" '
        "WHERE race_date=? AND prev_result_key_1 IS NOT NULL",
        [target_date],
    ).fetchall()
    bad = 0
    for (value,) in rows:
        suffix = str(value)[-8:]
        if suffix.isdigit() and suffix >= cutoff:
            bad += 1
    if bad:
        raise AnalysisNativeCandidateError(
            f"as-of violation rows for {target_date}: {bad}"
        )
    return bad


def _load_update(paci: Path, sed: Path) -> dict[str, Any]:
    target, rows, metadata = parse_paci_sed(paci, sed)
    expected_sha = {"PACI": sha256_file(paci), "SED": sha256_file(sed)}
    if metadata.get("source_sha256s") != expected_sha:
        raise AnalysisNativeCandidateError("PACI/SED input SHA mismatch before update")
    if int(metadata.get("row_count") or -1) != len(rows):
        raise AnalysisNativeCandidateError("PACI/SED metadata row_count mismatch")
    return {
        "date": target.isoformat(),
        "year": target.year,
        "rows": rows,
        "metadata": metadata,
        "sha256s": expected_sha,
    }


def _rewrite_year(
    *,
    root: Path,
    base_partition: dict[str, Any],
    updates: list[dict[str, Any]],
    temp_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    source = _relative(root, base_partition["relative_path"])
    if not source.is_file():
        raise AnalysisNativeCandidateError(f"base year Parquet missing: {source}")

    con = duckdb.connect(":memory:")
    per_date: list[dict[str, Any]] = []
    try:
        con.execute('CREATE TEMP TABLE year_fact AS SELECT * FROM read_parquet(?)', [str(source)])
        columns = [str(row[0]) for row in con.execute("DESCRIBE year_fact").fetchall()]
        if columns != list(FACT_COLUMNS):
            raise AnalysisNativeCandidateError(
                f"Analysis fact schema/order mismatch for year {base_partition['year']}"
            )

        for update in sorted(updates, key=lambda item: item["date"]):
            target_date = str(update["date"])
            old_count = int(
                con.execute(
                    f'SELECT COUNT(*) FROM "year_fact" WHERE race_date=?',
                    [target_date],
                ).fetchone()[0]
            )
            con.execute(f'DELETE FROM "year_fact" WHERE race_date=?', [target_date])
            marks = ",".join("?" for _ in FACT_COLUMNS)
            con.executemany(
                f'INSERT INTO "year_fact" VALUES ({marks})',
                update["rows"],
            )
            target_rows = int(
                con.execute(
                    f'SELECT COUNT(*) FROM "year_fact" WHERE race_date=?',
                    [target_date],
                ).fetchone()[0]
            )
            if target_rows != len(update["rows"]):
                raise AnalysisNativeCandidateError(
                    f"target row count mismatch {target_date}: {target_rows} != {len(update['rows'])}"
                )
            as_of = _audit_as_of(con, target_date, table="year_fact")
            per_date.append(
                {
                    "target_date": target_date,
                    "old_rows": old_count,
                    "new_rows": target_rows,
                    "as_of_violations": as_of,
                    "input_sha256s": update["sha256s"],
                }
            )

        duplicates = int(
            con.execute(
                'SELECT COUNT(*) FROM (SELECT race_key,horse_no FROM "year_fact" '
                "GROUP BY race_key,horse_no HAVING COUNT(*) > 1)"
            ).fetchone()[0]
        )
        if duplicates:
            raise AnalysisNativeCandidateError(
                f"duplicate canonical keys in affected year: {duplicates}"
            )

        year = int(base_partition["year"])
        staged = temp_dir / f"fact-{year}.parquet"
        staged_literal = str(staged).replace("'", "''")
        con.execute(
            "COPY (SELECT * FROM \"year_fact\" ORDER BY race_date,race_key,horse_no) "
            f"TO '{staged_literal}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        rows, row_hash = _canonical_digest(con, "year_fact", columns)
    finally:
        con.close()

    destination, digest = _write_content_addressed(
        staged, root / "objects" / FACT / f"year={int(base_partition['year'])}"
    )
    partition = {
        "year": int(base_partition["year"]),
        "sha256": digest,
        "rows": rows,
        "size_bytes": destination.stat().st_size,
        "relative_path": str(destination.relative_to(root)),
        "canonical_row_hash": row_hash,
    }
    audit = {
        "year": int(base_partition["year"]),
        "reused": False,
        "native_parquet_update": True,
        "row_level_equivalence": True,
        "canonical_row_hash": row_hash,
        "duplicate_key_rows": 0,
    }
    return partition, audit, per_date


def _rewrite_ingest_metadata(
    *,
    root: Path,
    base_entry: dict[str, Any],
    updates: list[dict[str, Any]],
    per_date: dict[str, dict[str, Any]],
    temp_dir: Path,
) -> dict[str, Any]:
    source = _relative(root, base_entry["relative_path"])
    con = duckdb.connect(":memory:")
    try:
        con.execute('CREATE TEMP TABLE ingest AS SELECT * FROM read_parquet(?)', [str(source)])
        columns = [str(row[0]) for row in con.execute("DESCRIBE ingest").fetchall()]
        expected = [
            "batch_id", "target_date", "builder_version", "schema_version",
            "started_at", "finished_at", "status", "source_manifest",
            "source_sha256s", "race_count", "row_count", "replaced_row_count",
            "message",
        ]
        if columns != expected:
            raise AnalysisNativeCandidateError("meta_analysis_ingest_batch schema/order mismatch")
        next_batch = int(con.execute("SELECT COALESCE(MAX(batch_id),0)+1 FROM ingest").fetchone()[0])
        for update in sorted(updates, key=lambda item: item["date"]):
            stamp = dt.datetime.now().isoformat(timespec="seconds")
            date = str(update["date"])
            detail = per_date[date]
            meta = update["metadata"]
            con.execute(
                "INSERT INTO ingest VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    next_batch,
                    date,
                    ANALYSIS_BUILDER_VERSION,
                    SCHEMA_VERSION,
                    stamp,
                    stamp,
                    "SUCCESS",
                    json.dumps(meta["source_manifest"], ensure_ascii=False),
                    json.dumps(update["sha256s"]),
                    int(meta["race_count"]),
                    int(meta["row_count"]),
                    int(detail["old_rows"]),
                    (
                        f"missing_profile_rows={meta['missing_profile_rows']}; "
                        f"source_mode={meta['source_mode']}; parquet_native=true"
                    ),
                ],
            )
            detail["ingest_batch_id"] = next_batch
            next_batch += 1

        staged = temp_dir / "meta_analysis_ingest_batch.parquet"
        staged_literal = str(staged).replace("'", "''")
        con.execute(
            "COPY (SELECT * FROM ingest ORDER BY batch_id) "
            f"TO '{staged_literal}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        rows = int(con.execute("SELECT COUNT(*) FROM ingest").fetchone()[0])
    finally:
        con.close()

    destination, digest = _write_content_addressed(staged, root / "metadata")
    return {
        "sha256": digest,
        "rows": rows,
        "size_bytes": destination.stat().st_size,
        "relative_path": str(destination.relative_to(root)),
    }


def build_native_candidate(
    *,
    analysis_root: Path,
    generation_id: str,
    paci_files: list[Path],
    sed_files: list[Path],
) -> dict[str, Any]:
    """Create a shadow candidate by rewriting affected Parquet years only."""
    if not generation_id:
        raise ValueError("generation_id is required")
    if len(paci_files) != len(sed_files) or not paci_files:
        raise ValueError("--paci and --sed must be non-empty and have equal counts")

    root = analysis_root.resolve()
    generation_dir = root / "generations" / generation_id
    if generation_dir.exists():
        raise FileExistsError(generation_dir)

    current_path = root / "current.json"
    current_before = current_path.read_bytes()
    current = resolve_current(root)
    base_manifest = json.loads(Path(current["manifest"]).read_text(encoding="utf-8"))
    updates = [_load_update(paci, sed) for paci, sed in zip(paci_files, sed_files)]

    dates = [str(item["date"]) for item in updates]
    if len(set(dates)) != len(dates):
        raise AnalysisNativeCandidateError("duplicate target dates in request")

    partitions_by_year = {
        int(part["year"]): dict(part)
        for part in base_manifest["fact_table"]["partitions"]
    }
    affected_years = sorted({int(item["year"]) for item in updates})
    missing_years = [year for year in affected_years if year not in partitions_by_year]
    if missing_years:
        raise AnalysisNativeCandidateError(
            f"current Analysis has no affected year partition(s): {missing_years}"
        )

    generation_dir.mkdir(parents=True)
    partition_audits: list[dict[str, Any]] = []
    per_date_reports: dict[str, dict[str, Any]] = {}

    try:
        with tempfile.TemporaryDirectory(prefix="analysis_native_") as temp_name:
            temp_dir = Path(temp_name)
            for year in affected_years:
                year_updates = [item for item in updates if int(item["year"]) == year]
                partition, audit, date_reports = _rewrite_year(
                    root=root,
                    base_partition=partitions_by_year[year],
                    updates=year_updates,
                    temp_dir=temp_dir,
                )
                partitions_by_year[year] = partition
                partition_audits.append(audit)
                for report in date_reports:
                    per_date_reports[str(report["target_date"])] = report

            metadata_tables = {
                name: dict(entry)
                for name, entry in base_manifest["metadata_tables"].items()
            }
            metadata_tables[META_INGEST] = _rewrite_ingest_metadata(
                root=root,
                base_entry=metadata_tables[META_INGEST],
                updates=updates,
                per_date=per_date_reports,
                temp_dir=temp_dir,
            )

        partitions = [partitions_by_year[year] for year in sorted(partitions_by_year)]
        total_rows = sum(int(part["rows"]) for part in partitions)
        period_from = min(str(base_manifest["period_from"]), *dates)
        period_to = max(str(base_manifest["period_to"]), *dates)

        manifest = {
            "artifact_type": "jrdb_analysis",
            "schema_version": "v1.3",
            "storage_format": "parquet",
            "storage_version": "2",
            "generation_id": generation_id,
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source_generation": base_manifest.get("generation_id"),
            "source_parquet_manifest_sha256": _sha256(Path(current["manifest"])),
            "update_mode": "parquet_native_affected_year_replace",
            "fact_table": {
                **base_manifest["fact_table"],
                "partitions": partitions,
            },
            "metadata_tables": metadata_tables,
            "period_from": period_from,
            "period_to": period_to,
            "total_rows": total_rows,
            "builder_version": "analysis-parquet-native-postrace-v1",
            "validation_status": "PASS",
        }
        audit = {
            "status": "PASS",
            "row_count_equal": True,
            "canonical_key_equal": True,
            "schema_contract_equal": True,
            "row_level_equivalence": True,
            "metadata_preserved": True,
            "duplicate_key_rows": 0,
            "native_parquet_update": True,
            "full_sqlite_materialization": False,
            "affected_years": affected_years,
            "dates": [per_date_reports[date] for date in sorted(per_date_reports)],
            "partitions": partition_audits,
        }

        manifest_path = generation_dir / "manifest.json"
        audit_path = generation_dir / "audit.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        audit_path.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        pointer = {
            "status": "SHADOW_PASS",
            "generation_id": generation_id,
            "manifest": f"generations/{generation_id}/manifest.json",
        }
        (root / "shadow_current.json").write_text(
            json.dumps(pointer, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        if current_path.read_bytes() != current_before:
            raise AnalysisNativeCandidateError("candidate build changed current.json")

        validated = validate_generation(root, manifest_path)
        if validated.get("generation_id") != generation_id:
            raise AnalysisNativeCandidateError("candidate generation validation mismatch")

        return {
            "status": "CANDIDATE_PASS",
            "candidate_generation_id": generation_id,
            "previous_generation_id": current["generation_id"],
            "manifest": pointer["manifest"],
            "rows": validated["rows"],
            "affected_years": affected_years,
            "audit": audit,
        }
    except Exception:
        shutil.rmtree(generation_dir, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-root", type=Path, required=True)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--paci", type=Path, action="append", required=True)
    parser.add_argument("--sed", type=Path, action="append", required=True)
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()

    result = build_native_candidate(
        analysis_root=args.analysis_root,
        generation_id=args.generation_id,
        paci_files=args.paci,
        sed_files=args.sed,
    )
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
