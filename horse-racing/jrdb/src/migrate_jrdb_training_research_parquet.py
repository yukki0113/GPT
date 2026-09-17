#!/usr/bin/env python3
"""Create one immutable JRDB Training Research Parquet generation.

SQLite remains a build-time comparison materialization only.  Conversion and basic
storage validation are delegated to the repository-wide ``tools/data-storage``
package; this module adds the JRDB-specific provenance, holdout, and scientific
non-regression gates.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "data-storage"))

from data_storage.convert import convert
from data_storage.validate import validate
from analyze_jrdb_training_stage1b import analyze

VERSION = "1"
CANONICAL_KEY = ["race_key", "horse_no"]
HOLDOUT_COLUMNS = [
    "race_date", "year", "race_key", "horse_no", "horse_id", "horse_name", "trainer_code",
    "course_code", "furlong_count", "final_segment_sec", "training_type_code",
    "training_course_type_code", "used_slope", "used_wood", "used_dirt", "used_turf",
    "used_pool", "used_jump", "used_polytrack", "rotation_interval", "days_since_last_run",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _schema_hash(columns: Iterable[tuple[Any, ...]]) -> str:
    normalized = [{"name": row[0], "type": row[1], "null": row[2]} for row in columns]
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()


def _write_subset(source: Path, target: Path, table: str, query: str) -> None:
    # A temporary SQLite materialization keeps the shared converter's SQLite
    # table contract intact while avoiding a second Parquet writer in JRDB.
    with sqlite3.connect(target) as write:
        write.execute("ATTACH DATABASE ? AS source_db", (str(source),))
        write.execute(f'CREATE TABLE "{table}" AS {query.replace("training_runner", "source_db.training_runner").replace("source_archive", "source_db.source_archive")}')
        write.execute("DETACH DATABASE source_db")
        write.commit()


def _config(source: Path, table: str, target: Path, keys: list[str], sort_by: list[str]) -> dict[str, Any]:
    return {
        "source": {"format": "sqlite", "path": str(source), "table": table, "batch_size": 50_000},
        "target": {"format": "parquet", "path": str(target), "compression": "zstd", "partition_by": []},
        "keys": {"canonical": keys}, "sort_by": sort_by,
        "validation": {"require_unique_key": bool(keys), "require_row_count_match": True},
    }


def _convert(source: Path, table: str, target: Path, keys: list[str], sort_by: list[str]) -> dict[str, Any]:
    config = _config(source, table, target, keys, sort_by)
    converted = convert(config)
    report = validate(config, converted)
    if not report["passed"]:
        raise RuntimeError(f"storage validation failed for {target.name}: {report}")
    return {"conversion": converted, "validation": report}


def _rows_sqlite(path: Path, table: str, columns: list[str], order: list[str]):
    names = ",".join(f'"{name}"' for name in columns)
    ordering = ",".join(f'"{name}"' for name in order)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        cursor = connection.execute(f'SELECT {names} FROM "{table}" ORDER BY {ordering}')
        while rows := cursor.fetchmany(50_000):
            yield rows
    finally:
        connection.close()


def _rows_parquet(path: Path, columns: list[str], order: list[str]):
    from data_storage.query import connect_parquet
    names = ",".join(f'"{name}"' for name in columns)
    ordering = ",".join(f'"{name}"' for name in order)
    connection = connect_parquet(path)
    try:
        cursor = connection.execute(f"SELECT {names} FROM data ORDER BY {ordering}")
        while rows := cursor.fetchmany(50_000):
            yield rows
    finally:
        connection.close()


def _exact_rows(source: Path, table: str, parquet: Path, columns: list[str], order: list[str]) -> dict[str, Any]:
    """Full ordered equality comparison, including binary source_record_hash values."""
    source_rows = _rows_sqlite(source, table, columns, order)
    target_rows = _rows_parquet(parquet, columns, order)
    count = 0
    while True:
        left = next(source_rows, None)
        right = next(target_rows, None)
        if left is None or right is None:
            if left != right:
                raise RuntimeError("row stream length mismatch")
            break
        if len(left) != len(right):
            raise RuntimeError("batch row count mismatch")
        for source_row, target_row in zip(left, right):
            # DuckDB returns bytearray for BLOB on some platforms.
            normalized_target = tuple(bytes(value) if isinstance(value, bytearray) else value for value in target_row)
            if source_row != normalized_target:
                raise RuntimeError(f"full row mismatch after {count} rows")
            count += 1
    return {"pass": True, "rows_compared": count, "columns": columns}


def _metadata(source: Path) -> dict[str, Any]:
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as db:
        row = db.execute("SELECT * FROM meta_training_research_build ORDER BY build_id DESC LIMIT 1").fetchone()
        names = [item[0] for item in db.execute("SELECT * FROM meta_training_research_build LIMIT 0").description]
        if row is None:
            raise RuntimeError("meta_training_research_build is empty")
        archive = [dict(zip(("source_kind", "source_year", "source_member_count", "archive_size_bytes", "archive_sha256"), values))
                   for values in db.execute("SELECT source_kind,source_year,source_member_count,archive_size_bytes,archive_sha256 FROM source_archive ORDER BY source_kind,source_year")]
    return {"build": dict(zip(names, row)), "source_archive_rows": len(archive)}


def _assert_holdout_locked(path: Path) -> dict[str, Any]:
    from data_storage.query import connect_parquet
    db = connect_parquet(path)
    try:
        columns = [row[0] for row in db.execute("DESCRIBE data").fetchall()]
        years = db.execute("SELECT MIN(year), MAX(year), COUNT(*) FROM data").fetchone()
    finally:
        db.close()
    forbidden = sorted(set(columns) & {"finish", "finish_percentile", "official_runperf_raw", "runperf_score_status", "runperf_provenance"})
    if columns != HOLDOUT_COLUMNS or forbidden or years[0] != 2024 or years[1] != 2025:
        raise RuntimeError("holdout locked contract failed")
    return {"pass": True, "columns": columns, "min_year": years[0], "max_year": years[1], "row_count": years[2]}


def _parquet_period(path: Path, column: str) -> dict[str, str | None]:
    """Return the actual min/max period represented by one Parquet asset."""
    from data_storage.query import connect_parquet
    db = connect_parquet(path)
    try:
        lower, upper = db.execute(f'SELECT MIN("{column}"), MAX("{column}") FROM data').fetchone()
    finally:
        db.close()
    return {
        "period_from": None if lower is None else str(lower),
        "period_to": None if upper is None else str(upper),
    }


def _compare_values(left: Any, right: Any, path: str = "root") -> list[str]:
    if isinstance(left, float) or isinstance(right, float):
        if left is None or right is None or abs(float(left) - float(right)) > 1e-12:
            return [path]
        return []
    if isinstance(left, dict) and isinstance(right, dict):
        return sum((_compare_values(left.get(key), right.get(key), f"{path}.{key}") for key in sorted(set(left) | set(right))), [])
    if isinstance(left, list) and isinstance(right, list):
        return sum((_compare_values(a, b, f"{path}[{index}]") for index, (a, b) in enumerate(zip(left, right))), []) + ([] if len(left) == len(right) else [path])
    return [] if left == right else [path]


def migrate(source: Path, output_root: Path, build_id: str, delete_source: bool = False) -> dict[str, Any]:
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    destination = output_root.resolve() / f"build-{build_id}"
    if destination.exists():
        raise FileExistsError(f"immutable generation already exists: {destination}")
    destination.mkdir(parents=True)
    before = {"filename": source.name, "size_bytes": source.stat().st_size, "sha256": _sha256(source)}
    metadata = _metadata(source)
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as db:
        runner_columns = [row[1] for row in db.execute("PRAGMA table_info(training_runner)")]
    try:
        runner_path = destination / "training_runner.parquet"
        runner = _convert(source, "training_runner", runner_path, CANONICAL_KEY, ["race_date", *CANONICAL_KEY])
        runner_exact = _exact_rows(source, "training_runner", runner_path, runner_columns, ["race_date", *CANONICAL_KEY])
        with tempfile.TemporaryDirectory(prefix="jrdb_training_parquet_") as temp:
            temp_root = Path(temp)
            development_db, holdout_db, archive_db = temp_root / "development.sqlite", temp_root / "holdout.sqlite", temp_root / "archive.sqlite"
            _write_subset(source, development_db, "training_development", "SELECT * FROM training_runner WHERE year BETWEEN 2010 AND 2023")
            holdout_select = ",".join(f'"{column}"' for column in HOLDOUT_COLUMNS)
            _write_subset(source, holdout_db, "training_holdout_locked", f"SELECT {holdout_select} FROM training_runner WHERE year BETWEEN 2024 AND 2025")
            _write_subset(source, archive_db, "source_archive", "SELECT * FROM source_archive")
            development_path = destination / "training_development.parquet"
            holdout_path = destination / "training_holdout_locked.parquet"
            archive_path = destination / "source_archive.parquet"
            development = _convert(development_db, "training_development", development_path, CANONICAL_KEY, ["race_date", *CANONICAL_KEY])
            holdout = _convert(holdout_db, "training_holdout_locked", holdout_path, CANONICAL_KEY, ["race_date", *CANONICAL_KEY])
            archive = _convert(archive_db, "source_archive", archive_path, ["source_kind", "source_year"], ["source_kind", "source_year"])
            development_exact = _exact_rows(development_db, "training_development", development_path, runner_columns, ["race_date", *CANONICAL_KEY])
            holdout_exact = _exact_rows(holdout_db, "training_holdout_locked", holdout_path, HOLDOUT_COLUMNS, ["race_date", *CANONICAL_KEY])
            archive_exact = _exact_rows(archive_db, "source_archive", archive_path, ["source_kind", "source_year", "archive_sha256"], ["source_kind", "source_year"])
        locked = _assert_holdout_locked(holdout_path)
        sqlite_stage1b = analyze(source, "sqlite")
        parquet_stage1b = analyze(development_path, "parquet")
        differences = _compare_values(sqlite_stage1b, parquet_stage1b)
        scientific = {"pass": not differences, "tolerance": 1e-12, "differences": differences,
                      "sqlite": sqlite_stage1b, "parquet": parquet_stage1b}
        if differences:
            raise RuntimeError(f"scientific regression failed: {differences[:5]}")
        assets: dict[str, dict[str, Any]] = {}
        period_columns = {
            "training_runner.parquet": "race_date",
            "training_development.parquet": "race_date",
            "training_holdout_locked.parquet": "race_date",
            "source_archive.parquet": "source_year",
        }
        for filename, result in {
            "training_runner.parquet": runner, "training_development.parquet": development,
            "training_holdout_locked.parquet": holdout, "source_archive.parquet": archive,
        }.items():
            path = destination / filename
            validation = result["validation"]
            assets[filename] = {"filename": filename, "size_bytes": path.stat().st_size, "sha256": _sha256(path),
                                "row_count": validation["row_count_target"], "schema_hash": validation["schema_hash"],
                                **_parquet_period(path, period_columns[filename])}
        source_build = dict(metadata["build"])
        source_build_id = source_build.pop("build_id", None)
        manifest = {"artifact_type": "jrdb_training_research", "schema_version": "v0.1", "storage_format": "parquet",
                    "storage_version": VERSION, "canonical_key": CANONICAL_KEY,
                    "generation_id": build_id, "source_build_id": source_build_id,
                    **source_build, "source_sqlite": before, "assets": assets,
                    "logical_uris": {"jrdb://training-research/v0.1": "training_runner.parquet",
                                     "jrdb://training-research/v0.1/development": "training_development.parquet",
                                     "jrdb://training-research/v0.1/holdout-locked": "training_holdout_locked.parquet"}}
        audit = {"status": "PASS", "source": before, "runner": {**runner, "exact": runner_exact},
                 "development": {**development, "exact": development_exact}, "holdout": {**holdout, "exact": holdout_exact, "locked_contract": locked},
                 "source_archive": {**archive, "exact": archive_exact}, "source_record_hash": runner_exact,
                 "metadata": metadata}
        (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (destination / "conversion_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (destination / "scientific_regression.json").write_text(json.dumps(scientific, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (output_root.resolve() / "current.json").write_text(json.dumps({"status": "SUCCESS", "build_id": build_id, "generation_id": build_id, "manifest": f"build-{build_id}/manifest.json"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if delete_source:
            source.unlink()
            audit["source_deletion"] = {"performed": True, **before}
            (destination / "conversion_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"status": "SUCCESS", "build_directory": str(destination), "manifest": manifest, "audit": audit, "scientific_regression": scientific}
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sqlite", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--build-id", default=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--delete-source-after-success", action="store_true")
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()
    result = migrate(args.source_sqlite, args.output_root, args.build_id, args.delete_source_after_success)
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "build_directory": result["build_directory"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
