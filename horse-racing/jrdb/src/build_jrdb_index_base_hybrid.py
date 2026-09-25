#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build one unchanged Index Base from Historical Warehouse + current Raw.

Historical 2010-2025 is read exclusively from the accepted normalized Warehouse.
Current 2026 is read through the existing Raw parser, preserving the established
PACI/SED daily semantics.  The resulting SQLite keeps the existing Index Base
v0.1 schema so all downstream consumers remain unchanged.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from build_jrdb_index_base_from_raw import (
    OPTIONAL_KINDS,
    REQUIRED_KINDS,
    _source_meta as raw_source_meta,
    load_year as load_raw_year,
)
from jrdb_index_base_warehouse_adapter import WarehouseIndexBaseReader

VERSION = "0.1.0"
SCHEMA_VERSION = "v0.1"
HISTORICAL_YEARS = tuple(range(2010, 2026))
CURRENT_YEARS = (2026,)
ACCEPTED_GENERATION = "jrdb_normalized_warehouse_v1_2010_2025_g20260921"


def _insert_dicts(
    connection: sqlite3.Connection,
    table: str,
    rows: Iterable[dict[str, Any]],
) -> int:
    """Insert homogeneous dictionaries without changing the target schema."""
    values = list(rows)
    if not values:
        return 0
    columns = list(values[0].keys())
    sql = (
        f"INSERT INTO {table} ({','.join(columns)}) "
        f"VALUES ({','.join('?' for _ in columns)})"
    )
    connection.executemany(
        sql,
        [tuple(row[column] for column in columns) for row in values],
    )
    return len(values)


def _insert_profiles(
    connection: sqlite3.Connection,
    rows: Iterable[dict[str, Any]],
) -> None:
    """Preserve legacy snapshot semantics across Historical and current years."""
    for profile in rows:
        columns = list(profile.keys())
        connection.execute(
            f"INSERT OR IGNORE INTO horse_profile_observation ({','.join(columns)}) "
            f"VALUES ({','.join('?' for _ in columns)})",
            tuple(profile[column] for column in columns),
        )


def _insert_year_data(connection: sqlite3.Connection, data: Any) -> None:
    """Insert one already-resolved YearData object into Index Base tables."""
    _insert_dicts(connection, "race_context", data.races.values())
    _insert_dicts(connection, "race_result_context", data.result_contexts.values())
    _insert_dicts(connection, "runner_pre", data.runners.values())
    _insert_dicts(connection, "runner_previous_link", data.previous_links)
    _insert_dicts(connection, "runner_result", data.results.values())
    _insert_dicts(connection, "workout_main", data.workouts.values())
    _insert_dicts(connection, "training_analysis", data.training.values())
    _insert_profiles(connection, data.profiles)


def _asset_roots(values: list[str]) -> dict[str, Path]:
    """Parse repeatable FAMILY=/path arguments."""
    roots: dict[str, Path] = {}
    for value in values:
        family, separator, path = value.partition("=")
        if not separator or not family or not path:
            raise ValueError("--asset-root requires FAMILY=/local/staging/root")
        roots[family.upper()] = Path(path)
    return roots


def _counts(connection: sqlite3.Connection) -> dict[str, int]:
    """Return the stable Index Base population counters."""
    return {
        "race_count": connection.execute(
            "SELECT COUNT(*) FROM race_context"
        ).fetchone()[0],
        "race_result_context_count": connection.execute(
            "SELECT COUNT(*) FROM race_result_context"
        ).fetchone()[0],
        "runner_pre_count": connection.execute(
            "SELECT COUNT(*) FROM runner_pre"
        ).fetchone()[0],
        "runner_result_count": connection.execute(
            "SELECT COUNT(*) FROM runner_result"
        ).fetchone()[0],
        "workout_count": connection.execute(
            "SELECT COUNT(*) FROM workout_main"
        ).fetchone()[0],
        "training_count": connection.execute(
            "SELECT COUNT(*) FROM training_analysis"
        ).fetchone()[0],
        "profile_observation_count": connection.execute(
            "SELECT COUNT(*) FROM horse_profile_observation"
        ).fetchone()[0],
    }


