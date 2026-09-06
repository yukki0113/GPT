#!/usr/bin/env python3
"""Build one full-month RaceNote Archive shard from historical annual JRDB Raw.

The script is the upstream production candidate for <=2025 historical months.
It uses Analysis Lite only as an authoritative race identity index; no target
result values are read. Base RaceNote v0.2 is reconstructed from annual
BAC/KYI/CHA/CYB plus only the SED/SKB rows referenced by selected KYI previous
result keys. The resulting bundle set is passed to the canonical Archive
builder with an exact expected race identity set.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import time
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import racenote_archive as archive
from jrdb_raw import iter_archive_records, race_key as common_race_key, result_key as common_result_key
from jrdb_racenote_raw_adapter import previous_result_keys as common_previous_result_keys

HERE = Path(__file__).resolve().parent
FETCH_HISTORY = HERE / "fetch_jrdb_history.py"
CONVERTER = HERE / "racenote_jrdb.py"
ARCHIVE_BUILDER = HERE / "build_racenote_archive.py"

TARGET_KINDS = ("BAC", "KYI", "CHA", "CYB")
HISTORY_KINDS = ("SED", "SKB")
PREV_RESULT_SLICES = (
    (203, 219),
    (219, 235),
    (235, 251),
    (251, 267),
    (267, 283),
)


class MonthBuildError(RuntimeError):
    """A full-month Archive cannot be reconstructed safely."""


@dataclass(frozen=True)
class RaceIdentity:
    """One authoritative race identity from Analysis Lite."""

    race_key: str
    race_date: str
    venue_code: str
    race_no: int

    @property
    def venue(self) -> str:
        """Return the canonical JRA venue name."""
        return archive.JRA_VENUES[self.venue_code]


@dataclass
class MonthIndex:
    """Authoritative target-month race index."""

    races: list[RaceIdentity]
    by_race_key: dict[str, RaceIdentity]
    by_date: dict[str, list[RaceIdentity]]


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Build one full-month RaceNote Archive from annual JRDB Raw"
    )
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--archive-output", type=Path, required=True)
    parser.add_argument("--converter-git-sha", required=True)
    parser.add_argument(
        "--source-ref",
        default=None,
        help="Optional logical provenance label; never use URLs or storage IDs",
    )
    parser.add_argument(
        "--fetch-missing",
        action="store_true",
        help="Fetch missing annual Raw packs through fetch_jrdb_history.py",
    )
    parser.add_argument("--force-fetch", action="store_true")
    parser.add_argument(
        "--validation-report",
        type=Path,
        default=None,
        help="Archive validation JSON path",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Month build summary JSON path",
    )
    return parser.parse_args()


def parse_target_month(value: str) -> tuple[str, date, date]:
    """Validate YYYYMM and return [start, next_month)."""
    text = value.strip()
    try:
        start = datetime.strptime(text, "%Y%m").date().replace(day=1)
    except ValueError as exc:
        raise MonthBuildError("--target-month must be a valid YYYYMM") from exc

    if start.month == 12:
        next_month = date(start.year + 1, 1, 1)
    else:
        next_month = date(start.year, start.month + 1, 1)
    return text, start, next_month


def run(command: list[str]) -> None:
    """Run a subprocess with fail-fast semantics."""
    subprocess.run(command, check=True)


def sha256_file(path: Path) -> str:
    """Return SHA-256 for one file without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_sqlite(path: Path) -> None:
    """Require a readable Analysis Lite SQLite."""
    if not path.is_file():
        raise MonthBuildError(f"Analysis Lite not found: {path}")
    connection = sqlite3.connect(path)
    try:
        row = connection.execute("PRAGMA integrity_check").fetchone()
        if row is None or row[0] != "ok":
            raise MonthBuildError(f"Analysis Lite integrity_check failed: {row}")
    finally:
        connection.close()


