#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-year JRDB Raw history access built on :mod:`jrdb_raw`.

Annual ZIP files remain the source data. The reader scans newest years and
members first and stops as soon as the requested number of runs is collected,
so consumers do not need a canonical SQLite dependency for ordinary history
lookups.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jrdb_raw import Parser, iter_archive_records, raw_field, ymd

VERSION = "0.1.0"


@dataclass(frozen=True)
class SourceRef:
    """Provenance for one record returned from annual Raw."""

    archive: str
    member: str
    year: int


@dataclass(frozen=True)
class HorseRun:
    """One parsed SED run plus Raw provenance."""

    source: SourceRef
    data: dict[str, Any]


def annual_archive(raw_root: Path, kind: str, year: int) -> Path:
    """Resolve the standard annual Raw path ROOT/KIND/KIND_YYYY.zip."""
    normalized = kind.upper()
    return raw_root / normalized / f"{normalized}_{year}.zip"


def _compact_date(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.replace("-", "")
    if len(stripped) != 8 or not stripped.isdigit():
        raise ValueError(f"invalid date: {value!r}")
    return stripped


def get_horse_runs(
    raw_root: Path,
    horse_id: str,
    *,
    before: str | None = None,
    limit: int = 8,
    start_year: int | None = None,
    end_year: int | None = None,
    strict_archives: bool = False,
) -> list[HorseRun]:
    """Return newest SED runs for one horse across annual Raw archives.

    ``before`` is exclusive. Years and daily members are scanned newest first,
    and scanning stops as soon as ``limit`` matching runs have been found.
    """
    normalized_horse_id = horse_id.strip()
    if not normalized_horse_id:
        raise ValueError("horse_id is required")
    if limit <= 0:
        raise ValueError("limit must be positive")

    before_compact = _compact_date(before)
    if end_year is None:
        if before_compact is not None:
            end_year = int(before_compact[:4])
        else:
            raise ValueError("end_year is required when before is omitted")
    if start_year is None:
        start_year = max(2000, end_year - 15)
    if start_year > end_year:
        raise ValueError("start_year must be <= end_year")

    parser = Parser()
    found: list[HorseRun] = []

    for year in range(end_year, start_year - 1, -1):
        archive = annual_archive(raw_root, "SED", year)
        if not archive.is_file():
            if strict_archives:
                raise FileNotFoundError(archive)
            continue

        for member, record in iter_archive_records(
            archive,
            "SED",
            reverse_members=True,
        ):
            # Filter on fixed-position identity/date before parsing the whole row.
            if raw_field(record, 11, 8) != normalized_horse_id:
                continue
            date_raw = raw_field(record, 19, 8)
            if before_compact is not None and date_raw >= before_compact:
                continue

            found.append(
                HorseRun(
                    source=SourceRef(
                        archive=str(archive),
                        member=member,
                        year=year,
                    ),
                    data=parser.sed(record),
                )
            )
            if len(found) >= limit:
                return found

    found.sort(
        key=lambda item: item.data.get("date_raw") or "",
        reverse=True,
    )
    return found[:limit]


def history_dates(runs: Iterable[HorseRun]) -> list[str | None]:
    """Return ISO dates for diagnostics/tests."""
    return [ymd(run.data.get("date_raw")) for run in runs]
