#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalize JRDB SRB race-level lap data into distance-aware segment rows.

SRB is bundled in the ordinary SED delivery.  The common Raw reader owns
fixed-width interpretation; this module joins SRB to SED only to obtain race
distance and expands leader-based lap slots into explicit distance intervals.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any, Iterable

from jrdb_raw import Parser, ReaderAudit, canonical_members, read_fixed_records


def _effective_lap_times(slots: list[float | None]) -> list[float]:
    """Return populated leading lap slots and reject internal gaps."""
    last = -1
    for index, value in enumerate(slots):
        if value is not None:
            last = index
    if last < 0:
        return []
    effective = slots[: last + 1]
    if any(value is None for value in effective):
        raise ValueError("SRB furlong times contain an internal blank slot")
    return [float(value) for value in effective if value is not None]


def segment_distances(distance_m: int, lap_count: int) -> list[int]:
    """Resolve the first partial segment plus following 200m segments.

    JRDB/JRA lap notation places the non-200m remainder in the first segment:
    e.g. 1700m => 100m + 8*200m, 1150m => 150m + 5*200m.
    """
    if distance_m <= 0:
        raise ValueError(f"distance_m must be positive: {distance_m}")
    if lap_count <= 0:
        raise ValueError(f"lap_count must be positive: {lap_count}")
    expected = (distance_m + 199) // 200
    if lap_count != expected:
        raise ValueError(
            f"lap count mismatch: distance_m={distance_m} "
            f"expected={expected} actual={lap_count}"
        )
    first = distance_m - 200 * (lap_count - 1)
    if not 1 <= first <= 200:
        raise ValueError(
            f"invalid first segment: distance_m={distance_m} "
            f"lap_count={lap_count} first={first}"
        )
    return [first] + [200] * (lap_count - 1)


def normalize_race_laps(
    parsed_srb: dict[str, Any],
    *,
    distance_m: int,
) -> list[dict[str, Any]]:
    """Expand one parsed SRB record into one row per measured segment."""
    lap_times = _effective_lap_times(parsed_srb["furlong_times_sec"])
    if not lap_times:
        return []

    distances = segment_distances(distance_m, len(lap_times))
    rows: list[dict[str, Any]] = []
    start_m = 0
    for index, (segment_m, lap_sec) in enumerate(
        zip(distances, lap_times, strict=True),
        start=1,
    ):
        end_m = start_m + segment_m
        rows.append(
            {
                "race_key_raw": parsed_srb["race_key_raw"],
                "segment_no": index,
                "start_m": start_m,
                "end_m": end_m,
                "segment_distance_m": segment_m,
                "lap_sec": lap_sec,
            }
        )
        start_m = end_m

    if start_m != distance_m:
        raise ValueError(
            f"distance sum mismatch: race_key={parsed_srb['race_key_raw']} "
            f"expected={distance_m} actual={start_m}"
        )
    return rows


def read_sed_zip_race_laps(
    archive: Path,
    *,
    audit: ReaderAudit | None = None,
) -> list[dict[str, Any]]:
    """Read an SED ZIP and return normalized SRB lap segment rows.

    SED is used only as the race-distance source.  SRB and SED are joined by
    the canonical 8-byte race key.  Races without SRB lap values (for example
    unsupported race types) are omitted rather than guessed.
    """
    parser = Parser(audit)
    rows: list[dict[str, Any]] = []

    with zipfile.ZipFile(archive) as zf:
        sed_members = canonical_members(zf, "SED")
        srb_members = canonical_members(zf, "SRB")
        if not sed_members:
            raise ValueError(f"SED member not found: {archive}")
        if not srb_members:
            raise ValueError(f"SRB member not found: {archive}")

        distances: dict[str, int] = {}
        sed_member_by_race: dict[str, str] = {}
        for member in sed_members:
            for record in read_fixed_records(zf, member, "SED", audit):
                parsed = parser.sed(record)
                key = parsed["race_key_raw"]
                distance = parsed["distance_m"]
                if distance is None:
                    continue
                distance_int = int(distance)
                previous = distances.get(key)
                if previous is not None and previous != distance_int:
                    raise ValueError(
                        f"inconsistent SED distance for {key}: "
                        f"{previous} vs {distance_int}"
                    )
                distances[key] = distance_int
                sed_member_by_race[key] = member

        for member in srb_members:
            for record in read_fixed_records(zf, member, "SRB", audit):
                parsed = parser.srb(record)
                key = parsed["race_key_raw"]
                if key not in distances:
                    raise ValueError(f"SED distance missing for SRB race: {key}")
                normalized = normalize_race_laps(
                    parsed,
                    distance_m=distances[key],
                )
                for row in normalized:
                    row.update(
                        {
                            "distance_m": distances[key],
                            "source_archive": archive.name,
                            "source_sed_member": sed_member_by_race[key],
                            "source_srb_member": member,
                        }
                    )
                rows.extend(normalized)

    return rows


def write_jsonl(rows: Iterable[dict[str, Any]], output: Path) -> None:
    with output.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract normalized race-level laps from a JRDB SED ZIP."
    )
    parser.add_argument("sed_zip", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        help="Write JSONL to this path; stdout is used when omitted.",
    )
    args = parser.parse_args()

    rows = read_sed_zip_race_laps(args.sed_zip)
    if args.output:
        write_jsonl(rows, args.output)
    else:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
