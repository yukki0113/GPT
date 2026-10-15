"""Build deterministic race-level Parquet from canonical SED ZIP snapshots.

Fixed-width parsing and distance normalization remain owned by the common Raw
Reader and jrdb_race_lap. There is deliberately no acquisition or consumer logic.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import tempfile
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jrdb_raw import Parser, ReaderAudit, canonical_members, read_fixed_records
from jrdb_race_lap import normalize_race_laps
from jrdb_race_lap_contract import (
    COLUMN_TYPES, DATASET_SCHEMA_VERSION, LOGIC_VERSION, decode_row,
    normalize_race_key, optional_context_available,
)
from jrdb_race_lap_shape import shape_from_segments
from jrdb_race_lap_store import RaceLapStore


def build_archive_rows(archive: Path) -> list[dict[str, Any]]:
    audit = ReaderAudit()
    parser = Parser(audit)
    metadata: dict[str, dict[str, Any]] = {}
    result = []
    seen = set()
    with zipfile.ZipFile(archive) as zf:
        sed_members = canonical_members(zf, "SED")
        srb_members = canonical_members(zf, "SRB")
        if not sed_members or not srb_members:
            raise ValueError(f"SED and SRB members required: {archive}")
        for member in sed_members:
            for record in read_fixed_records(zf, member, "SED", audit):
                parsed = parser.sed(record)
                key = normalize_race_key(parsed["race_key_raw"])
                date_raw = parsed.get("date_raw") or ""
                if len(date_raw) != 8 or not date_raw.isdigit():
                    raise ValueError(f"invalid SED date: {key}")
                date = dt.datetime.strptime(date_raw, "%Y%m%d").date().isoformat()
                distance = parsed.get("distance_m")
                if type(distance) not in (int, float) or int(distance) != distance or distance <= 0:
                    raise ValueError(f"invalid SED distance: {key}")
                row = {"race_key": key, "race_date": date,
                       "surface_code": str(parsed.get("surface_code") or "").strip(),
                       "distance_m": int(distance), "source_sed_member": member}
                if key in metadata and metadata[key] != row:
                    raise ValueError(f"inconsistent SED race metadata: {key}")
                metadata[key] = row
        for member in srb_members:
            for record in read_fixed_records(zf, member, "SRB", audit):
                parsed = parser.srb(record)
                key = normalize_race_key(parsed["race_key_raw"])
                if key in seen:
                    raise ValueError(f"duplicate SRB race_key: {key}")
                seen.add(key)
                if key not in metadata:
                    raise ValueError(f"SED metadata missing for SRB race: {key}")
                meta = metadata[key]
                segments = normalize_race_laps(parsed, distance_m=meta["distance_m"])
                bias = parsed.get("track_bias_raw") or {}
                comment = (parsed.get("race_comment") or "").strip() or None
                pace = parsed.get("pace_up_remaining_furlongs")
                if pace is not None and (not isinstance(pace, (int, float)) or int(pace) != pace):
                    raise ValueError(f"invalid SRB pace-up: {key}")
                optional = optional_context_available(pace, bias, comment)
                shape = shape_from_segments(segments, pace, optional)
                coverage = dict(shape["coverage"])
                coverage["coverage_status"] = coverage.pop("status")
                row = {
                    **meta, **coverage, **shape["lap_shape"],
                    "lap_count": len(segments),
                    "partial_first_segment": bool(segments and segments[0]["segment_distance_m"] != 200),
                    "segment_distances_m": [s["segment_distance_m"] for s in segments],
                    "lap_times_sec": [s["lap_sec"] for s in segments],
                    "track_bias_raw_json": json.dumps(bias, ensure_ascii=False, sort_keys=True, allow_nan=False),
                    "race_comment": comment, "source_archive": archive.name,
                    "source_srb_member": member, "dataset_schema_version": DATASET_SCHEMA_VERSION,
                    "shape_logic_version": LOGIC_VERSION,
                }
                decode_row(row)
                result.append(row)
        if audit.record_length_errors:
            raise ValueError(f"invalid fixed-record lengths: {dict(audit.record_length_errors)}")
        missing = metadata.keys() - seen
        if missing:
            raise ValueError(f"SRB records missing for SED races: {sorted(missing)}")
    if not result:
        raise ValueError(f"no race records: {archive}")
    return result


def build_rows(archives: Iterable[Path]) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for archive in archives:
        for row in build_archive_rows(Path(archive)):
            key = row["race_key"]
            if key in seen:
                raise ValueError(f"duplicate race_key across archives: {key}")
            seen.add(key)
            rows.append(row)
    if not rows:
        raise ValueError("at least one populated canonical SED archive is required")
    return sorted(rows, key=lambda row: (row["race_date"], row["race_key"]))


def _publish(staged: Path, target: Path, replace: bool) -> None:
    if replace:
        os.replace(staged, target)
    else:
        # Atomic no-clobber publication even if another builder races this one.
        os.link(staged, target)
        staged.unlink()


def build_dataset(archives: Iterable[Path], output: Path, audit: Path, *, replace: bool = False) -> dict[str, Any]:
    import duckdb

    archives = [Path(p).resolve() for p in archives]
    output, audit = Path(output).resolve(), Path(audit).resolve()
    if output == audit or output in archives or audit in archives:
        raise ValueError("output, audit and input paths must be distinct")
    for path in (output, audit):
        if path.exists() and not replace:
            raise FileExistsError(f"output exists (use --replace): {path}")
    rows = build_rows(archives)
    for path in (output, audit):
        path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".race-lap-", suffix=".parquet", dir=output.parent)
    os.close(fd)
    staged = Path(name)
    staged_audit: Path | None = None
    try:
        connection = duckdb.connect(":memory:")
        try:
            connection.execute("SET threads=1")
            declarations = ", ".join(f'"{key}" {kind}' for key, kind in COLUMN_TYPES.items())
            connection.execute(f"CREATE TABLE race_lap ({declarations})")
            marks = ", ".join("?" for _ in COLUMN_TYPES)
            connection.executemany(f"INSERT INTO race_lap VALUES ({marks})",
                                   [[row[key] for key in COLUMN_TYPES] for row in rows])
            # DuckDB 1.1.3 COPY's path is a SQL literal; escape it as a literal,
            # never interpolate user keys. All lookup predicates are bound.
            literal = "'" + str(staged).replace("'", "''") + "'"
            connection.execute(f"COPY (SELECT * FROM race_lap ORDER BY race_date, race_key) TO {literal} (FORMAT PARQUET, COMPRESSION ZSTD)")
        finally:
            connection.close()
        store = RaceLapStore(staged)
        report = {
            "input_archive_count": len(archives), "race_count": len(rows),
            "available_count": sum(r["coverage_status"] == "AVAILABLE" for r in rows),
            "no_laps_count": sum(r["coverage_status"] == "NO_LAPS" for r in rows),
            "partial_first_count": sum(r["partial_first_segment"] for r in rows),
            "optional_context_available_count": sum(r["optional_srb_context_available"] for r in rows),
            "min_race_date": store.metadata()["min_race_date"],
            "max_race_date": store.metadata()["max_race_date"],
            "duplicate_count": 0, "validation_status": "PASS",
            "output_sha256": hashlib.sha256(staged.read_bytes()).hexdigest(),
            "output_size_bytes": staged.stat().st_size,
            "dataset_schema_version": DATASET_SCHEMA_VERSION, "shape_logic_version": LOGIC_VERSION,
        }
        fd, name = tempfile.mkstemp(prefix=".race-lap-", suffix=".json", dir=audit.parent)
        staged_audit = Path(name)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        _publish(staged, output, replace)
        _publish(staged_audit, audit, replace)
        return report
    finally:
        staged.unlink(missing_ok=True)
        if staged_audit is not None:
            staged_audit.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    try:
        report = build_dataset(args.archives, args.output, args.audit, replace=args.replace)
    except (ValueError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"race-lap build failed: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