def load_month_index(analysis: Path, start: date, next_month: date) -> MonthIndex:
    """Read only target-month race identity fields from Analysis Lite."""
    sql = """
        SELECT DISTINCT race_key, race_date, venue_code, race_no
        FROM fact_entry_result_lite
        WHERE race_date >= ? AND race_date < ?
        ORDER BY race_date, venue_code, race_no, race_key
    """
    connection = sqlite3.connect(analysis)
    try:
        rows = connection.execute(
            sql,
            (start.isoformat(), next_month.isoformat()),
        ).fetchall()
    finally:
        connection.close()

    if not rows:
        raise MonthBuildError(
            f"Analysis Lite has no races in target month {start:%Y%m}"
        )

    races: list[RaceIdentity] = []
    by_race_key: dict[str, RaceIdentity] = {}
    identity_keys: set[tuple[str, str, int]] = set()
    by_date: dict[str, list[RaceIdentity]] = defaultdict(list)

    for row in rows:
        race_key = str(row[0] or "").strip()
        race_date = archive.normalize_race_date(row[1])
        venue_code = str(row[2] or "").strip()
        race_no = int(row[3])

        if len(race_key) != 8 or not race_key.isascii():
            raise MonthBuildError(f"Invalid Analysis race_key: {race_key!r}")
        if venue_code not in archive.JRA_VENUES:
            raise MonthBuildError(f"Invalid Analysis venue_code: {venue_code!r}")
        if not 1 <= race_no <= 12:
            raise MonthBuildError(f"Invalid Analysis race_no: {race_no}")

        identity = RaceIdentity(race_key, race_date, venue_code, race_no)
        logical_key = (race_date, venue_code, race_no)
        if race_key in by_race_key:
            raise MonthBuildError(f"Duplicate Analysis race_key: {race_key}")
        if logical_key in identity_keys:
            raise MonthBuildError(f"Duplicate Analysis race identity: {logical_key}")

        races.append(identity)
        by_race_key[race_key] = identity
        identity_keys.add(logical_key)
        by_date[race_date].append(identity)

    return MonthIndex(races, by_race_key, dict(by_date))


def annual_zip(raw_dir: Path, kind: str, year: int) -> Path:
    """Return canonical annual Raw cache path."""
    return raw_dir / kind / f"{kind}_{year}.zip"


def zip_is_valid(path: Path, kind: str) -> bool:
    """Return whether one annual Raw ZIP is readable and contains the kind."""
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        with zipfile.ZipFile(path) as source:
            members = [
                name
                for name in source.namelist()
                if Path(name).name.upper().startswith(kind)
            ]
            return bool(members) and source.testzip() is None
    except (OSError, zipfile.BadZipFile):
        return False


def ensure_raw_kinds(
    raw_dir: Path,
    year: int,
    kinds: Iterable[str],
    fetch_missing: bool,
    force_fetch: bool,
) -> list[Path]:
    """Ensure requested annual Raw packs are locally available and valid."""
    kind_list = list(kinds)
    missing = [
        kind
        for kind in kind_list
        if force_fetch or not zip_is_valid(annual_zip(raw_dir, kind, year), kind)
    ]
    if missing and fetch_missing:
        command = [
            sys.executable,
            str(FETCH_HISTORY),
            "--year",
            str(year),
            "--kinds",
            *missing,
            "--output-dir",
            str(raw_dir.resolve()),
        ]
        if force_fetch:
            command.append("--force")
        run(command)

    still_missing = [
        kind
        for kind in kind_list
        if not zip_is_valid(annual_zip(raw_dir, kind, year), kind)
    ]
    if still_missing:
        raise MonthBuildError(
            f"Missing/invalid annual Raw for {year}: {still_missing}"
        )
    return [annual_zip(raw_dir, kind, year) for kind in kind_list]


