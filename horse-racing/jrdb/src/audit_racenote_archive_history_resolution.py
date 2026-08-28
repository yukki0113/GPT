#!/usr/bin/env python3
"""Audit unresolved KYI previous-result keys for a RaceNote Archive month.

The audit deliberately reports source-observable facts rather than assigning
reasons such as foreign/local racing. A JRDB result key is treated as
``blood_registration_no + YYYYMMDD``. Unresolved keys are compared with
Analysis Lite using the corresponding ``horse_id + race_date`` pair.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import racenote_archive as archive

PREV_RESULT_SLICES = (
    (203, 219),
    (219, 235),
    (235, 251),
    (251, 267),
    (267, 283),
)


class AuditError(RuntimeError):
    """History-resolution audit cannot be completed safely."""


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Audit unresolved RaceNote Archive previous-result keys"
    )
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def parse_target_month(value: str) -> tuple[str, date, date]:
    """Validate YYYYMM and return [start, next_month)."""
    text = value.strip()
    try:
        start = datetime.strptime(text, "%Y%m").date().replace(day=1)
    except ValueError as exc:
        raise AuditError("--target-month must be valid YYYYMM") from exc
    if start.month == 12:
        next_month = date(start.year + 1, 1, 1)
    else:
        next_month = date(start.year, start.month + 1, 1)
    return text, start, next_month


def validate_analysis(path: Path) -> None:
    """Require a valid Analysis Lite SQLite."""
    if not path.is_file():
        raise AuditError(f"Analysis Lite not found: {path}")
    connection = sqlite3.connect(path)
    try:
        row = connection.execute("PRAGMA integrity_check").fetchone()
        if row is None or row[0] != "ok":
            raise AuditError(f"Analysis integrity_check failed: {row}")
    finally:
        connection.close()


def annual_zip(raw_dir: Path, kind: str, year: int) -> Path:
    """Return canonical annual Raw path."""
    return raw_dir / kind / f"{kind}_{year}.zip"


def require_zip(raw_dir: Path, kind: str, year: int) -> Path:
    """Require one readable annual Raw ZIP."""
    path = annual_zip(raw_dir, kind, year)
    if not path.is_file():
        raise AuditError(f"Raw ZIP not found: {path}")
    try:
        with zipfile.ZipFile(path) as source:
            members = [
                name
                for name in source.namelist()
                if Path(name).name.upper().startswith(kind)
            ]
            if not members or source.testzip() is not None:
                raise AuditError(f"Raw ZIP validation failed: {path}")
    except zipfile.BadZipFile as exc:
        raise AuditError(f"Bad ZIP: {path}") from exc
    return path


def iter_records(path: Path, kind: str) -> Iterable[bytes]:
    """Yield non-empty fixed-width rows from matching ZIP members."""
    with zipfile.ZipFile(path) as source:
        members = [
            name
            for name in source.namelist()
            if Path(name).name.upper().startswith(kind)
        ]
        for member in members:
            for line in source.read(member).splitlines():
                if line:
                    yield line


def target_races(
    analysis: Path,
    start: date,
    next_month: date,
) -> dict[str, dict]:
    """Return authoritative target-month race identities keyed by race_key."""
    connection = sqlite3.connect(analysis)
    try:
        rows = connection.execute(
            """
            SELECT DISTINCT race_key, race_date, venue_code, race_no
            FROM fact_entry_result_lite
            WHERE race_date >= ? AND race_date < ?
            ORDER BY race_date, venue_code, race_no
            """,
            (start.isoformat(), next_month.isoformat()),
        ).fetchall()
    finally:
        connection.close()
    if not rows:
        raise AuditError("No target-month races found in Analysis Lite")

    output: dict[str, dict] = {}
    for row in rows:
        race_key = str(row[0] or "").strip()
        venue_code = str(row[2] or "").strip()
        if venue_code not in archive.JRA_VENUES:
            raise AuditError(f"Unknown JRA venue_code: {venue_code}")
        output[race_key] = {
            "race_date": archive.normalize_race_date(row[1]),
            "venue_code": venue_code,
            "venue": archive.JRA_VENUES[venue_code],
            "race_no": int(row[3]),
        }
    return output


def decode_name(record: bytes) -> str | None:
    """Decode KYI horse name only for audit readability."""
    value = (
        record[18:54]
        .decode("cp932", errors="replace")
        .replace("\u3000", " ")
        .strip()
    )
    return value or None


def previous_keys(record: bytes) -> list[tuple[int, str]]:
    """Return non-empty previous result keys with 1-based slot number."""
    output: list[tuple[int, str]] = []
    for slot, (start, end) in enumerate(PREV_RESULT_SLICES, 1):
        value = record[start:end].strip()
        if not value or value == b"0" * 16:
            continue
        try:
            key = value.decode("ascii")
        except UnicodeDecodeError as exc:
            raise AuditError(f"Non-ASCII previous result key: {value!r}") from exc
        if len(key) != 16 or not key[-8:].isdigit():
            raise AuditError(f"Invalid previous result key: {key!r}")
        output.append((slot, key))
    return output


def collect_references(
    raw_dir: Path,
    year: int,
    races: dict[str, dict],
) -> dict[str, list[dict]]:
    """Collect all target-month KYI references to previous result keys."""
    path = require_zip(raw_dir, "KYI", year)
    references: dict[str, list[dict]] = defaultdict(list)
    target_keys = set(races)
    for record in iter_records(path, "KYI"):
        try:
            race_key = record[:8].decode("ascii")
        except UnicodeDecodeError:
            continue
        if race_key not in target_keys:
            continue
        horse_no_raw = record[8:10].decode("ascii", errors="ignore").strip()
        horse_no = int(horse_no_raw) if horse_no_raw.isdigit() else None
        horse_id = record[10:18].decode("ascii", errors="ignore").strip() or None
        horse_name = decode_name(record)
        race = races[race_key]
        for slot, result_key in previous_keys(record):
            references[result_key].append(
                {
                    "target_race_key": race_key,
                    "target_race_date": race["race_date"],
                    "target_venue_code": race["venue_code"],
                    "target_venue": race["venue"],
                    "target_race_no": race["race_no"],
                    "target_horse_no": horse_no,
                    "target_horse_id": horse_id,
                    "target_horse_name": horse_name,
                    "previous_slot": slot,
                }
            )
    if not references:
        raise AuditError("No previous-result references found in target-month KYI")
    return dict(references)


def collect_resolved_keys(
    raw_dir: Path,
    kind: str,
    years: list[int],
    wanted: set[str],
) -> set[str]:
    """Return wanted result keys found in annual SED/SKB packs."""
    resolved: set[str] = set()
    for year in years:
        path = require_zip(raw_dir, kind, year)
        for record in iter_records(path, kind):
            value = record[10:26].strip()
            try:
                key = value.decode("ascii")
            except UnicodeDecodeError:
                continue
            if key in wanted:
                resolved.add(key)
    return resolved


def analysis_coverage(
    analysis: Path,
    unmatched_keys: list[str],
) -> dict[str, dict]:
    """Compare unmatched result-key horse/date pairs with Analysis Lite."""
    horse_ids = sorted({key[:8] for key in unmatched_keys})
    if not horse_ids:
        return {}

    connection = sqlite3.connect(analysis)
    try:
        existing_horses: set[str] = set()
        exact_pairs: set[tuple[str, str]] = set()
        dates_by_horse: dict[str, list[str]] = defaultdict(list)

        chunk_size = 400
        for offset in range(0, len(horse_ids), chunk_size):
            chunk = horse_ids[offset:offset + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            rows = connection.execute(
                f"""
                SELECT DISTINCT horse_id, race_date
                FROM fact_entry_result_lite
                WHERE horse_id IN ({placeholders})
                ORDER BY horse_id, race_date
                """,
                chunk,
            ).fetchall()
            for horse_id, race_date in rows:
                if not horse_id or not race_date:
                    continue
                horse = str(horse_id)
                race_date_text = archive.normalize_race_date(race_date)
                existing_horses.add(horse)
                exact_pairs.add((horse, race_date_text))
                dates_by_horse[horse].append(race_date_text)
    finally:
        connection.close()

    output: dict[str, dict] = {}
    for key in unmatched_keys:
        horse_id = key[:8]
        previous_date = archive.normalize_race_date(key[8:])
        if (horse_id, previous_date) in exact_pairs:
            status = "exact_horse_date_present"
        elif horse_id in existing_horses:
            status = "horse_present_date_absent"
        else:
            status = "horse_absent"
        horse_dates = dates_by_horse.get(horse_id, [])
        output[key] = {
            "horse_id": horse_id,
            "previous_date": previous_date,
            "analysis_status": status,
            "analysis_first_date": horse_dates[0] if horse_dates else None,
            "analysis_last_date": horse_dates[-1] if horse_dates else None,
            "analysis_race_date_count": len(horse_dates),
        }
    return output


def audit(args: argparse.Namespace) -> dict:
    """Run the complete history-resolution audit."""
    target_month, start, next_month = parse_target_month(args.target_month)
    validate_analysis(args.analysis)
    races = target_races(args.analysis, start, next_month)
    references = collect_references(args.raw_dir, start.year, races)
    wanted = set(references)
    years = sorted({int(key[8:12]) for key in wanted})
    resolved_zed = collect_resolved_keys(args.raw_dir, "SED", years, wanted)
    resolved_zkb = collect_resolved_keys(args.raw_dir, "SKB", years, wanted)

    unresolved_zed = sorted(wanted - resolved_zed)
    unresolved_zkb = sorted(wanted - resolved_zkb)
    coverage = analysis_coverage(args.analysis, unresolved_zed)

    rows: list[dict] = []
    for key in unresolved_zed:
        row = {
            "result_key": key,
            **coverage[key],
            "reference_count": len(references[key]),
            "target_references": references[key],
            "zkb_resolved": key in resolved_zkb,
        }
        rows.append(row)

    status_counts = Counter(row["analysis_status"] for row in rows)
    previous_year_counts = Counter(row["previous_date"][:4] for row in rows)
    slot_counts = Counter(
        reference["previous_slot"]
        for row in rows
        for reference in row["target_references"]
    )
    target_date_counts = Counter(
        reference["target_race_date"]
        for row in rows
        for reference in row["target_references"]
    )

    report = {
        "status": "PASS",
        "target_month": target_month,
        "target_race_count": len(races),
        "previous_result_key_count": len(wanted),
        "zed_resolved_key_count": len(resolved_zed),
        "zed_unresolved_key_count": len(unresolved_zed),
        "zkb_resolved_key_count": len(resolved_zkb),
        "zkb_unresolved_key_count": len(unresolved_zkb),
        "zed_zkb_unresolved_sets_equal": set(unresolved_zed) == set(unresolved_zkb),
        "analysis_status_counts": dict(sorted(status_counts.items())),
        "unresolved_previous_year_counts": dict(sorted(previous_year_counts.items())),
        "unresolved_reference_slot_counts": {
            str(key): value for key, value in sorted(slot_counts.items())
        },
        "unresolved_target_date_reference_counts": dict(sorted(target_date_counts.items())),
        "classification_note": (
            "analysis_status is source-observable only: exact_horse_date_present means the "
            "same horse_id/date exists in Analysis Lite; horse_present_date_absent means the "
            "horse exists in Analysis but that date does not; horse_absent means no Analysis "
            "row for the horse_id. No foreign/local cause is inferred."
        ),
        "unresolved_rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    try:
        report = audit(args)
    except (AuditError, archive.RaceNoteArchiveError, sqlite3.Error, OSError, zipfile.BadZipFile) as exc:
        print(
            json.dumps(
                {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    summary = {key: value for key, value in report.items() if key != "unresolved_rows"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
