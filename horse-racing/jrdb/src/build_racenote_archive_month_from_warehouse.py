#!/usr/bin/env python3
"""Build one Historical RaceNote Archive month from accepted JRDB Warehouse.

This is the production upstream for new 2010--2025 Archive shards.  It keeps
the existing Archive format and RaceNote v0.2 normalizer intact: Warehouse rows
are read exclusively through ``WarehouseRaceNoteReader`` and the canonical
Archive builder still owns full-month and full-scan validation.  The sole Raw
exception is the documented 2010 previous-result seam (pre-2010 ZED/ZKB rows).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import build_racenote_archive_month_from_raw as common
from jrdb_raw import Parser, iter_archive_records, result_key
from jrdb_racenote_warehouse_adapter import previous_result_year
from jrdb_racenote_warehouse_reader import WarehouseRaceNoteReader, WarehouseRaceNoteReaderError

HERE = Path(__file__).resolve().parent
ARCHIVE_BUILDER = HERE / "build_racenote_archive.py"
HISTORY_FAMILIES = ("ZED", "ZKB")


class WarehouseMonthBuildError(RuntimeError):
    """A Warehouse-backed Archive month cannot be completed safely."""


def parse_asset_roots(values: list[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        family, marker, raw_path = value.partition("=")
        family = family.strip().upper()
        if marker != "=" or family not in {"BAC", "KYI", "CHA", "CYB", "ZED", "ZKB"}:
            raise WarehouseMonthBuildError("--warehouse-asset-root requires FAMILY=PATH for BAC,KYI,CHA,CYB,ZED,ZKB")
        if family in roots:
            raise WarehouseMonthBuildError(f"duplicate Warehouse asset root: {family}")
        roots[family] = Path(raw_path).expanduser()
    missing = sorted({"BAC", "KYI", "CHA", "CYB", "ZED", "ZKB"} - set(roots))
    if missing:
        raise WarehouseMonthBuildError(f"missing Warehouse asset roots: {missing}")
    return roots


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one full-month RaceNote Archive from JRDB Warehouse")
    parser.add_argument("--target-month", required=True, help="YYYYMM (2010..2025 only)")
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--warehouse-current", type=Path, required=True)
    parser.add_argument("--warehouse-asset-root", action="append", default=[], metavar="FAMILY=PATH")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--archive-output", type=Path, required=True)
    parser.add_argument("--converter-git-sha", required=True)
    parser.add_argument("--source-ref", default=None)
    parser.add_argument("--boundary-raw-dir", type=Path, default=None,
                        help="2010-only cache containing ZED_YYYY.zip/ZKB_YYYY.zip for pre-2010 result rows")
    parser.add_argument("--validation-report", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _source_manifest(reader: WarehouseRaceNoteReader, target_year: int, boundary_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build location-free, immutable input provenance for the Archive contract."""
    rows: list[dict[str, str]] = []
    for asset in reader.assets:
        family = str(asset.get("family") or "").upper()
        year = int(asset.get("year") or 0)
        if family not in {"BAC", "KYI", "CHA", "CYB", "ZED", "ZKB"}:
            continue
        # Target families are read for target year; result history may use any
        # covered year, and recording all immutable listed assets is clearer
        # than claiming an unprovable row-level subset.
        if family in {"BAC", "KYI", "CHA", "CYB"} and year != target_year:
            continue
        rows.append({
            "source_type": "JRDB_WAREHOUSE_PARQUET",
            "source_period": str(year),
            "filename": Path(str(asset["relative_path"])).name,
            "sha256": str(asset["sha256"]),
            "role": f"warehouse:{family}",
        })
    for row in boundary_rows:
        rows.append({
            "source_type": "ANNUAL_RAW_BOUNDARY",
            "source_period": str(row["year"]),
            "filename": str(row["filename"]),
            "sha256": str(row["sha256"]),
            "role": f"2010_previous_result_boundary:{row['family']}",
        })
    rows.sort(key=lambda x: (x["source_period"], x["filename"], x["role"]))
    return rows


