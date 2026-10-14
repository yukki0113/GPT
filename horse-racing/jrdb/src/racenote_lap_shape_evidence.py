#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build neutral RaceNote lap-shape evidence from JRDB SED/SRB ZIPs.

This module deliberately does not score horses. SRB laps are race-level,
leader-based observations used only as historical context.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import zipfile
from pathlib import Path
from typing import Any, Iterable

from jrdb_raw import Parser, canonical_members, read_fixed_records
from jrdb_race_lap import normalize_race_laps

SCHEMA_VERSION = "RaceNote-Lap-Shape-Evidence-0.1"
LOGIC_VERSION = "SRB-Neutral-RaceShape-v0.1"


def _round(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(float(value), digits)


def _race_metadata(zf: zipfile.ZipFile, archive: Path) -> dict[str, dict[str, Any]]:
    parser = Parser()
    result: dict[str, dict[str, Any]] = {}
    for member in canonical_members(zf, "SED"):
        for record in read_fixed_records(zf, member, "SED"):
            parsed = parser.sed(record)
            key = parsed["race_key_raw"]
            date_raw = str(parsed.get("date_raw") or "")
            date_iso = (
                f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}"
                if len(date_raw) == 8 and date_raw.isdigit()
                else ""
            )
            distance = parsed.get("distance_m")
            if distance is None:
                continue
            row = {
                "race_date": date_iso,
                "surface_code": str(parsed.get("surface_code") or ""),
                "distance_m": int(distance),
                "sed_member": member,
                "archive": archive.name,
            }
            previous = result.get(key)
            if previous is not None and previous != row:
                raise ValueError(f"inconsistent SED race metadata: {key}")
            result[key] = row
    return result


def _shape_from_segments(
    segments: list[dict[str, Any]],
    pace_up_remaining_furlongs: int | float | None,
    optional_context_available: bool,
) -> dict[str, Any]:
    full = [row for row in segments if row["segment_distance_m"] == 200]
    values = [float(row["lap_sec"]) for row in full]
    segment_nos = [int(row["segment_no"]) for row in full]

    early3f: float | None = None
    late3f: float | None = None
    early_late: float | None = None

    if len(segments) >= 3 and all(row["segment_distance_m"] == 200 for row in segments[:3]):
        early3f = sum(float(row["lap_sec"]) for row in segments[:3])
    if len(full) >= 3:
        late3f = sum(values[-3:])
    if early3f is not None and late3f is not None:
        early_late = late3f - early3f

    if values:
        fastest = min(values)
        fastest_index = values.index(fastest)
        fastest_segment_no = segment_nos[fastest_index]
        lap_std = statistics.pstdev(values) if len(values) >= 2 else 0.0
        lap_range = max(values) - min(values)
        last_vs_best = values[-1] - fastest
    else:
        fastest = None
        fastest_segment_no = None
        lap_std = None
        lap_range = None
        last_vs_best = None

    accel: list[float] = []
    decel: list[float] = []
    for previous, current in zip(values, values[1:]):
        delta = current - previous
        if delta < 0:
            accel.append(-delta)
        elif delta > 0:
            decel.append(delta)

    last3_slope: float | None = None
    if len(values) >= 3:
        y0, _, y2 = values[-3:]
        last3_slope = (y2 - y0) / 2.0

    pace_up = None
    if pace_up_remaining_furlongs is not None:
        try:
            pace_up = int(pace_up_remaining_furlongs)
        except (TypeError, ValueError):
            pace_up = None

    return {
        "coverage": {
            "status": "AVAILABLE" if segments else "NO_LAPS",
            "comparable_200m_lap_count": len(full),
            "early_late_delta_available": early_late is not None,
            "optional_srb_context_available": bool(optional_context_available),
        },
        "lap_shape": {
            "early3f_sec": _round(early3f, 1),
            "late3f_sec": _round(late3f, 1),
            "early_late_delta_sec": _round(early_late, 1),
            "lap_std_sec": _round(lap_std),
            "lap_range_sec": _round(lap_range, 1),
            "fastest_lap_sec": _round(fastest, 1),
            "fastest_segment_no": fastest_segment_no,
            "max_accel_sec": _round(max(accel) if accel else 0.0, 1) if values else None,
            "max_decel_sec": _round(max(decel) if decel else 0.0, 1) if values else None,
            "last_vs_best_sec": _round(last_vs_best, 1),
            "last3_slope_sec_per_segment": _round(last3_slope, 2),
            "pace_up_remaining_furlongs": pace_up,
        },
    }


def build_archive_evidence(archive: Path) -> list[dict[str, Any]]:
    parser = Parser()
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive) as zf:
        metadata = _race_metadata(zf, archive)
        srb_members = canonical_members(zf, "SRB")
        if not srb_members:
            raise ValueError(f"SRB member not found: {archive}")

        for member in srb_members:
            for record in read_fixed_records(zf, member, "SRB"):
                parsed = parser.srb(record)
                key = parsed["race_key_raw"]
                meta = metadata.get(key)
                if meta is None:
                    raise ValueError(f"SED metadata missing for SRB race: {key}")

                segments = normalize_race_laps(
                    parsed,
                    distance_m=meta["distance_m"],
                )

                optional = any(
                    value not in (None, "", [], {})
                    for value in (
                        parsed.get("pace_up_remaining_furlongs"),
                        parsed.get("race_comment"),
                        *(parsed.get("track_bias_raw") or {}).values(),
                    )
                )
                shape = _shape_from_segments(
                    segments,
                    parsed.get("pace_up_remaining_furlongs"),
                    optional,
                )
                rows.append(
                    {
                        "race_key_raw": key,
                        "race_date": meta["race_date"],
                        "surface_code": meta["surface_code"],
                        "distance_m": meta["distance_m"],
                        "lap_count": len(segments),
                        **shape,
                        "source": {
                            "archive": archive.name,
                            "sed_member": meta["sed_member"],
                            "srb_member": member,
                        },
                    }
                )
    return rows


def build_evidence(archives: Iterable[Path]) -> dict[str, Any]:
    races: list[dict[str, Any]] = []
    seen: set[str] = set()
    for archive in archives:
        for row in build_archive_evidence(archive):
            key = row["race_key_raw"]
            if key in seen:
                raise ValueError(f"duplicate race key across archives: {key}")
            seen.add(key)
            races.append(row)
    races.sort(key=lambda row: (row["race_date"], row["race_key_raw"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "logic_version": LOGIC_VERSION,
        "policy": {
            "source_kind": "JRDB_SRB",
            "leader_based": True,
            "individual_sectionals": False,
            "score_status": "NO_ADDITIVE_SCORE",
            "target_race_usage": "HISTORICAL_ONLY_AS_OF_EXCLUSIVE",
            "partial_first_segment_policy": "EXCLUDE_FROM_200M_COMPARABLE_METRICS",
        },
        "races": races,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("archives", nargs="+", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    evidence = build_evidence(args.archives)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status":"success","race_count":len(evidence["races"]),"output":str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
