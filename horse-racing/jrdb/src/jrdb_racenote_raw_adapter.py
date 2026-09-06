#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RaceNote historical Raw reconstruction on the common JRDB reader.

This module owns no fixed-width offsets. It reconstructs the PACI-equivalent
BAC/KYI/CHA/CYB + ZED/ZKB input expected by RaceNote from annual Raw archives.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Callable, Iterable

from jrdb_raw import Parser, iter_archive_records, race_key, result_key

_COMMON = Parser()
BASE_KINDS = ("BAC", "KYI", "CHA", "CYB")
HISTORY_KINDS = ("SED", "SKB")


def annual_zip(raw_dir: Path, kind: str, year: int) -> Path:
    return raw_dir / kind / f"{kind}_{year}.zip"


def _race_key_strings(values: Iterable[bytes | str]) -> set[str]:
    output: set[str] = set()
    for value in values:
        if isinstance(value, bytes):
            output.add(value.decode("ascii"))
        else:
            output.add(str(value))
    return output


def previous_result_keys(kyi_record: bytes) -> set[str]:
    """Return explicit nonzero KYI previous-result keys through Common Parser."""
    parsed = _COMMON.kyi(kyi_record)
    output: set[str] = set()
    previous = parsed.get("previous")
    if not isinstance(previous, list):
        return output
    for item in previous:
        if not isinstance(item, dict):
            continue
        key = str(item.get("result_key") or "")
        if key and key != "0" * 16:
            output.add(key)
    return output


def previous_result_year(key: str) -> int:
    """Return YYYY embedded in a JRDB 16-character result key."""
    return int(key[-8:-4])


def write_fixed_member(rows: list[bytes]) -> bytes:
    if not rows:
        return b""
    return b"\r\n".join(rows) + b"\r\n"


def build_paci_equivalent(
    raw_dir: Path,
    target_year: int,
    short_date: str,
    race_keys: Iterable[bytes | str],
    destination: Path,
    ensure_history: Callable[[int, list[str]], None],
) -> dict[str, object]:
    """Build one RaceNote historical PACI-equivalent ZIP from annual Raw."""
    targets = _race_key_strings(race_keys)
    selected: dict[str, list[bytes]] = {kind: [] for kind in BASE_KINDS}

    for kind in BASE_KINDS:
        for _member, record in iter_archive_records(annual_zip(raw_dir, kind, target_year), kind):
            if race_key(record) in targets:
                selected[kind].append(record)

    if not selected["BAC"] or not selected["KYI"]:
        raise ValueError("Historical reconstruction found no BAC/KYI records")

    previous_keys: set[str] = set()
    for record in selected["KYI"]:
        previous_keys.update(previous_result_keys(record))

    previous_years: set[int] = set()
    for key in previous_keys:
        try:
            previous_years.add(previous_result_year(key))
        except ValueError:
            continue
    if previous_keys and not previous_years:
        raise ValueError("Could not resolve previous-result years from KYI keys")

    for year in sorted(previous_years):
        ensure_history(year, list(HISTORY_KINDS))

    zed: list[bytes] = []
    zkb: list[bytes] = []
    for year in sorted(previous_years):
        for _member, record in iter_archive_records(annual_zip(raw_dir, "SED", year), "SED"):
            if result_key(record) in previous_keys:
                zed.append(record)
        for _member, record in iter_archive_records(annual_zip(raw_dir, "SKB", year), "SKB"):
            if result_key(record) in previous_keys:
                zkb.append(record)

    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for kind in BASE_KINDS:
            archive.writestr(f"{kind}{short_date}.txt", write_fixed_member(selected[kind]))
        archive.writestr(f"ZED{short_date}.txt", write_fixed_member(zed))
        archive.writestr(f"ZKB{short_date}.txt", write_fixed_member(zkb))

    return {
        "race_key_count": len(targets),
        "record_counts": {
            **{kind: len(rows) for kind, rows in selected.items()},
            "ZED": len(zed),
            "ZKB": len(zkb),
        },
        "previous_result_key_count": len(previous_keys),
        "previous_result_years": sorted(previous_years),
    }
