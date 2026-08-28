#!/usr/bin/env python3
"""Run the historical monthly RaceNote Archive builder with daily Raw repair.

The canonical <=2025 path uses annual BAC/KYI/CHA/CYB packs for efficiency.
Some annual snapshots can be structurally valid ZIP files while omitting one or
more target dates. In that case this thin compatibility layer replaces the
whole affected date with JRDB daily Raw packs before continuing the canonical
monthly build. Daily repair inputs are added to the source manifest so the
published shard keeps exact file-level provenance.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import build_racenote_archive_month_from_raw as base


REPAIR_PATHS: list[Path] = []
REPAIR_DATES: list[str] = []
ORIGINAL_SOURCE_MANIFEST_ROWS = base.source_manifest_rows


def daily_zip(raw_dir: Path, kind: str, race_date: str) -> Path:
    """Return the cache path used by fetch_jrdb_history.py for daily Raw."""
    compact = race_date.replace("-", "")
    return raw_dir / kind / f"{kind}{compact[2:]}.zip"


def ensure_daily_raw(raw_dir: Path, race_date: str) -> list[Path]:
    """Fetch and validate the four target-race daily Raw packs."""
    paths = [daily_zip(raw_dir, kind, race_date) for kind in base.TARGET_KINDS]
    missing = [
        kind
        for kind, path in zip(base.TARGET_KINDS, paths)
        if not base.zip_is_valid(path, kind)
    ]
    if missing:
        if "--fetch-missing" not in sys.argv:
            raise base.MonthBuildError(
                f"Annual Raw is incomplete for {race_date}; daily repair requires --fetch-missing"
            )
        command = [
            sys.executable,
            str(base.FETCH_HISTORY),
            "--date",
            race_date.replace("-", ""),
            "--kinds",
            *missing,
            "--output-dir",
            str(raw_dir.resolve()),
        ]
        if "--force-fetch" in sys.argv:
            command.append("--force")
        subprocess.run(command, check=True)

    still_missing = [
        kind
        for kind, path in zip(base.TARGET_KINDS, paths)
        if not base.zip_is_valid(path, kind)
    ]
    if still_missing:
        raise base.MonthBuildError(
            f"Missing/invalid daily Raw repair for {race_date}: {still_missing}"
        )
    return paths


def counts_complete(counts: dict[str, int]) -> bool:
    """Return whether one race has the complete target base components."""
    return (
        counts["BAC"] == 1
        and counts["KYI"] > 0
        and counts["CHA"] == counts["KYI"]
        and counts["CYB"] == counts["KYI"]
    )


def completeness_errors(
    index: base.MonthIndex,
    counts_by_race: dict[str, dict[str, int]],
) -> list[str]:
    """Return the same fail-fast completeness diagnostics as the base builder."""
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
    return errors


def extract_target_base_records(
    raw_dir: Path,
    year: int,
    index: base.MonthIndex,
) -> tuple[
    dict[str, dict[str, list[bytes]]],
    dict[str, set[bytes]],
    dict[str, dict[str, int]],
]:
    """Read annual target rows and replace incomplete dates from daily Raw."""
    by_date: dict[str, dict[str, list[bytes]]] = {
        race_date: {kind: [] for kind in base.TARGET_KINDS}
        for race_date in index.by_date
    }
    prev_keys_by_date: dict[str, set[bytes]] = {
        race_date: set() for race_date in index.by_date
    }
    counts_by_race: dict[str, dict[str, int]] = {
        race.race_key: {kind: 0 for kind in base.TARGET_KINDS}
        for race in index.races
    }

    def add_records(kind: str, path: Path) -> None:
        for line in base.iter_records(path, kind):
            try:
                race_key = line[:8].decode("ascii")
            except UnicodeDecodeError:
                continue
            identity = index.by_race_key.get(race_key)
            if identity is None:
                continue
            by_date[identity.race_date][kind].append(line)
            counts_by_race[race_key][kind] += 1
            if kind == "KYI":
                prev_keys_by_date[identity.race_date].update(
                    base.previous_result_keys(line)
                )

    for kind in base.TARGET_KINDS:
        add_records(kind, base.annual_zip(raw_dir, kind, year))

    incomplete_dates = sorted(
        {
            race.race_date
            for race in index.races
            if not counts_complete(counts_by_race[race.race_key])
        }
    )
    for race_date in incomplete_dates:
        paths = ensure_daily_raw(raw_dir, race_date)

        # Do not mix generations from annual and daily packs for one race day.
        by_date[race_date] = {kind: [] for kind in base.TARGET_KINDS}
        prev_keys_by_date[race_date] = set()
        for race in index.by_date[race_date]:
            counts_by_race[race.race_key] = {
                kind: 0 for kind in base.TARGET_KINDS
            }
        for kind, path in zip(base.TARGET_KINDS, paths):
            add_records(kind, path)

        REPAIR_PATHS.extend(paths)
        REPAIR_DATES.append(race_date)
        print(
            f"[REPAIR] replaced target base date from daily Raw: {race_date}",
            file=sys.stderr,
        )

    errors = completeness_errors(index, counts_by_race)
    if errors:
        raise base.MonthBuildError(
            "Target Raw completeness check failed after daily repair: "
            + "; ".join(errors[:20])
        )
    return by_date, prev_keys_by_date, counts_by_race


def source_manifest_rows(
    target_paths: list[Path],
    history_paths: list[Path],
) -> list[dict]:
    """Add daily repair files to the canonical file-level provenance manifest."""
    rows = ORIGINAL_SOURCE_MANIFEST_ROWS(target_paths, history_paths)
    seen = {row["filename"] + "|" + row["role"] for row in rows}
    for path in REPAIR_PATHS:
        kind = path.name[:3].upper()
        key = path.name + f"|target_race_base_repair:{kind}"
        if key in seen:
            continue
        short_date = path.stem[-6:]
        rows.append(
            {
                "source_type": "DAILY_RAW",
                "source_period": datetime.strptime(short_date, "%y%m%d").date().isoformat(),
                "filename": path.name,
                "sha256": base.sha256_file(path),
                "role": f"target_race_base_repair:{kind}",
            }
        )
        seen.add(key)
    rows.sort(key=lambda row: (row["source_period"], row["filename"], row["role"]))
    return rows


def main() -> int:
    """Install the compatibility hooks and delegate to the canonical CLI."""
    base.extract_target_base_records = extract_target_base_records
    base.source_manifest_rows = source_manifest_rows
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
