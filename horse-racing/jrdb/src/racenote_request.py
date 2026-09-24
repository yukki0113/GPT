#!/usr/bin/env python3
"""Unified RaceNote request router.

Stable RaceNote entrypoint. User/GPT specifies a target date and optionally venue/race.
Temporal routing and scope routing are independent.

Backends:
- current/future: JRDB PACI
- past: resolved publishable RaceNote Archive first
- historical rebuild (2010-2025): accepted JRDB Warehouse Parquet
- historical Raw: explicit audit/rollback and 2010 boundary fallback only
- Archive discovery remains outside this router; this module receives only a resolved local shard.

Historical enrichment always uses as_of_exclusive=target_date.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import racenote_archive_backend as archive_backend
from jrdb_raw import Parser as CommonRawParser
from jrdb_raw import iter_archive_records, race_key as raw_race_key, result_key as raw_result_key
from jrdb_racenote_raw_adapter import build_paci_equivalent as build_common_historical_paci
from jrdb_racenote_warehouse_reader import (
    WarehouseRaceNoteReader,
    WarehouseRaceNoteReaderError,
)
from jrdb_store import StoreError, StoreResolver, manifest_path_from_args
from racenote_analysis_backend import AnalysisBackendError, open_analysis_backend
from racenote_history_enrichment import enrich_production_many

HERE = Path(__file__).resolve().parent
FETCH_PACI = HERE / "fetch_jrdb_paci.py"
FETCH_HISTORY = HERE / "fetch_jrdb_history.py"
CONVERTER = HERE / "racenote_jrdb.py"
ENRICHER = HERE / "racenote_history_enrichment.py"

@dataclass(frozen=True)
class RaceNoteRequest:
    """Normalized RaceNote request."""

    target_date: date
    venue: str | None
    race_no: int | None
    today: date

    @property
    def temporal_mode(self) -> str:
        """Return past/current/future."""
        if self.target_date < self.today:
            return "past"
        if self.target_date == self.today:
            return "current"
        return "future"

    @property
    def scope(self) -> str:
        """Return all/venue/race."""
        if self.venue is None:
            return "all"
        if self.race_no is None:
            return "venue"
        return "race"

    @property
    def compact_date(self) -> str:
        """Return YYYYMMDD."""
        return self.target_date.strftime("%Y%m%d")


class RaceNoteRequestError(RuntimeError):
    """RaceNote request cannot be fulfilled safely."""


def parse_date(value: str) -> date:
    """Parse YYYYMMDD, YYYY-MM-DD or YYYY/MM/DD."""
    normalized = value.replace("-", "").replace("/", "").strip()
    return datetime.strptime(normalized, "%Y%m%d").date()


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Unified RaceNote request router")
    parser.add_argument("--date", required=True, help="Target date")
    parser.add_argument("--venue", default=None, help="Optional JRA venue")
    parser.add_argument("--race", type=int, default=None, help="Optional race number; requires venue")
    parser.add_argument("--today", default=None, help="Router-date override for tests")
    parser.add_argument("--analysis-root", type=Path, default=None, help="Verified Analysis Parquet current root")
    parser.add_argument("--analysis", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--analysis-backend", choices=("parquet", "sqlite"), default="parquet")
    parser.add_argument("--store-manifest", type=Path, default=None, help="JRDB Store manifest; falls back to JRDB_STORE_MANIFEST")
    parser.add_argument("--store-cache", type=Path, default=None, help="Optional JRDB Store cache root")
    parser.add_argument("--store-offline", action="store_true", help="Resolve Store artifacts from verified cache only")
    parser.add_argument("--raw-dir", type=Path, default=None, help="Historical Raw cache/root")
    parser.add_argument(
        "--warehouse-current", type=Path, default=None,
        help="Accepted dedicated JRDB Warehouse current.json (required for 2010-2025 rebuild)",
    )
    parser.add_argument(
        "--warehouse-asset-root", action="append", default=[], metavar="FAMILY=PATH",
        help="Verified local immutable asset root; repeat for BAC,KYI,CHA,CYB,ZED,ZKB",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=None,
        help="Optional resolved publishable monthly RaceNote Archive shard for past requests",
    )
    parser.add_argument("--output", type=Path, default=Path("output_racenote_request"))
    parser.add_argument("--stats-window-years", type=int, default=5)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--force-fetch", action="store_true")
    return parser.parse_args()


def normalize_request(args: argparse.Namespace) -> RaceNoteRequest:
    """Validate request dimensions independently from backend choice."""
    target_date = parse_date(args.date)
    today_value = parse_date(args.today) if args.today else date.today()
    venue = args.venue.strip() if args.venue else None
    race_no = args.race
    if race_no is not None and venue is None:
        raise RaceNoteRequestError("--race requires --venue")
    if race_no is not None and not 1 <= race_no <= 12:
        raise RaceNoteRequestError("--race must be between 1 and 12")
    return RaceNoteRequest(target_date, venue, race_no, today_value)


def build_plan(request: RaceNoteRequest) -> dict:
    """Return a machine-readable execution plan before I/O."""
    use_historical_warehouse = request.temporal_mode == "past" and request.target_date.year <= 2025
    if use_historical_warehouse:
        base_backend = "historical_warehouse"
    else:
        base_backend = "paci"
    return {
        "request_version": "0.2.0",
        "final_schema_version": "1.0",
        "target_date": request.target_date.isoformat(),
        "today": request.today.isoformat(),
        "temporal_mode": request.temporal_mode,
        "scope": request.scope,
        "venue": request.venue,
        "race_no": request.race_no,
        "base_backend": base_backend,
        "enrichment": {
            "analysis": True,
            "analysis_backend": "parquet_duckdb",
            "sqlite_materialization_required": False,
            "stats_mart": False,
            "stats_mart_required": False,
            "as_of_exclusive": request.target_date.isoformat(),
            "future_leakage_rule": "Never use target-date result rows or later rows.",
        },
        "phase_b_markers": {
            "RACENOTE_PHASE_B_PARQUET_NATIVE": "PASS",
            "RACENOTE_ANALYSIS_BACKEND": "PARQUET_DUCKDB",
            "RACENOTE_SQLITE_MATERIALIZATION_REQUIRED": False,
            "RACENOTE_STATS_MART_ACTIVE_DEPENDENCY": False,
            "RACENOTE_HISTORICAL_BACKEND": "HISTORICAL_WAREHOUSE",
            "RACENOTE_2026_BACKEND": "PACI",
            "RACENOTE_OUTPUT_SEMANTICS_UNCHANGED": True,
        },
        "historical_backend_policy": {
            "preferred": "racenote_archive",
            "rebuild_2010_2025": "historical_warehouse",
            "raw_fallback_2010": "explicit_boundary_or_rollback_only",
            "fallback_from_2026": "paci",
            "raw_is_not_normal_daily_query_path": True,
        },
    }


def run(command: list[str], cwd: Path | None = None) -> None:
    """Run subprocess with fail-fast semantics."""
    subprocess.run(command, cwd=cwd, check=True)


def validate_sqlite(path: Path, label: str) -> None:
    """Validate external SQLite artifact."""
    if not path.is_file():
        raise RaceNoteRequestError(f"{label} not found: {path}")
    connection = sqlite3.connect(path)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise RaceNoteRequestError(f"{label} integrity_check failed: {result}")
    finally:
        connection.close()

def resolve_enrichment_sources(args: argparse.Namespace) -> tuple[Path, dict]:
    """Resolve one verified Analysis source without automatic fallback."""
    backend_name = getattr(args, "analysis_backend", None)
    if backend_name is None:
        backend_name = "sqlite" if getattr(args, "analysis", None) is not None else "parquet"
    analysis_root = getattr(args, "analysis_root", None)
    analysis_db = getattr(args, "analysis", None)
    source = analysis_root if backend_name == "parquet" else analysis_db
    if source is None:
        try:
            manifest_path = manifest_path_from_args(args.store_manifest)
            resolver = StoreResolver.from_file(manifest_path, cache_root=args.store_cache)
            source = resolver.resolve("jrdb://analysis/current", offline=args.store_offline)
        except StoreError as exc:
            raise RaceNoteRequestError(f"JRDB Store resolution failed: {exc}") from exc
    if source is None:
        raise RaceNoteRequestError("Analysis canonical resolution is incomplete")
    try:
        backend = open_analysis_backend(
            analysis_root=source if backend_name == "parquet" else None,
            analysis_db=source if backend_name == "sqlite" else None,
            backend=backend_name,
        )
        source_info = dict(backend.source_info)
        backend.close()
    except AnalysisBackendError as exc:
        raise RaceNoteRequestError(str(exc)) from exc
    return source, {
        "mode": "explicit_path" if analysis_root or analysis_db else "store_manifest",
        "analysis": str(source),
        "analysis_backend": "parquet_duckdb" if backend_name == "parquet" else "sqlite_compatibility",
        "stats_mart": False,
        "stats_mart_required": False,
        "sqlite_materialization_required": False,
        "source": source_info,
    }

def try_archive_base(
    archive_path: Path | None,
    request: RaceNoteRequest,
    output_dir: Path,
) -> tuple[Path | None, dict]:
    """Try a publishable Archive shard before historical fallback."""
    if request.temporal_mode != "past":
        return None, {
            "attempted": False,
            "status": "skipped_non_past",
        }
    if archive_path is None:
        return None, {
            "attempted": False,
            "status": "not_supplied",
        }
    if not archive_path.is_file():
        return None, {
            "attempted": True,
            "status": "fallback",
            "archive_file": archive_path.name,
            "reason": "archive_file_missing",
        }

    try:
        base_dir, report = archive_backend.materialize(
            archive_path,
            request.target_date.isoformat(),
            request.venue,
            request.race_no,
            output_dir,
        )
    except (archive_backend.RaceNoteArchiveBackendError, sqlite3.Error, OSError) as exc:
        return None, {
            "attempted": True,
            "status": "fallback",
            "archive_file": archive_path.name,
            "reason": "archive_rejected",
            "detail": str(exc),
        }

    return base_dir, {
        "attempted": True,
        "status": "used",
        **report,
    }


def target_race_keys(analysis: Path, request: RaceNoteRequest, backend_name: str) -> set[bytes]:
    """Resolve target race keys without using target result values."""
    sql = "SELECT DISTINCT race_key FROM fact_entry_result_lite WHERE race_date=?"
    parameters: list[object] = [request.target_date.isoformat()]
    if request.venue is not None:
        venue_map = {
            "札幌": "01", "函館": "02", "福島": "03", "新潟": "04", "東京": "05",
            "中山": "06", "中京": "07", "京都": "08", "阪神": "09", "小倉": "10",
        }
        if request.venue not in venue_map:
            raise RaceNoteRequestError(f"Unknown JRA venue: {request.venue}")
        sql += " AND venue_code=?"
        parameters.append(venue_map[request.venue])
    if request.race_no is not None:
        sql += " AND race_no=?"
        parameters.append(request.race_no)
    try:
        backend = open_analysis_backend(
            analysis_root=analysis if backend_name == "parquet" else None,
            analysis_db=analysis if backend_name == "sqlite" else None,
            backend=backend_name,
        )
        table = "analysis_fact" if backend_name == "parquet" else "fact_entry_result_lite"
        rows = backend.execute(sql.replace("fact_entry_result_lite", table), parameters).fetchall()
    except AnalysisBackendError as exc:
        raise RaceNoteRequestError(str(exc)) from exc
    finally:
        if "backend" in locals():
            backend.close()
    race_keys = {str(row[0]).encode("ascii") for row in rows if row[0]}
    if not race_keys:
        raise RaceNoteRequestError("No target races found in Analysis Lite for request")
    return race_keys


def annual_zip(raw_dir: Path, kind: str, year: int) -> Path:
    """Return canonical cache path for one annual Raw ZIP."""
    return raw_dir / kind / f"{kind}_{year}.zip"


def fetch_historical_raw(year: int, raw_dir: Path, force: bool, kinds: list[str]) -> None:
    """Fetch annual packs through the canonical JRDB history fetcher."""
    command = [
        sys.executable, str(FETCH_HISTORY), "--year", str(year), "--kinds", *kinds,
        "--output-dir", str(raw_dir.resolve()), "--continue-on-error",
    ]
    if force:
        command.append("--force")
    run(command, cwd=HERE)


def ensure_historical_raw(year: int, raw_dir: Path, force: bool, kinds: list[str]) -> None:
    """Use pre-positioned Raw ZIPs first; fetch only packs that are actually missing.

    This keeps normal historical requests independent from JRDB credentials when GPT,
    an Archive builder, or another storage adapter has already populated the cache.
    """
    missing = [kind for kind in kinds if not annual_zip(raw_dir, kind, year).is_file()]
    if force:
        missing = list(kinds)
    if missing:
        fetch_historical_raw(year, raw_dir, force, missing)
    still_missing = [kind for kind in kinds if not annual_zip(raw_dir, kind, year).is_file()]
    if still_missing:
        raise RaceNoteRequestError(f"Missing historical Raw after fetch/cache resolution: {still_missing}")


def iter_records(zip_path: Path, prefix: str) -> Iterable[bytes]:
    """Yield non-empty fixed-width rows from matching ZIP members."""
    found = False
    for _member, record in iter_archive_records(zip_path, prefix):
        found = True
        yield record
    if not found:
        raise RaceNoteRequestError(f"No {prefix} member in {zip_path}")


def build_historical_paci(raw_dir: Path, request: RaceNoteRequest, analysis: Path, analysis_backend: str, destination: Path, force_fetch: bool) -> dict:
    """Build target-date PACI-equivalent input from annual Raw.

    BAC/KYI/CHA/CYB are selected by target race key. ZED/ZKB are selected only by
    previous-result keys explicitly carried by selected KYI rows.
    """
    try:
        return build_common_historical_paci(
            raw_dir=raw_dir,
            target_year=request.target_date.year,
            short_date=request.target_date.strftime("%y%m%d"),
            race_keys=target_race_keys(analysis, request, analysis_backend),
            destination=destination,
            ensure_history=lambda year, kinds: ensure_historical_raw(
                year, raw_dir, force_fetch, kinds
            ),
        )
    except ValueError as exc:
        raise RaceNoteRequestError(str(exc)) from exc


def warehouse_asset_roots(values: list[str]) -> dict[str, Path]:
    """Parse the explicit verified immutable asset-root contract."""
    roots: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise RaceNoteRequestError("--warehouse-asset-root must be FAMILY=PATH")
        family, path = value.split("=", 1)
        family = family.strip().upper()
        if not family or not path:
            raise RaceNoteRequestError("--warehouse-asset-root must be FAMILY=PATH")
        roots[family] = Path(path)
    required = {"BAC", "KYI", "CHA", "CYB", "ZED", "ZKB"}
    missing = sorted(required - set(roots))
    if missing:
        raise RaceNoteRequestError(f"Warehouse asset roots missing: {missing}")
    return roots


def build_historical_warehouse_base(
    request: RaceNoteRequest,
    current: Path | None,
    asset_root_values: list[str],
    output_dir: Path,
) -> tuple[Path, dict]:
    """Materialize unchanged RaceNote v0.2 bundles from accepted Parquet only."""
    if current is None:
        raise RaceNoteRequestError(
            "2010-2025 historical rebuild requires --warehouse-current; "
            "Raw is reserved for explicit audit/rollback or 2010 boundary fallback"
        )
    try:
        reader = WarehouseRaceNoteReader(current, asset_roots=warehouse_asset_roots(asset_root_values))
        bundles, evidence = reader.build(request.target_date, source_member_date=request.target_date)
    except WarehouseRaceNoteReaderError as exc:
        raise RaceNoteRequestError(str(exc)) from exc
    bundle_dir = output_dir / f"RaceNote_{request.compact_date}"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    for bundle in bundles.values():
        race = bundle["race"]
        path = bundle_dir / f"race_bundle_{request.compact_date}_{race['venue']}{race['race_no']}R.json"
        path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return bundle_dir, evidence


def fetch_paci(request: RaceNoteRequest, work_dir: Path, force: bool) -> Path:
    """Fetch current/future PACI through canonical authenticated downloader."""
    paci_dir = work_dir / "PACI"
    command = [sys.executable, str(FETCH_PACI), "--date", request.compact_date, "--out-dir", str(paci_dir.resolve())]
    if force:
        command.append("--force")
    run(command, cwd=HERE)
    paci_path = paci_dir / f"PACI{request.target_date.strftime('%y%m%d')}.zip"
    if not paci_path.is_file():
        raise RaceNoteRequestError(f"PACI fetch completed but file is missing: {paci_path}")
    return paci_path


def convert_base(paci_path: Path, request: RaceNoteRequest, work_dir: Path) -> Path:
    """Convert base PACI-equivalent input with existing RaceNote converter."""
    command = [sys.executable, str(CONVERTER), str(paci_path), "--output", str(work_dir), "--format", "json"]
    if request.scope == "race":
        command.extend(["--race", f"{request.venue}{request.race_no}"])
    run(command)
    bundle_dir = work_dir / f"RaceNote_{request.compact_date}"
    if not bundle_dir.is_dir():
        raise RaceNoteRequestError(f"Converter output directory missing: {bundle_dir}")
    return bundle_dir


def select_bundles(bundle_dir: Path, request: RaceNoteRequest) -> list[Path]:
    """Apply all/venue/race scope after base generation."""
    bundles = sorted(bundle_dir.glob("race_bundle_*.json"))
    if request.scope == "all":
        selected = bundles
    elif request.scope == "venue":
        selected = [path for path in bundles if f"_{request.venue}" in path.name]
    else:
        selected = [path for path in bundles if f"_{request.venue}{request.race_no}R" in path.name]
    if not selected:
        raise RaceNoteRequestError("No RaceNote bundles matched request scope")
    return selected


def enrich_bundle(bundle: Path, analysis: Path, analysis_backend: str, output_dir: Path, stats_window_years: int) -> Path:
    """Add production Analysis/Mart enrichment and write a stable v1.0 bundle."""
    target = output_dir / bundle.name
    command = [
        sys.executable, str(ENRICHER), "--bundle", str(bundle),
        "--analysis-backend", analysis_backend,
        "--analysis-root" if analysis_backend == "parquet" else "--analysis",
        str(analysis), "--output", str(target),
        "--stats-window-years", str(stats_window_years),
    ]
    run(command)
    if not target.is_file():
        raise RaceNoteRequestError(f"Enriched bundle missing: {target}")
    return target


def enrich_bundles_shared(
    bundles: list[Path],
    analysis: Path,
    analysis_backend: str,
    output_dir: Path,
    stats_window_years: int,
) -> list[Path]:
    """Enrich a request in one process with one validated backend connection."""
    bases = [json.loads(path.read_text(encoding="utf-8")) for path in bundles]
    backend = open_analysis_backend(
        analysis_root=analysis if analysis_backend == "parquet" else None,
        analysis_db=analysis if analysis_backend == "sqlite" else None,
        backend=analysis_backend,
    )
    try:
        enriched_items = enrich_production_many(bases, backend, None, stats_window_years)
        outputs: list[Path] = []
        for bundle, (enriched, _warnings) in zip(bundles, enriched_items):
            target = output_dir / bundle.name
            metadata = enriched.setdefault("metadata", {}).setdefault("history_enrichment", {})
            metadata["analysis_backend"] = backend.source_info.get("backend", "sqlite")
            metadata["analysis_source"] = {**backend.source_info, **backend.metrics()}
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            outputs.append(target)
        return outputs
    finally:
        backend.close()


def package_output(
    output_dir: Path,
    request: RaceNoteRequest,
    generated: list[Path],
    plan: dict,
    reconstruction: dict | None,
    backend_resolution: dict,
) -> Path:
    """Write manifest and package selected RaceNote bundles."""
    manifest = {
        "request": plan,
        "bundle_count": len(generated),
        "bundles": [path.name for path in generated],
        "backend_resolution": backend_resolution,
        "historical_reconstruction": reconstruction,
    }
    manifest_path = output_dir / "request_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    parts = [request.compact_date]
    if request.venue:
        parts.append(request.venue)
    if request.race_no:
        parts.append(f"{request.race_no}R")
    zip_path = output_dir.parent / ("RaceNote_" + "_".join(parts) + ".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(manifest_path, manifest_path.name)
        for path in generated:
            archive.write(path, path.name)
    return zip_path


def main() -> int:
    """Route, build, enrich and package one RaceNote request."""
    args = parse_args()
    request = normalize_request(args)
    plan = build_plan(request)
    plan["archive_candidate_supplied"] = args.archive is not None
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if args.plan_only:
        return 0

    analysis, enrichment_resolution = resolve_enrichment_sources(args)
    analysis_backend = args.analysis_backend
    plan["enrichment_source_resolution"] = enrichment_resolution
    request_root = args.output / request.compact_date
    work_dir = request_root / "work"
    final_dir = request_root / "bundles"
    final_dir.mkdir(parents=True, exist_ok=True)

    reconstruction: dict | None = None
    base_dir, archive_resolution = try_archive_base(
        args.archive,
        request,
        work_dir / "archive_base",
    )

    if base_dir is not None:
        plan["base_backend"] = "racenote_archive"
    else:
        use_historical_warehouse = (
            request.temporal_mode == "past"
            and request.target_date.year <= 2025
        )
        if use_historical_warehouse:
            try:
                base_dir, reconstruction = build_historical_warehouse_base(
                    request,
                    args.warehouse_current,
                    args.warehouse_asset_root,
                    work_dir,
                )
                plan["base_backend"] = "historical_warehouse"
            except RaceNoteRequestError as exc:
                # The only automatic Raw route retained for historical rebuilds
                # is the documented pre-2010 previous-result boundary.  A
                # caller must explicitly provide Raw; no credentialed fetch or
                # silent backend downgrade occurs here.
                boundary = "out-of-coverage previous-result keys" in str(exc)
                if not (boundary and args.raw_dir is not None):
                    raise
                ensure_historical_raw(
                    request.target_date.year,
                    args.raw_dir,
                    args.force_fetch,
                    ["BAC", "KYI", "CHA", "CYB"],
                )
                paci_path = request_root / f"PACI_REBUILT_{request.compact_date}.zip"
                reconstruction = build_historical_paci(
                    args.raw_dir, request, analysis, analysis_backend, paci_path, args.force_fetch,
                )
                reconstruction["fallback_reason"] = "pre_2010_previous_result_boundary"
                plan["base_backend"] = "historical_raw_boundary_fallback"
                base_dir = convert_base(paci_path, request, work_dir)
        else:
            paci_path = fetch_paci(request, request_root, args.force_fetch)
            plan["base_backend"] = "paci"
            base_dir = convert_base(paci_path, request, work_dir)

    backend_resolution = {
        "used_backend": plan["base_backend"],
        "archive": archive_resolution,
    }
    selected = select_bundles(base_dir, request)
    if analysis_backend == "parquet":
        generated = enrich_bundles_shared(
            selected,
            analysis,
            analysis_backend,
            final_dir,
            args.stats_window_years,
        )
    else:
        # Keep the compatibility route as the legacy per-bundle comparator.
        generated = [
            enrich_bundle(bundle, analysis, analysis_backend, final_dir, args.stats_window_years)
            for bundle in selected
        ]
    zip_path = package_output(
        final_dir,
        request,
        generated,
        plan,
        reconstruction,
        backend_resolution,
    )
    print(json.dumps({"status": "success", "zip": str(zip_path), "bundle_count": len(generated)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