def iter_records(zip_path: Path, kind: str) -> Iterable[bytes]:
    """Yield fixed-width rows from all matching members in source order."""
    for _member, record in iter_archive_records(zip_path, kind):
        yield record
    return
    with zipfile.ZipFile(zip_path) as source:
        members = [
            name
            for name in source.namelist()
            if Path(name).name.upper().startswith(kind)
        ]
        if not members:
            raise MonthBuildError(f"No {kind} member in {zip_path}")
        for member in members:
            for line in source.read(member).splitlines():
                if line:
                    yield line


def previous_result_keys(line: bytes) -> list[bytes]:
    """Return explicit KYI previous-result keys without guessing missing values."""
    return [key.encode("ascii") for key in common_previous_result_keys(line)]
    output: list[bytes] = []
    for start, end in PREV_RESULT_SLICES:
        key = line[start:end].strip()
        if key and key != b"0" * 16:
            output.append(key)
    return output


def previous_result_year(key: bytes) -> int:
    """Return YYYY from a 16-byte result key."""
    try:
        return int(key[-8:-4].decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise MonthBuildError(f"Invalid previous result key date: {key!r}") from exc


def extract_target_base_records(
    raw_dir: Path,
    year: int,
    index: MonthIndex,
) -> tuple[
    dict[str, dict[str, list[bytes]]],
    dict[str, set[bytes]],
    dict[str, dict[str, int]],
]:
    """Select target-month BAC/KYI/CHA/CYB in one pass per annual file."""
    by_date: dict[str, dict[str, list[bytes]]] = {
        race_date: {kind: [] for kind in TARGET_KINDS}
        for race_date in index.by_date
    }
    prev_keys_by_date: dict[str, set[bytes]] = {
        race_date: set() for race_date in index.by_date
    }
    counts_by_race: dict[str, dict[str, int]] = {
        race.race_key: {kind: 0 for kind in TARGET_KINDS}
        for race in index.races
    }

    for kind in TARGET_KINDS:
        path = annual_zip(raw_dir, kind, year)
        for line in iter_records(path, kind):
            race_key = common_race_key(line)
            identity = index.by_race_key.get(race_key)
            if identity is None:
                continue
            by_date[identity.race_date][kind].append(line)
            counts_by_race[race_key][kind] += 1
            if kind == "KYI":
                prev_keys_by_date[identity.race_date].update(
                    previous_result_keys(line)
                )

    errors: list[str] = []
    for race in index.races:
        counts = counts_by_race[race.race_key]
        if counts["BAC"] != 1:
            errors.append(
                f"{race.race_date} {race.venue}{race.race_no}R BAC={counts['BAC']}"
            )
        if counts["KYI"] <= 0:
            errors.append(
                f"{race.race_date} {race.venue}{race.race_no}R KYI={counts['KYI']}"
            )
        if counts["CHA"] != counts["KYI"]:
            errors.append(
                f"{race.race_date} {race.venue}{race.race_no}R "
                f"CHA={counts['CHA']} KYI={counts['KYI']}"
            )
        if counts["CYB"] != counts["KYI"]:
            errors.append(
                f"{race.race_date} {race.venue}{race.race_no}R "
                f"CYB={counts['CYB']} KYI={counts['KYI']}"
            )
    if errors:
        raise MonthBuildError(
            "Target Raw completeness check failed: " + "; ".join(errors[:20])
        )

    return by_date, prev_keys_by_date, counts_by_race


def extract_history_records(
    raw_dir: Path,
    prev_keys_by_date: dict[str, set[bytes]],
    fetch_missing: bool,
    force_fetch: bool,
) -> tuple[
    dict[str, dict[str, list[bytes]]],
    list[int],
    set[bytes],
    set[bytes],
    list[Path],
]:
    """Select only SED/SKB rows referenced by target-month KYI previous keys."""
    all_keys: set[bytes] = set()
    key_dates: dict[bytes, set[str]] = defaultdict(set)
    for race_date, keys in prev_keys_by_date.items():
        for key in keys:
            all_keys.add(key)
            key_dates[key].add(race_date)

    history_by_date: dict[str, dict[str, list[bytes]]] = {
        race_date: {kind: [] for kind in HISTORY_KINDS}
        for race_date in prev_keys_by_date
    }
    if not all_keys:
        return history_by_date, [], set(), set(), []

    years = sorted({previous_result_year(key) for key in all_keys})
    used_paths: list[Path] = []
    matched_zed: set[bytes] = set()
    matched_zkb: set[bytes] = set()

    for year in years:
        used_paths.extend(
            ensure_raw_kinds(
                raw_dir,
                year,
                HISTORY_KINDS,
                fetch_missing,
                force_fetch,
            )
        )
        for kind in HISTORY_KINDS:
            path = annual_zip(raw_dir, kind, year)
            for line in iter_records(path, kind):
                key = line[10:26].strip()
                dates = key_dates.get(key)
                if not dates:
                    continue
                for race_date in dates:
                    history_by_date[race_date][kind].append(line)
                if kind == "SED":
                    matched_zed.add(key)
                else:
                    matched_zkb.add(key)

    return history_by_date, years, matched_zed, matched_zkb, used_paths


def write_fixed_member(rows: list[bytes]) -> bytes:
    """Return CRLF-terminated fixed-width member bytes."""
    if not rows:
        return b""
    return b"\r\n".join(rows) + b"\r\n"


def write_daily_paci(
    destination: Path,
    race_date: str,
    base_rows: dict[str, list[bytes]],
    history_rows: dict[str, list[bytes]],
) -> None:
    """Write one PACI-equivalent ZIP for the target date."""
    short_date = race_date.replace("-", "")[2:]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for kind in TARGET_KINDS:
            output.writestr(
                f"{kind}{short_date}.txt",
                write_fixed_member(base_rows[kind]),
            )
        for kind, paci_kind in (("SED", "ZED"), ("SKB", "ZKB")):
            output.writestr(
                f"{paci_kind}{short_date}.txt",
                write_fixed_member(history_rows[kind]),
            )


def convert_all_dates(
    index: MonthIndex,
    work_dir: Path,
    base_rows_by_date: dict[str, dict[str, list[bytes]]],
    history_rows_by_date: dict[str, dict[str, list[bytes]]],
) -> tuple[Path, list[dict]]:
    """Convert every target date to base v0.2 and collect one common bundle dir."""
    paci_dir = work_dir / "paci_rebuilt"
    converter_root = work_dir / "converter"
    bundle_dir = work_dir / "bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    date_reports: list[dict] = []

    for race_date in sorted(index.by_date):
        compact_date = race_date.replace("-", "")
        paci_path = paci_dir / f"PACI_REBUILT_{compact_date}.zip"
        write_daily_paci(
            paci_path,
            race_date,
            base_rows_by_date[race_date],
            history_rows_by_date[race_date],
        )

        date_output = converter_root / compact_date
        run(
            [
                sys.executable,
                str(CONVERTER),
                str(paci_path),
                "--output",
                str(date_output),
                "--format",
                "json",
            ]
        )

        generated = sorted(date_output.rglob("race_bundle_*.json"))
        expected_count = len(index.by_date[race_date])
        if len(generated) != expected_count:
            raise MonthBuildError(
                f"Converter bundle count mismatch {race_date}: "
                f"expected={expected_count} actual={len(generated)}"
            )

        for path in generated:
            destination = bundle_dir / path.name
            if destination.exists():
                raise MonthBuildError(f"Duplicate output bundle filename: {path.name}")
            shutil.copy2(path, destination)

        validation_reports = sorted(date_output.rglob("validation_report.json"))
        if len(validation_reports) != 1:
            raise MonthBuildError(
                f"Expected one converter validation report for {race_date}"
            )
        validation = json.loads(
            validation_reports[0].read_text(encoding="utf-8")
        )
        errors = validation.get("bundle_generation_errors")
        if errors:
            raise MonthBuildError(
                f"Converter reported errors for {race_date}: {errors[:10]}"
            )
        date_reports.append(
            {
                "race_date": race_date,
                "expected_races": expected_count,
                "generated_races": len(generated),
                "kyi_horses": validation.get("kyi_horse_count"),
                "zed_match": validation.get("joins", {}).get("KYI_previous_to_ZED"),
                "zkb_match": validation.get("joins", {}).get("KYI_previous_to_ZKB"),
                "unknown_code_count": validation.get("unknown_code_count"),
            }
        )

    return bundle_dir, date_reports


def write_expected_index(path: Path, target_month: str, index: MonthIndex) -> None:
    """Write the exact race identity set consumed by the canonical Archive builder."""
    rows = [
        {
            "race_date": race.race_date,
            "venue_code": race.venue_code,
            "venue": race.venue,
            "race_no": race.race_no,
        }
        for race in index.races
    ]
    payload = {
        "target_month": target_month,
        "source": "Analysis Lite identity fields only",
        "races": rows,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def source_manifest_rows(
    target_paths: list[Path],
    history_paths: list[Path],
) -> list[dict]:
    """Return non-location provenance rows for every Raw input actually used."""
    rows: list[dict] = []
    seen: set[Path] = set()
    for path, role in [
        *[(item, "target_race_base") for item in target_paths],
        *[(item, "recent_history_source") for item in history_paths],
    ]:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        kind = path.name.split("_", 1)[0]
        period = path.stem.rsplit("_", 1)[-1]
        rows.append(
            {
                "source_type": "ANNUAL_RAW",
                "source_period": period,
                "filename": path.name,
                "sha256": sha256_file(path),
                "role": f"{role}:{kind}",
            }
        )
    rows.sort(key=lambda row: (row["source_period"], row["filename"], row["role"]))
    return rows


def build_archive(
    target_month: str,
    index: MonthIndex,
    bundle_dir: Path,
    archive_output: Path,
    work_dir: Path,
    converter_git_sha: str,
    source_ref: str,
    target_paths: list[Path],
    history_paths: list[Path],
    validation_report: Path,
) -> dict:
    """Invoke the canonical Archive builder with full-month publication rules."""
    expected_index = work_dir / "expected_race_index.json"
    source_manifest = work_dir / "source_manifest.json"
    write_expected_index(expected_index, target_month, index)
    source_manifest.write_text(
        json.dumps(
            {"sources": source_manifest_rows(target_paths, history_paths)},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    command = [
        sys.executable,
        str(ARCHIVE_BUILDER),
        "--bundle-dir",
        str(bundle_dir),
        "--target-month",
        target_month,
        "--output",
        str(archive_output),
        "--source-mode",
        "annual_raw_reconstruction",
        "--coverage-mode",
        "full_month",
        "--expected-index",
        str(expected_index),
        "--source-ref",
        source_ref,
        "--source-manifest",
        str(source_manifest),
        "--converter-git-sha",
        converter_git_sha,
        "--expected-race-count",
        str(len(index.races)),
        "--validation-report",
        str(validation_report),
    ]
    run(command)
    return json.loads(validation_report.read_text(encoding="utf-8"))


def default_source_ref(target_month: str) -> str:
    """Return a stable logical label without external storage location data."""
    return f"annual-raw-{target_month}"


def build(args: argparse.Namespace) -> dict:
    """Execute full-month reconstruction and return a validation summary."""
    started = time.monotonic()
    target_month, start, next_month = parse_target_month(args.target_month)
    if start.year >= 2026:
        raise MonthBuildError(
            "Annual Raw monthly builder is for <=2025; use PACI-based Archive build for 2026+"
        )

    validate_sqlite(args.analysis)
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.work_dir.mkdir(parents=True, exist_ok=True)
    args.archive_output.parent.mkdir(parents=True, exist_ok=True)

    index = load_month_index(args.analysis, start, next_month)
    target_paths = ensure_raw_kinds(
        args.raw_dir,
        start.year,
        TARGET_KINDS,
        args.fetch_missing,
        args.force_fetch,
    )
    base_rows_by_date, prev_keys_by_date, counts_by_race = extract_target_base_records(
        args.raw_dir,
        start.year,
        index,
    )
    (
        history_rows_by_date,
        history_years,
        matched_zed,
        matched_zkb,
        history_paths,
    ) = extract_history_records(
        args.raw_dir,
        prev_keys_by_date,
        args.fetch_missing,
        args.force_fetch,
    )

    bundle_dir, date_reports = convert_all_dates(
        index,
        args.work_dir,
        base_rows_by_date,
        history_rows_by_date,
    )

    validation_report = args.validation_report or (
        args.archive_output.with_name(args.archive_output.stem + "_validation.json")
    )
    source_ref = args.source_ref or default_source_ref(target_month)
    archive_validation = build_archive(
        target_month,
        index,
        bundle_dir,
        args.archive_output,
        args.work_dir,
        args.converter_git_sha,
        source_ref,
        target_paths,
        history_paths,
        validation_report,
    )

    if not archive_validation.get("publishable"):
        raise MonthBuildError("Full-month Archive validation did not mark shard publishable")
    if archive_validation.get("publication_status") != "publishable":
        raise MonthBuildError("Archive publication_status is not publishable")
    if not archive_validation.get("identity_match"):
        raise MonthBuildError("Archive expected race identity set did not match")

    all_prev_keys = set().union(*prev_keys_by_date.values()) if prev_keys_by_date else set()
    total_kyi = sum(
        counts["KYI"] for counts in counts_by_race.values()
    )
    summary = {
        "status": "PASS",
        "target_month": target_month,
        "race_date_count": len(index.by_date),
        "expected_race_count": len(index.races),
        "generated_bundle_count": archive_validation.get("selected_bundle_count"),
        "target_kyi_horse_count": total_kyi,
        "previous_result_key_count": len(all_prev_keys),
        "history_years": history_years,
        "zed_matched_key_count": len(matched_zed),
        "zkb_matched_key_count": len(matched_zkb),
        "zed_unmatched_key_count": len(all_prev_keys - matched_zed),
        "zkb_unmatched_key_count": len(all_prev_keys - matched_zkb),
        "archive_file": args.archive_output.name,
        "archive_bytes": args.archive_output.stat().st_size,
        "archive_schema_version": archive_validation.get("archive_schema_version"),
        "base_schema_version": archive_validation.get("base_schema_version"),
        "coverage_mode": archive_validation.get("coverage_mode"),
        "publication_status": archive_validation.get("publication_status"),
        "publishable": archive_validation.get("publishable"),
        "identity_match": archive_validation.get("identity_match"),
        "verified_bundle_count": archive_validation.get("verified_bundle_count"),
        "total_json_bytes": archive_validation.get("total_json_bytes"),
        "total_compressed_blob_bytes": archive_validation.get("total_compressed_blob_bytes"),
        "compression_ratio": archive_validation.get("compression_ratio"),
        "expected_index_sha256": archive_validation.get("expected_index_sha256"),
        "source_input_count": archive_validation.get("source_input_count"),
        "provenance_status": archive_validation.get("provenance_status"),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "date_reports": date_reports,
    }

    summary_path = args.summary or (args.work_dir / "month_build_summary.json")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary["summary_path"] = str(summary_path)
    return summary


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    try:
        summary = build(args)
    except (
        MonthBuildError,
        archive.RaceNoteArchiveError,
        sqlite3.Error,
        subprocess.CalledProcessError,
        OSError,
        zipfile.BadZipFile,
    ) as exc:
        print(
            json.dumps(
                {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
