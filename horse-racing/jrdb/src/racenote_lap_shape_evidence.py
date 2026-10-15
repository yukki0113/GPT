#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build neutral RaceNote lap-shape evidence from JRDB SED/SRB ZIPs.

This module deliberately does not score horses. SRB laps are race-level,
leader-based observations used only as historical context.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any, Iterable

from jrdb_raw import Parser, canonical_members, read_fixed_records
from jrdb_race_lap import normalize_race_laps

from jrdb_race_lap_shape import LOGIC_VERSION, shape_from_segments as _shape_from_segments

SCHEMA_VERSION = "RaceNote-Lap-Shape-Evidence-0.1"


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
