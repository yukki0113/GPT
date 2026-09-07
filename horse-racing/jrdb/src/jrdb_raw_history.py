#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-year JRDB Raw history access built on :mod:`jrdb_raw`.

Annual ZIP files remain the source data. The reader scans newest years and
members first and stops as soon as the requested runs are collected. Batch
lookup scans each SED archive only once for all requested horses, so RaceNote
and other consumers do not need one annual scan per runner or a canonical
SQLite dependency for ordinary history lookups.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jrdb_raw import Parser, iter_archive_records, raw_field, ymd

VERSION = "0.2.0"


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


def _year_range(
    before_compact: str | None,
    start_year: int | None,
    end_year: int | None,
) -> tuple[int, int]:
    if end_year is None:
        if before_compact is not None:
            end_year = int(before_compact[:4])
        else:
            raise ValueError("end_year is required when before is omitted")
    if start_year is None:
        start_year = max(2000, end_year - 15)
    if start_year > end_year:
        raise ValueError("start_year must be <= end_year")
    return start_year, end_year


def _normalize_horse_ids(horse_ids: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in horse_ids:
        horse_id = str(value).strip()
        if not horse_id:
            raise ValueError("horse_id must not be blank")
        if horse_id in seen:
            continue
        seen.add(horse_id)
        normalized.append(horse_id)
    if not normalized:
        raise ValueError("horse_ids is required")
    return normalized


def get_horses_runs(
    raw_root: Path,
    horse_ids: Iterable[str],
    *,
    before: str | None = None,
    limit_per_horse: int = 8,
    start_year: int | None = None,
    end_year: int | None = None,
    strict_archives: bool = False,
) -> dict[str, list[HorseRun]]:
    """Return newest SED runs for multiple horses in one cross-year scan.

    ``before`` is exclusive. Years and daily members are scanned newest first.
    Each annual SED archive is traversed once for the whole horse set. A horse is
    removed from the active filter as soon as ``limit_per_horse`` runs are found,
    and scanning stops entirely when all requested horses are satisfied.
    """
    normalized_ids = _normalize_horse_ids(horse_ids)
    if limit_per_horse <= 0:
        raise ValueError("limit_per_horse must be positive")

    before_compact = _compact_date(before)
    start_year, end_year = _year_range(before_compact, start_year, end_year)

    parser = Parser()
    found: dict[str, list[HorseRun]] = {
        horse_id: [] for horse_id in normalized_ids
    }
    remaining = set(normalized_ids)

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
            # Filter identity/date before parsing the complete fixed-width row.
            horse_id = raw_field(record, 11, 8)
            if horse_id not in remaining:
                continue
            date_raw = raw_field(record, 19, 8)
            if before_compact is not None and date_raw >= before_compact:
                continue

            found[horse_id].append(
                HorseRun(
                    source=SourceRef(
                        archive=str(archive),
                        member=member,
                        year=year,
                    ),
                    data=parser.sed(record),
                )
            )
            if len(found[horse_id]) >= limit_per_horse:
                remaining.remove(horse_id)
                if not remaining:
                    return _finalize_runs(found, limit_per_horse)

    return _finalize_runs(found, limit_per_horse)


def _finalize_runs(
    runs_by_horse: dict[str, list[HorseRun]],
    limit_per_horse: int,
) -> dict[str, list[HorseRun]]:
    result: dict[str, list[HorseRun]] = {}
    for horse_id, runs in runs_by_horse.items():
        ordered = sorted(
            runs,
            key=lambda item: item.data.get("date_raw") or "",
            reverse=True,
        )
        result[horse_id] = ordered[:limit_per_horse]
    return result


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

    This compatibility API delegates to :func:`get_horses_runs`, keeping one
    implementation of the cross-year scan semantics.
    """
    normalized_horse_id = horse_id.strip()
    if not normalized_horse_id:
        raise ValueError("horse_id is required")
    result = get_horses_runs(
        raw_root,
        [normalized_horse_id],
        before=before,
        limit_per_horse=limit,
        start_year=start_year,
        end_year=end_year,
        strict_archives=strict_archives,
    )
    return result[normalized_horse_id]


def history_dates(runs: Iterable[HorseRun]) -> list[str | None]:
    """Return ISO dates for diagnostics/tests."""
    return [ymd(run.data.get("date_raw")) for run in runs]
