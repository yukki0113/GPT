#!/usr/bin/env python3
"""Unified RaceNote request router.

A stable front door for RaceNote generation. The request model is independent from
how target-date data is sourced:

- current/future dates: JRDB PACI
- past dates: historical annual Raw fallback for now; a future RaceNote Archive
  backend can replace this without changing the request contract.

Analysis Lite and Stats Mart are always treated as as-of sources. Queries must not
read rows on or after the target race date when reproducing a historical race.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
FETCH_PACI = HERE / "fetch_jrdb_paci.py"
FETCH_HISTORY = HERE / "fetch_jrdb_history.py"
CONVERTER = HERE / "racenote_jrdb.py"
ENRICHER = HERE / "racenote_history_enrichment_poc.py"

PREV_RESULT_SLICES = (
    (203, 219),
    (219, 235),
    (235, 251),
    (251, 267),
    (267, 283),
)


@dataclass(frozen=True)
class RaceNoteRequest:
    """Normalized request understood by the router."""

    target_date: date
    venue: str | None
    race_no: int | None
    today: date

    @property
    def temporal_mode(self) -> str:
        """Return past/current/future without mixing it with source selection."""
        if self.target_date < self.today:
            return "past"
        if self.target_date == self.today:
            return "current"
        return "future"

    @property
    def scope(self) -> str:
        """Return all/venue/race selection scope."""
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
    """Raised when a request cannot be safely fulfilled."""


def parse_date(value: str) -> date:
    """Parse YYYYMMDD, YYYY-MM-DD or YYYY/MM/DD."""
    normalized = value.replace("-", "").replace("/", "").strip()
    return datetime.strptime(normalized, "%Y%m%d").date()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Unified RaceNote request router")
    parser.add_argument("--date", required=True, help="Target date: YYYYMMDD / YYYY-MM-DD")
    parser.add_argument("--venue", default=None, help="Optional JRA venue name, e.g. 新潟")
    parser.add_argument("--race", type=int, default=None, help="Optional race number 1-12; requires --venue")
    parser.add_argument("--today", default=None, help="Test override for router current date")
    parser.add_argument("--analysis", type=Path, required=True, help="Analysis Lite SQLite")
    parser.add_argument("--mart", type=Path, required=True, help="Stats Mart SQLite")
    parser.add_argument("--raw-dir", type=Path, default=None, help="Historical Raw cache/root; fetched when needed")
    parser.add_argument("--output", type=Path, default=Path("output_racenote_request"))
    parser.add_argument("--stats-window-years", type=int, default=5)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--force-fetch", action="store_true")
    return parser.parse_args()


def normalize_request(args: argparse.Namespace) -> RaceNoteRequest:
    """Validate and normalize user selection independently from data backends."""
    target_date = parse_date(args.date)
    today_value = parse_date(args.today) if args.today else date.today()
    venue = args.venue.strip() if args.venue else None
    race_no = args.race

    if race_no is not None and venue is None:
        raise RaceNoteRequestError("--race requires --venue")
    if race_no is not None and not 1 <= race_no <= 12:
        raise RaceNoteRequestError("--race must be between 1 and 12")

    return RaceNoteRequest(
        target_date=target_date,
        venue=venue,
        race_no=race_no,
        today=today_value,
    )


def build_plan(request: RaceNoteRequest) -> dict:
    """Build a machine-readable plan before any I/O occurs."""
    if request.temporal_mode == "past":
        base_backend = "historical_raw_fallback"
    else:
        base_backend = "paci"

    return {
        "request_version": "0.1",
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
            "current_fallback": "annual_raw_reconstruction",
            "raw_is_not_normal_daily_query_path": True,
        },
    }


def run(command: list[str], cwd: Path | None = None) -> None:
    """Run a subprocess and fail fast with the exact command owner isolated."""
    subprocess.run(command, cwd=cwd, check=True)


def validate_sqlite(path: Path, label: str) -> None:
    """Confirm that the supplied external database is a healthy SQLite file."""
    if not path.is_file():
        raise RaceNoteRequestError(f"{label} not found: {path}")
    connection = sqlite3.connect(path)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise RaceNoteRequestError(f"{label} integrity_check failed: {result}")
    finally:
        connection.close()


def target_race_keys(analysis: Path, request: RaceNoteRequest) -> set[bytes]:
    """Resolve race keys from Analysis without reading target-race result values."""
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


def fetch_historical_raw(year: int, raw_dir: Path, force: bool, kinds: list[str]) -> None:
    """Fetch requested annual Raw kinds through the canonical history fetcher."""
    command = [
        sys.executable,
        str(FETCH_HISTORY),
        "--year",
        str(year),
        "--kinds",
        *kinds,
        "--output-dir",
        str(raw_dir),
        "--continue-on-error",
    ]
    if force:
        command.append("--force")
    run(command, cwd=HERE)


def iter_records(zip_path: Path, prefix: str) -> Iterable[bytes]:
    """Yield non-empty fixed-width records from all matching members in one annual ZIP."""
    with zipfile.ZipFile(zip_path) as archive:
        members = [name for name in archive.namelist() if Path(name).name.upper().startswith(prefix)]
        if not members:
            raise RaceNoteRequestError(f"No {prefix} member in {zip_path}")
        for member in members:
            data = archive.read(member)
            for line in data.splitlines():
                if line:
                    yield line


def annual_zip(raw_dir: Path, kind: str, year: int) -> Path:
    """Return expected path produced by fetch_jrdb_history.py."""
    path = raw_dir / kind / f"{kind}_{year}.zip"
    if not path.is_file():
        raise RaceNoteRequestError(f"Missing historical Raw ZIP: {path}")
    return path


def build_historical_paci(raw_dir: Path, request: RaceNoteRequest, analysis: Path, destination: Path, force_fetch: bool) -> dict:
    """Reconstruct one target-date PACI-equivalent ZIP from annual Raw.

    Target entries come from BAC/KYI/CHA/CYB race keys. Historical ZED/ZKB rows are
    restricted to result keys explicitly referenced by the selected KYI records.
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

    # Previous runs can cross a year boundary. The result key ends with YYYYMMDD,
    # so fetch only the SED/SKB annual packs actually referenced by target KYI.
    previous_years: set[int] = set()
    for key in previous_result_keys:
        try:
            previous_years.add(int(key[-8:-4].decode("ascii")))
        except (UnicodeDecodeError, ValueError):
            continue
    if not previous_years and previous_result_keys:
        raise RaceNoteRequestError("Could not resolve previous-result years from KYI keys")

    for previous_year in sorted(previous_years):
        sed_path = raw_dir / "SED" / f"SED_{previous_year}.zip"
        skb_path = raw_dir / "SKB" / f"SKB_{previous_year}.zip"
        if not sed_path.is_file() or not skb_path.is_file():
            fetch_historical_raw(previous_year, raw_dir, force_fetch, ["SED", "SKB"])

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
    yyMMdd = request.target_date.strftime("%y%m%d")
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for kind in ("BAC", "KYI", "CHA", "CYB"):
            payload = b"\r\n".join(selected[kind]) + b"\r\n"
            archive.writestr(f"{kind}{yyMMdd}.txt", payload)
        archive.writestr(f"ZED{yyMMdd}.txt", b"\r\n".join(zed) + (b"\r\n" if zed else b""))
        archive.writestr(f"ZKB{yyMMdd}.txt", b"\r\n".join(zkb) + (b"\r\n" if zkb else b""))

    return {
        "race_key_count": len(race_keys),
        "record_counts": {**{kind: len(rows) for kind, rows in selected.items()}, "ZED": len(zed), "ZKB": len(zkb)},
        "previous_result_key_count": len(previous_result_keys),
        "previous_result_years": sorted(previous_years),
    }


