#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the unchanged JRDB Index Base v0.1 from accepted Historical Warehouse."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from jrdb_index_base_warehouse_adapter import (
    MAX_YEAR,
    MIN_YEAR,
    WarehouseIndexBaseReader,
)

VERSION = "0.1.0"
SCHEMA_VERSION = "v0.1"


def _insert_dicts(connection: sqlite3.Connection, table: str, rows: Iterable[dict[str, Any]]) -> int:
    values = list(rows)
    if not values:
        return 0
    columns = list(values[0].keys())
    sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"
    connection.executemany(sql, [tuple(row[column] for column in columns) for row in values])
    return len(values)


def build(
    reader: WarehouseIndexBaseReader,
    years: list[int],
    output: Path,
    schema_path: Path,
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing database: {output}")
    if not years:
        raise ValueError("years are required")
    if min(years) < MIN_YEAR or max(years) > MAX_YEAR:
        raise ValueError("Historical Warehouse build is restricted to 2010-2025")

    connection = sqlite3.connect(output)
    connection.execute("PRAGMA journal_mode=MEMORY")
    connection.execute("PRAGMA synchronous=OFF")
    connection.executescript(schema_path.read_text(encoding="utf-8"))
    started = dt.datetime.now().isoformat(timespec="seconds")
    build_id = connection.execute(
        """
        INSERT INTO meta_index_base_build(
          builder_version,schema_version,started_at,status,years_json
        ) VALUES(?,?,?,?,?)
        """,
        (VERSION, SCHEMA_VERSION, started, "RUNNING", json.dumps(sorted(years))),
    ).lastrowid
    anomaly_count = 0
    source_manifest: list[dict[str, Any]] = []
    try:
        for year in sorted(years):
            data, evidence = reader.load_year(year)
            for family, meta in evidence["assets"].items():
                if not meta:
                    continue
                source_manifest.append({"family": family, "year": year, **meta})
                connection.execute(
                    """
                    INSERT INTO meta_index_base_source(
                      build_id,source_kind,year,archive_path,archive_sha256,
                      archive_size_bytes,member_count,imported_at
                    ) VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        build_id,
                        f"WAREHOUSE_{family}",
                        year,
                        meta["path"],
                        meta["sha256"],
                        meta.get("size_bytes"),
                        meta.get("row_count"),
                        dt.datetime.now().isoformat(timespec="seconds"),
                    ),
                )

            _insert_dicts(connection, "race_context", data.races.values())
            _insert_dicts(connection, "race_result_context", data.result_contexts.values())
            _insert_dicts(connection, "runner_pre", data.runners.values())
            _insert_dicts(connection, "runner_previous_link", data.previous_links)
            _insert_dicts(connection, "runner_result", data.results.values())
            _insert_dicts(connection, "workout_main", data.workouts.values())
            _insert_dicts(connection, "training_analysis", data.training.values())
            for profile in data.profiles:
                columns = list(profile.keys())
                connection.execute(
                    f"INSERT OR IGNORE INTO horse_profile_observation ({','.join(columns)}) "
                    f"VALUES ({','.join('?' for _ in columns)})",
                    tuple(profile[column] for column in columns),
                )
            connection.commit()

        counts = {
            "race_count": connection.execute("SELECT COUNT(*) FROM race_context").fetchone()[0],
            "race_result_context_count": connection.execute("SELECT COUNT(*) FROM race_result_context").fetchone()[0],
            "runner_pre_count": connection.execute("SELECT COUNT(*) FROM runner_pre").fetchone()[0],
            "runner_result_count": connection.execute("SELECT COUNT(*) FROM runner_result").fetchone()[0],
            "workout_count": connection.execute("SELECT COUNT(*) FROM workout_main").fetchone()[0],
            "training_count": connection.execute("SELECT COUNT(*) FROM training_analysis").fetchone()[0],
            "profile_observation_count": connection.execute("SELECT COUNT(*) FROM horse_profile_observation").fetchone()[0],
        }
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")
        finished = dt.datetime.now().isoformat(timespec="seconds")
        connection.execute(
            """
            UPDATE meta_index_base_build
            SET finished_at=?,status='SUCCESS',source_manifest_json=?,
                race_count=?,race_result_context_count=?,runner_pre_count=?,runner_result_count=?,
                workout_count=?,training_count=?,profile_observation_count=?,anomaly_count=?,
                message=?
            WHERE build_id=?
            """,
            (
                finished,
                json.dumps(source_manifest, ensure_ascii=False),
                counts["race_count"],
                counts["race_result_context_count"],
                counts["runner_pre_count"],
                counts["runner_result_count"],
                counts["workout_count"],
                counts["training_count"],
                counts["profile_observation_count"],
                anomaly_count,
                f"source_generation_id={reader.current.get('generation_id')}",
                build_id,
            ),
        )
        connection.commit()
        connection.execute("ANALYZE")
        connection.commit()
        return {
            **counts,
            "anomaly_count": anomaly_count,
            "integrity_check": integrity,
            "size_bytes": output.stat().st_size,
            "build_id": build_id,
            "source_generation_id": reader.current.get("generation_id"),
        }
    except Exception as exc:
        connection.execute(
            """
            UPDATE meta_index_base_build
            SET finished_at=?,status='ERROR',message=?,anomaly_count=?
            WHERE build_id=?
            """,
            (dt.datetime.now().isoformat(timespec="seconds"), str(exc), anomaly_count, build_id),
        )
        connection.commit()
        raise
    finally:
        connection.close()


def _asset_roots(values: list[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        family, sep, path = value.partition("=")
        if not sep or not family or not path:
            raise ValueError("--asset-root requires FAMILY=/local/staging/root")
        roots[family.upper()] = Path(path)
    return roots


def main() -> None:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--warehouse-current", type=Path)
    source.add_argument("--warehouse-manifest", type=Path)
    parser.add_argument("--asset-root", action="append", required=True)
    parser.add_argument("--record-hash-compat-manifest", type=Path)
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "schema" / "jrdb_index_base_schema_v0_1.sql",
    )
    args = parser.parse_args()
    reader = WarehouseIndexBaseReader(
        args.warehouse_current,
        manifest=args.warehouse_manifest,
        asset_roots=_asset_roots(args.asset_root),
        record_hash_compat_manifest=args.record_hash_compat_manifest,
    )
    result = build(reader, args.years, args.db, args.schema)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
