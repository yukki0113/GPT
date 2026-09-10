#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Eval Phase2 previous-run features from pre-race JRDB PACI.

Current BAC/KYI identify the target runner. KYI previous-result key 1 is joined
exactly to PACI ZED's result_key. ZED is historical result data already supplied
before the current race; current-race SED is never read.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
JRDB_SRC = ROOT / "jrdb" / "src"
if str(JRDB_SRC) not in sys.path:
    sys.path.insert(0, str(JRDB_SRC))

from jrdb_raw import (
    VERSION as JRDB_RAW_VERSION,
    Parser,
    ReaderAudit,
    canonical_members,
    read_fixed_records,
    ymd,
)
from racenote_jrdb import SURFACE, TRACK_CONDITION


VERSION = "0.1.2"
ZERO_RESULT_KEY = "0" * 16

OUTPUT_COLUMNS = (
    "race_date",
    "race_key",
    "horse_no",
    "race_horse_key",
    "current_distance_m",
    "current_surface_code",
    "current_surface_label",
    "current_race_class_code",
    "prev_result_key_1",
    "previous_lookup_status",
    "previous_race_date",
    "previous_race_key",
    "previous_distance_m",
    "previous_surface_code",
    "previous_surface_label",
    "previous_track_condition_code",
    "previous_track_condition_label",
    "previous_race_class_code",
    "distance_change_m",
    "surface_transition",
    "surface_changed",
    "source_availability_class",
    "source_file",
    "previous_source_member",
    "jrdb_raw_version",
)


class Phase2PreviousFeatureError(RuntimeError):
    """Raised when exact previous-run linkage is ambiguous or invalid."""


def text_or_none(value: object) -> str | None:
    """Normalize an optional parsed value to stripped text."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def int_or_none(value: object) -> int | None:
    """Normalize an optional integer-like parsed value."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def first_previous_result_key(parsed: dict[str, object]) -> str | None:
    """Return the raw KYI previous-result key 1 without guessing another run.

    JRDB's all-zero key is preserved as source provenance. Whether the horse has
    a usable previous run is expressed separately by ``previous_lookup_status``.
    """
    previous = parsed.get("previous")
    if not isinstance(previous, list) or not previous:
        return None
    item = previous[0]
    if not isinstance(item, dict):
        return None
    return text_or_none(item.get("result_key"))


def load_races(
    archive: zipfile.ZipFile,
    parser: Parser,
    audit: ReaderAudit,
) -> dict[str, dict[str, object]]:
    """Load current pre-race BAC conditions by race key."""
    members = canonical_members(archive, "BAC")
    if not members:
        raise Phase2PreviousFeatureError("PACI has no BAC member")

    races: dict[str, dict[str, object]] = {}
    for member in members:
        for raw in read_fixed_records(archive, member, "BAC", audit):
            parsed = parser.bac(raw)
            key = str(parsed.get("race_key_raw") or "")
            race_date = ymd(text_or_none(parsed.get("date_raw")))
            if not key or race_date is None:
                raise Phase2PreviousFeatureError(
                    f"invalid BAC race identity: member={member}"
                )
            row = {
                "race_date": race_date,
                "distance_m": int_or_none(parsed.get("distance_raw")),
                "surface_code": text_or_none(parsed.get("surface_code")),
                "race_class_code": text_or_none(parsed.get("race_class_code")),
            }
            existing = races.get(key)
            if existing is not None and existing != row:
                raise Phase2PreviousFeatureError(
                    f"conflicting BAC race row: {key}"
                )
            races[key] = row
    return races


def load_previous_results(
    archive: zipfile.ZipFile,
    parser: Parser,
    audit: ReaderAudit,
) -> dict[str, dict[str, object]]:
    """Load pre-race ZED rows by exact JRDB result key."""
    results: dict[str, dict[str, object]] = {}
    for member in canonical_members(archive, "ZED"):
        for raw in read_fixed_records(archive, member, "ZED", audit):
            parsed = parser.zed(raw)
            key = text_or_none(parsed.get("result_key"))
            if key is None:
                raise Phase2PreviousFeatureError(
                    f"ZED result_key is blank: member={member}"
                )
            row = dict(parsed)
            row["_source_member"] = Path(member).name
            if key in results:
                raise Phase2PreviousFeatureError(
                    f"duplicate ZED result_key: {key}"
                )
            results[key] = row
    return results


def transition_label(current_code: str | None, previous_code: str | None) -> str:
    """Return a readable surface transition without inferring quality."""
    if current_code is None or previous_code is None:
        return ""
    current = SURFACE.get(current_code, current_code)
    previous = SURFACE.get(previous_code, previous_code)
    return f"{previous}->{current}"