def fetch_paci(request: RaceNoteRequest, work_dir: Path, force: bool) -> Path:
    """Fetch target-date PACI using the existing authenticated downloader."""
    paci_dir = work_dir / "PACI"
    command = [
        sys.executable,
        str(FETCH_PACI),
        "--date",
        request.compact_date,
        "--out-dir",
        str(paci_dir),
    ]
    if force:
        command.append("--force")
    run(command, cwd=HERE)
    paci_path = paci_dir / f"PACI{request.target_date.strftime('%y%m%d')}.zip"
    if not paci_path.is_file():
        raise RaceNoteRequestError(f"PACI fetch completed but file is missing: {paci_path}")
    return paci_path


def convert_base(paci_path: Path, request: RaceNoteRequest, work_dir: Path) -> Path:
    """Create base RaceNote bundles using the existing converter."""
    command = [
        sys.executable,
        str(CONVERTER),
        str(paci_path),
        "--output",
        str(work_dir),
        "--format",
        "json",
    ]
    if request.scope == "race":
        command.extend(["--race", f"{request.venue}{request.race_no}"])
    run(command)
    bundle_dir = work_dir / f"RaceNote_{request.compact_date}"
    if not bundle_dir.is_dir():
        raise RaceNoteRequestError(f"Converter output directory missing: {bundle_dir}")
    return bundle_dir