def load_boundary_history(raw_dir: Path, keys: set[str]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Load only the pre-2010 parser rows explicitly referenced by KYI.

    There is intentionally no fetch option here: a missing boundary artifact is
    a fail-closed operational error, not permission to use the Raw target-race
    path.
    """
    years = sorted({previous_result_year(key) for key in keys if previous_result_year(key) is not None and previous_result_year(key) < 2010})
    parser = Parser()
    selected: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sources: list[dict[str, Any]] = []
    for year in years:
        for family in HISTORY_FAMILIES:
            path = raw_dir / family / f"{family}_{year}.zip"
            if not path.is_file():
                raise WarehouseMonthBuildError(f"missing explicit 2010 boundary Raw input: {path}")
            matched = 0
            for _member, record in iter_archive_records(path, family):
                if result_key(record) not in keys:
                    continue
                selected[family].append(getattr(parser, family.lower())(record))
                matched += 1
            sources.append({"year": year, "family": family, "filename": path.name, "sha256": sha256_file(path), "matched_rows": matched})
    return dict(selected), sources


def write_bundles(reader: WarehouseRaceNoteReader, index: common.MonthIndex, work_dir: Path, boundary_raw_dir: Path | None) -> tuple[Path, list[dict[str, Any]], list[dict[str, Any]], int]:
    bundle_dir = work_dir / "bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, Any]] = []
    boundary_sources: dict[tuple[int, str], dict[str, Any]] = {}
    boundary_key_count = 0
    for race_date, races in sorted(index.by_date.items()):
        day = date.fromisoformat(race_date)
        keys = [race.race_key for race in races]
        boundary_history = None
        # Query before build so a 2010 day can provide exactly the keys that
        # need the seam.  For 2011--2025 this never touches Raw.
        if day.year == 2010:
            all_boundary = set(
                reader.boundary_previous_keys(
                    2010, race_keys=keys, source_member_date=day
                )
            )
            # This is cheap relative to the build and makes the Raw seam
            # explicit even when the month contains only a subset of races.
            if all_boundary:
                if boundary_raw_dir is None:
                    raise WarehouseMonthBuildError("2010 Archive requires --boundary-raw-dir for pre-2010 previous-result references")
                boundary_history, source_rows = load_boundary_history(boundary_raw_dir, all_boundary)
                for row in source_rows:
                    boundary_sources[(int(row["year"]), str(row["family"]))] = row
                boundary_key_count = len(all_boundary)
        try:
            bundles, audit = reader.build(day, race_keys=keys, source_member_date=day, boundary_history=boundary_history)
        except WarehouseRaceNoteReaderError as exc:
            raise WarehouseMonthBuildError(str(exc)) from exc
        if set(bundles) != set(keys):
            raise WarehouseMonthBuildError(f"Warehouse bundle identity mismatch for {race_date}: expected={len(keys)} actual={len(bundles)}")
        for race_key, bundle in sorted(bundles.items()):
            _json(bundle_dir / f"race_bundle_{race_key}.json", bundle)
        reports.append({"race_date": race_date, "expected_races": len(keys), "generated_races": len(bundles), "warehouse_audit": audit})
    return bundle_dir, reports, list(boundary_sources.values()), boundary_key_count


def build(args: argparse.Namespace) -> dict[str, Any]:
    started = time.monotonic()
    target_month, start, next_month = common.parse_target_month(args.target_month)
    if not 2010 <= start.year <= 2025:
        raise WarehouseMonthBuildError("Warehouse Archive builder accepts only 2010..2025; 2026 remains the PACI/Raw daily route")
    common.validate_sqlite(args.analysis)
    roots = parse_asset_roots(args.warehouse_asset_root)
    reader = WarehouseRaceNoteReader(args.warehouse_current, asset_roots=roots)
    index = common.load_month_index(args.analysis, start, next_month)
    args.work_dir.mkdir(parents=True, exist_ok=True)
    args.archive_output.parent.mkdir(parents=True, exist_ok=True)
    bundle_dir, date_reports, boundary_sources, boundary_key_count = write_bundles(reader, index, args.work_dir, args.boundary_raw_dir)

    expected_index = args.work_dir / "expected_race_index.json"
    source_manifest = args.work_dir / "source_manifest.json"
    common.write_expected_index(expected_index, target_month, index)
    _json(source_manifest, {"sources": _source_manifest(reader, start.year, boundary_sources)})
    validation_report = args.validation_report or args.archive_output.with_name(args.archive_output.stem + "_validation.json")
    command = [
        sys.executable, str(ARCHIVE_BUILDER), "--bundle-dir", str(bundle_dir),
        "--target-month", target_month, "--output", str(args.archive_output),
        "--source-mode", "warehouse", "--coverage-mode", "full_month",
        "--expected-index", str(expected_index), "--source-manifest", str(source_manifest),
        "--source-ref", args.source_ref or f"warehouse-{reader.manifest['generation_id']}",
        "--converter-git-sha", args.converter_git_sha, "--expected-race-count", str(len(index.races)),
        "--validation-report", str(validation_report),
    ]
    subprocess.run(command, check=True)
    validation = json.loads(validation_report.read_text(encoding="utf-8"))
    if not validation.get("publishable") or validation.get("status") != "PASS":
        raise WarehouseMonthBuildError("canonical Archive validation did not produce a publishable PASS shard")
    # The child builder validates before returning.  Re-open the immutable
    # output here as well: the Warehouse route must never report a semantic
    # success if its final SQLite has been replaced, truncated, or lost while
    # unwinding the parent process.
    try:
        with sqlite3.connect(args.archive_output) as archive_connection:
            actual_rows = int(archive_connection.execute("SELECT COUNT(*) FROM race_bundle").fetchone()[0])
            source_rows = int(archive_connection.execute("SELECT COUNT(*) FROM source_input").fetchone()[0])
            integrity = archive_connection.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.Error as exc:
        raise WarehouseMonthBuildError(f"final Warehouse Archive readback failed: {exc}") from exc
    if integrity != "ok" or actual_rows != len(index.races) or source_rows <= 0:
        raise WarehouseMonthBuildError(
            "final Warehouse Archive readback mismatch: "
            f"integrity={integrity!r} rows={actual_rows}/{len(index.races)} source_inputs={source_rows}"
        )
    summary = {
        "status": "PASS", "input_backend": "jrdb_warehouse", "target_month": target_month,
        "warehouse_generation_id": reader.manifest["generation_id"], "expected_race_count": len(index.races),
        "generated_bundle_count": validation.get("selected_bundle_count"), "archive_file": args.archive_output.name,
        "archive_bytes": args.archive_output.stat().st_size, "coverage_mode": validation.get("coverage_mode"),
        "publication_status": validation.get("publication_status"), "publishable": validation.get("publishable"),
        "identity_match": validation.get("identity_match"), "verified_bundle_count": validation.get("verified_bundle_count"),
        "expected_index_sha256": validation.get("expected_index_sha256"), "source_input_count": validation.get("source_input_count"),
        "provenance_status": validation.get("provenance_status"), "boundary_previous_result_key_count": boundary_key_count,
        "boundary_raw_source_count": len(boundary_sources), "date_reports": date_reports,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    summary_path = args.summary or args.work_dir / "month_build_summary.json"
    _json(summary_path, summary)
    summary["summary_path"] = str(summary_path)
    return summary


def main() -> int:
    try:
        result = build(parse_args())
    except (WarehouseMonthBuildError, WarehouseRaceNoteReaderError, sqlite3.Error, OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