def build_features(paci_path: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Build exact previous-run conditions for every current KYI runner."""
    audit = ReaderAudit()
    parser = Parser(audit)
    output: list[dict[str, object]] = []
    seen: set[str] = set()
    status_counts: dict[str, int] = {}

    with zipfile.ZipFile(paci_path) as archive:
        races = load_races(archive, parser, audit)
        previous_results = load_previous_results(archive, parser, audit)
        kyi_members = canonical_members(archive, "KYI")
        if not kyi_members:
            raise Phase2PreviousFeatureError("PACI has no KYI member")

        for member in kyi_members:
            for raw in read_fixed_records(archive, member, "KYI", audit):
                parsed = parser.kyi(raw)
                race_key = str(parsed.get("race_key_raw") or "")
                race = races.get(race_key)
                if race is None:
                    raise Phase2PreviousFeatureError(
                        f"KYI race_key missing from BAC: {race_key}"
                    )

                horse_no = int_or_none(parsed.get("horse_no"))
                race_horse_key = str(parsed.get("race_horse_key") or "")
                if horse_no is None or not race_horse_key:
                    raise Phase2PreviousFeatureError(
                        f"invalid KYI runner identity: race_key={race_key}"
                    )
                if race_horse_key in seen:
                    raise Phase2PreviousFeatureError(
                        f"duplicate KYI race_horse_key: {race_horse_key}"
                    )
                seen.add(race_horse_key)

                prev_key = first_previous_result_key(parsed)
                previous: dict[str, object] | None = None
                if prev_key is None or prev_key == ZERO_RESULT_KEY:
                    status = "NO_PREVIOUS"
                else:
                    previous = previous_results.get(prev_key)
                    if previous is None:
                        status = "LINK_NOT_RESOLVED"
                    else:
                        previous_date = ymd(text_or_none(previous.get("date_raw")))
                        if previous_date is None:
                            raise Phase2PreviousFeatureError(
                                f"invalid ZED previous date: result_key={prev_key}"
                            )
                        if previous_date >= str(race["race_date"]):
                            raise Phase2PreviousFeatureError(
                                "previous run is not strictly prior: "
                                f"result_key={prev_key} previous={previous_date} "
                                f"current={race['race_date']}"
                            )
                        status = "RESOLVED"

                current_distance = int_or_none(race.get("distance_m"))
                current_surface = text_or_none(race.get("surface_code"))

                previous_date_value: str | None = None
                previous_distance: int | None = None
                previous_surface: str | None = None
                previous_track_condition: str | None = None
                previous_class: str | None = None
                previous_race_key: str | None = None
                source_member: str | None = None
                if previous is not None:
                    previous_date_value = ymd(text_or_none(previous.get("date_raw")))
                    previous_distance = int_or_none(previous.get("distance_m"))
                    previous_surface = text_or_none(previous.get("surface_code"))
                    previous_track_condition = text_or_none(
                        previous.get("track_condition_code")
                    )
                    previous_class = text_or_none(previous.get("race_class_code"))
                    previous_race_key = text_or_none(previous.get("race_key_raw"))
                    source_member = text_or_none(previous.get("_source_member"))

                distance_change: int | None = None
                if current_distance is not None and previous_distance is not None:
                    distance_change = current_distance - previous_distance

                surface_changed: int | None = None
                if current_surface is not None and previous_surface is not None:
                    if current_surface != previous_surface:
                        surface_changed = 1
                    else:
                        surface_changed = 0

                row: dict[str, object] = {
                    "race_date": race["race_date"],
                    "race_key": race_key,
                    "horse_no": horse_no,
                    "race_horse_key": race_horse_key,
                    "current_distance_m": current_distance,
                    "current_surface_code": current_surface,
                    "current_surface_label": SURFACE.get(current_surface or "", ""),
                    "current_race_class_code": race.get("race_class_code"),
                    "prev_result_key_1": prev_key,
                    "previous_lookup_status": status,
                    "previous_race_date": previous_date_value,
                    "previous_race_key": previous_race_key,
                    "previous_distance_m": previous_distance,
                    "previous_surface_code": previous_surface,
                    "previous_surface_label": SURFACE.get(previous_surface or "", ""),
                    "previous_track_condition_code": previous_track_condition,
                    "previous_track_condition_label": TRACK_CONDITION.get(
                        previous_track_condition or "", ""
                    ),
                    "previous_race_class_code": previous_class,
                    "distance_change_m": distance_change,
                    "surface_transition": transition_label(
                        current_surface, previous_surface
                    ),
                    "surface_changed": surface_changed,
                    "source_availability_class": "PRE_RACE_HISTORY",
                    "source_file": paci_path.name,
                    "previous_source_member": source_member,
                    "jrdb_raw_version": JRDB_RAW_VERSION,
                }
                output.append(row)
                status_counts[status] = status_counts.get(status, 0) + 1

    if audit.record_length_errors:
        raise Phase2PreviousFeatureError(
            "PACI fixed-record length error: "
            + str(dict(audit.record_length_errors))
        )

    output.sort(key=lambda row: (str(row["race_key"]), int(row["horse_no"])))
    summary: dict[str, object] = {
        "status": "success",
        "schema_version": VERSION,
        "jrdb_raw_version": JRDB_RAW_VERSION,
        "source_file": paci_path.name,
        "runner_rows": len(output),
        "zed_result_rows": len(previous_results),
        "previous_lookup_status_counts": dict(sorted(status_counts.items())),
        "source_availability_class": "PRE_RACE_HISTORY",
    }
    return output, summary


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write one-row-per-runner previous feature CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_audit(path: Path, audit: dict[str, object]) -> None:
    """Write audit JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_argument_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Build Eval Phase2 exact previous-run features from JRDB PACI."
    )
    parser.add_argument("--paci", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path)
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def main() -> int:
    """Run the previous-run feature adapter."""
    parser = build_argument_parser()
    args = parser.parse_args()
    try:
        rows, audit = build_features(args.paci)
        write_csv(args.output, rows)
        if args.audit_json is not None:
            write_audit(args.audit_json, audit)
        print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
        return 0
    except (
        Phase2PreviousFeatureError,
        FileNotFoundError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