def select_bundles(bundle_dir: Path, request: RaceNoteRequest) -> list[Path]:
    """Select all, venue or one-race bundle after conversion."""
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
    """Add Analysis/Mart information using the validated enrichment implementation."""
    temp_dir = output_dir / "_enrichment_tmp"
    command = [
        sys.executable,
        str(ENRICHER),
        "--bundle",
        str(bundle),
        "--analysis",
        str(analysis),
        "--mart",
        str(mart),
        "--output-dir",
        str(temp_dir),
        "--stats-window-years",
        str(stats_window_years),
    ]
    run(command)
    enriched = temp_dir / f"{bundle.stem}_enriched_8runs_poc.json"
    if not enriched.is_file():
        raise RaceNoteRequestError(f"Enriched bundle missing: {enriched}")
    target = output_dir / bundle.name
    shutil.copy2(enriched, target)
    return target


def package_output(output_dir: Path, request: RaceNoteRequest, generated: list[Path], plan: dict, reconstruction: dict | None) -> Path:
    """Write request manifest and package selected RaceNote files as one ZIP."""
    manifest = {
        "request": plan,
        "bundle_count": len(generated),
        "bundles": [path.name for path in generated],
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
    """Resolve the request, choose a backend, enrich as-of and package output."""
    args = parse_args()
    request = normalize_request(args)
    plan = build_plan(request)
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
    if request.temporal_mode == "past":
        raw_dir = args.raw_dir if args.raw_dir is not None else request_root / "raw_cache"
        # First fetch only target-date pre-race source kinds. SED/SKB years are
        # resolved from KYI previous-result keys inside build_historical_paci.
        fetch_historical_raw(
            request.target_date.year,
            raw_dir,
            args.force_fetch,
            ["BAC", "KYI", "CHA", "CYB"],
        )
        paci_path = request_root / f"PACI_REBUILT_{request.compact_date}.zip"
        reconstruction = build_historical_paci(
            raw_dir, request, args.analysis, paci_path, args.force_fetch
        )
    else:
        paci_path = fetch_paci(request, request_root, args.force_fetch)

    base_dir = convert_base(paci_path, request, work_dir)
    selected = select_bundles(base_dir, request)

    generated: list[Path] = []
    for bundle in selected:
        generated.append(
            enrich_bundle(bundle, args.analysis, args.mart, final_dir, args.stats_window_years)
        )

    zip_path = package_output(final_dir, request, generated, plan, reconstruction)
    print(json.dumps({"status": "success", "zip": str(zip_path), "bundle_count": len(generated)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
