#!/usr/bin/env python3
"""Unified RaceNote request router.

Stable RaceNote entrypoint. User/GPT specifies a target date and optionally venue/race.
Temporal routing and scope routing are independent.

Backends:
- current/future: JRDB PACI
- past: pre-positioned historical Raw cache first, JRDB annual fetch only for missing packs
- future design: RaceNote Archive can replace the past base backend without changing
  this request contract.

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

HERE = Path(__file__).resolve().parent
FETCH_PACI = HERE / "fetch_jrdb_paci.py"
FETCH_HISTORY = HERE / "fetch_jrdb_history.py"
CONVERTER = HERE / "racenote_jrdb.py"
ENRICHER = HERE / "racenote_history_enrichment.py"

PREV_RESULT_SLICES = (
    (203, 219),
    (219, 235),
    (235, 251),
    (251, 267),
    (267, 283),
)


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
    parser.add_argument("--analysis", type=Path, required=True, help="Analysis Lite SQLite")
    parser.add_argument("--mart", type=Path, required=True, help="Stats Mart SQLite")
    parser.add_argument("--raw-dir", type=Path, default=None, help="Historical Raw cache/root")
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
    use_annual_raw = request.temporal_mode == "past" and request.target_date.year <= 2025
    if use_annual_raw:
        base_backend = "historical_raw_cache_or_fetch"
    else:
        base_backend = "paci"
    return {
        "request_version": "0.1.1",
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
            "stats_mart": True,
            "as_of_exclusive": request.target_date.isoformat(),
            "future_leakage_rule": "Never use target-date result rows or later rows.",
        },
        "historical_backend_policy": {
            "preferred_future": "racenote_archive",
            "current": "prepositioned annual Raw cache; fetch only missing packs",
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


def target_race_keys(analysis: Path, request: RaceNoteRequest) -> set[bytes]:
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
    connection = sqlite3.connect(analysis)
    try:
        rows = connection.execute(sql, parameters).fetchall()
    finally:
        connection.close()
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
    with zipfile.ZipFile(zip_path) as archive:
        members = [name for name in archive.namelist() if Path(name).name.upper().startswith(prefix)]
        if not members:
            raise RaceNoteRequestError(f"No {prefix} member in {zip_path}")
        for member in members:
            for line in archive.read(member).splitlines():
                if line:
                    yield line


def build_historical_paci(raw_dir: Path, request: RaceNoteRequest, analysis: Path, destination: Path, force_fetch: bool) -> dict:
    """Build target-date PACI-equivalent input from annual Raw.

    BAC/KYI/CHA/CYB are selected by target race key. SED/SKB are selected only by
    previous-result keys explicitly carried by selected KYI rows.
    """
    year = request.target_date.year
    race_keys = target_race_keys(analysis, request)
    selected: dict[str, list[bytes]] = {"BAC": [], "KYI": [], "CHA": [], "CYB": []}
    for kind in selected:
        for line in iter_records(annual_zip(raw_dir, kind, year), kind):
            if line[:8] in race_keys:
                selected[kind].append(line)
    if not selected["BAC"] or not selected["KYI"]:
        raise RaceNoteRequestError("Historical reconstruction found no BAC/KYI records")

    previous_result_keys: set[bytes] = set()
    for line in selected["KYI"]:
        for start, end in PREV_RESULT_SLICES:
            key = line[start:end].strip()
            if key and key != b"0" * 16:
                previous_result_keys.add(key)

    previous_years: set[int] = set()
    for key in previous_result_keys:
        try:
            previous_years.add(int(key[-8:-4].decode("ascii")))
        except (UnicodeDecodeError, ValueError):
            continue
    if previous_result_keys and not previous_years:
        raise RaceNoteRequestError("Could not resolve previous-result years from KYI keys")

    for previous_year in sorted(previous_years):
        ensure_historical_raw(previous_year, raw_dir, force_fetch, ["SED", "SKB"])

    zed: list[bytes] = []
    zkb: list[bytes] = []
    for previous_year in sorted(previous_years):
        for line in iter_records(annual_zip(raw_dir, "SED", previous_year), "SED"):
            if line[10:26].strip() in previous_result_keys:
                zed.append(line)
        for line in iter_records(annual_zip(raw_dir, "SKB", previous_year), "SKB"):
            if line[10:26].strip() in previous_result_keys:
                zkb.append(line)

    destination.parent.mkdir(parents=True, exist_ok=True)
    short_date = request.target_date.strftime("%y%m%d")
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for kind in ("BAC", "KYI", "CHA", "CYB"):
            archive.writestr(f"{kind}{short_date}.txt", b"\r\n".join(selected[kind]) + b"\r\n")
        archive.writestr(f"ZED{short_date}.txt", b"\r\n".join(zed) + (b"\r\n" if zed else b""))
        archive.writestr(f"ZKB{short_date}.txt", b"\r\n".join(zkb) + (b"\r\n" if zkb else b""))

    return {
        "race_key_count": len(race_keys),
        "record_counts": {**{kind: len(rows) for kind, rows in selected.items()}, "ZED": len(zed), "ZKB": len(zkb)},
        "previous_result_key_count": len(previous_result_keys),
        "previous_result_years": sorted(previous_years),
    }


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


def enrich_bundle(bundle: Path, analysis: Path, mart: Path, output_dir: Path, stats_window_years: int) -> Path:
    """Add production Analysis/Mart enrichment and write a stable v1.0 bundle."""
    target = output_dir / bundle.name
    command = [
        sys.executable, str(ENRICHER), "--bundle", str(bundle), "--analysis", str(analysis),
        "--mart", str(mart), "--output", str(target), "--stats-window-years", str(stats_window_years),
    ]
    run(command)
    if not target.is_file():
        raise RaceNoteRequestError(f"Enriched bundle missing: {target}")
    return target


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

    validate_sqlite(args.analysis, "Analysis Lite")
    validate_sqlite(args.mart, "Stats Mart")
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
        use_annual_raw = (
            request.temporal_mode == "past"
            and request.target_date.year <= 2025
        )
        if use_annual_raw:
            raw_dir = args.raw_dir if args.raw_dir is not None else request_root / "raw_cache"
            ensure_historical_raw(
                request.target_date.year,
                raw_dir,
                args.force_fetch,
                ["BAC", "KYI", "CHA", "CYB"],
            )
            paci_path = request_root / f"PACI_REBUILT_{request.compact_date}.zip"
            reconstruction = build_historical_paci(
                raw_dir,
                request,
                args.analysis,
                paci_path,
                args.force_fetch,
            )
            plan["base_backend"] = "historical_raw_cache_or_fetch"
        else:
            paci_path = fetch_paci(request, request_root, args.force_fetch)
            plan["base_backend"] = "paci"
        base_dir = convert_base(paci_path, request, work_dir)

    backend_resolution = {
        "used_backend": plan["base_backend"],
        "archive": archive_resolution,
    }
    selected = select_bundles(base_dir, request)
    generated = [
        enrich_bundle(
            bundle,
            args.analysis,
            args.mart,
            final_dir,
            args.stats_window_years,
        )
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