def build(
    reader: WarehouseIndexBaseReader,
    raw_root: Path,
    output: Path,
    schema_path: Path,
    hash_current_archives: bool = True,
) -> dict[str, Any]:
    """Build the hybrid 2010-2026 Index Base without changing row semantics."""
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing database: {output}")
    generation_id = reader.current.get("generation_id")
    if generation_id != ACCEPTED_GENERATION:
        raise ValueError(
            f"unexpected Historical Warehouse generation: {generation_id}"
        )

    for year in CURRENT_YEARS:
        for kind in REQUIRED_KINDS:
            meta = raw_source_meta(raw_root, year, kind, hash_current_archives)
            if meta is None:
                raise FileNotFoundError(
                    f"required current Raw archive missing: {raw_root / kind / f'{kind}_{year}.zip'}"
                )

    connection = sqlite3.connect(output)
    connection.execute("PRAGMA journal_mode=MEMORY")
    connection.execute("PRAGMA synchronous=OFF")
    connection.executescript(schema_path.read_text(encoding="utf-8"))

    started = dt.datetime.now().isoformat(timespec="seconds")
    all_years = [*HISTORICAL_YEARS, *CURRENT_YEARS]
    build_id = connection.execute(
        """
        INSERT INTO meta_index_base_build(
          builder_version,schema_version,started_at,status,years_json
        ) VALUES(?,?,?,?,?)
        """,
        (
            VERSION,
            SCHEMA_VERSION,
            started,
            "RUNNING",
            json.dumps(all_years),
        ),
    ).lastrowid

    source_manifest: list[dict[str, Any]] = []
    anomaly_count = 0
    try:
        for year in HISTORICAL_YEARS:
            data, evidence = reader.load_year(year)
            for family, meta in evidence["assets"].items():
                if not meta:
                    continue
                source = {
                    "source_kind": f"WAREHOUSE_{family}",
                    "year": year,
                    "archive_path": meta["path"],
                    "archive_sha256": meta["sha256"],
                    "archive_size_bytes": meta.get("size_bytes"),
                    "member_count": meta.get("row_count"),
                }
                source_manifest.append(source)
                connection.execute(
                    """
                    INSERT INTO meta_index_base_source(
                      build_id,source_kind,year,archive_path,archive_sha256,
                      archive_size_bytes,member_count,imported_at
                    ) VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        build_id,
                        source["source_kind"],
                        source["year"],
                        source["archive_path"],
                        source["archive_sha256"],
                        source["archive_size_bytes"],
                        source["member_count"],
                        dt.datetime.now().isoformat(timespec="seconds"),
                    ),
                )
            _insert_year_data(connection, data)
            connection.commit()

        for year in CURRENT_YEARS:
            for kind in REQUIRED_KINDS + OPTIONAL_KINDS:
                meta = raw_source_meta(raw_root, year, kind, hash_current_archives)
                if meta is None:
                    anomaly_count += 1
                    connection.execute(
                        """
                        INSERT INTO meta_index_base_anomaly(
                          build_id,severity,anomaly_type,source_kind,year,detail,detected_at
                        ) VALUES(?,?,?,?,?,?,?)
                        """,
                        (
                            build_id,
                            "WARN",
                            "OPTIONAL_ARCHIVE_MISSING",
                            kind,
                            year,
                            str(raw_root / kind / f"{kind}_{year}.zip"),
                            dt.datetime.now().isoformat(timespec="seconds"),
                        ),
                    )
                    continue
                source_manifest.append(meta)
                connection.execute(
                    """
                    INSERT INTO meta_index_base_source(
                      build_id,source_kind,year,archive_path,archive_sha256,
                      archive_size_bytes,member_count,imported_at
                    ) VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        build_id,
                        meta["source_kind"],
                        meta["year"],
                        meta["archive_path"],
                        meta["archive_sha256"],
                        meta["archive_size_bytes"],
                        meta["member_count"],
                        dt.datetime.now().isoformat(timespec="seconds"),
                    ),
                )
            data = load_raw_year(raw_root, year)
            _insert_year_data(connection, data)
            connection.commit()

        counts = _counts(connection)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")

        finished = dt.datetime.now().isoformat(timespec="seconds")
        connection.execute(
            """
            UPDATE meta_index_base_build
            SET finished_at=?,status='SUCCESS',source_manifest_json=?,
                race_count=?,race_result_context_count=?,runner_pre_count=?,
                runner_result_count=?,workout_count=?,training_count=?,
                profile_observation_count=?,anomaly_count=?,message=?
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
                (
                    f"historical_source=warehouse:{generation_id};"
                    "current_source=raw:2026"
                ),
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
            "historical_source_mode": "warehouse",
            "historical_generation_id": generation_id,
            "current_source_mode": "raw",
            "current_years": list(CURRENT_YEARS),
        }
    except Exception as exc:
        connection.execute(
            """
            UPDATE meta_index_base_build
            SET finished_at=?,status='ERROR',message=?,anomaly_count=?
            WHERE build_id=?
            """,
            (
                dt.datetime.now().isoformat(timespec="seconds"),
                str(exc),
                anomaly_count,
                build_id,
            ),
        )
        connection.commit()
        raise
    finally:
        connection.close()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--warehouse-current", type=Path)
    source.add_argument("--warehouse-manifest", type=Path)
    parser.add_argument("--asset-root", action="append", required=True)
    parser.add_argument("--record-hash-compat-manifest", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "schema"
        / "jrdb_index_base_schema_v0_1.sql",
    )
    parser.add_argument(
        "--no-current-archive-hash",
        action="store_true",
        help="Skip 2026 ZIP SHA-256 calculation for exploratory runs.",
    )
    args = parser.parse_args()

    reader = WarehouseIndexBaseReader(
        args.warehouse_current,
        manifest=args.warehouse_manifest,
        asset_roots=_asset_roots(args.asset_root),
        record_hash_compat_manifest=args.record_hash_compat_manifest,
    )
    result = build(
        reader=reader,
        raw_root=args.raw_root,
        output=args.db,
        schema_path=args.schema,
        hash_current_archives=not args.no_current_archive_hash,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
