#!/usr/bin/env python3
"""Build leakage-safe current-runner facts for JRDB Edge matching from PACI."""
from __future__ import annotations

import argparse
import json
import sqlite3
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from jrdb_edge_canonical import derive_transition_features
from jrdb_raw import (
    Parser,
    ReaderAudit,
    canonical_members,
    race_key_parts,
    read_fixed_records,
    ymd,
)

VERSION = "0.1.0"
ANALYSIS_TABLE = "fact_entry_result_lite"
ANALYSIS_REQUIRED_COLUMNS = {
    "race_key", "race_date", "horse_no", "horse_id", "track_type", "distance", "frame_no"
}


class CurrentFactError(RuntimeError):
    """Current Edge fact input is malformed, ambiguous, or leakage-unsafe."""


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def validate_analysis(connection: sqlite3.Connection) -> None:
    """Validate the minimal Analysis Lite v1.2 history contract used here."""
    rows = connection.execute(f"PRAGMA table_info({ANALYSIS_TABLE})").fetchall()
    columns = {str(row[1]) for row in rows}
    missing = ANALYSIS_REQUIRED_COLUMNS - columns
    if missing:
        raise CurrentFactError(f"Analysis Lite is missing required column(s): {sorted(missing)}")


def lookup_previous_fact(
    connection: sqlite3.Connection | None,
    *,
    prev_race_key: str | None,
    horse_id: str | None,
    target_date: str,
) -> tuple[str, dict[str, Any] | None]:
    """Resolve KYI's exact prev-race link without falling back to a guessed prior run."""
    if not prev_race_key:
        return "NO_LINK", None
    if connection is None:
        return "NO_HISTORY_SOURCE", None
    if not horse_id:
        return "NO_HORSE_ID", None
    rows = connection.execute(
        f"""SELECT race_date,track_type,distance,frame_no
            FROM {ANALYSIS_TABLE}
            WHERE race_key=? AND horse_id=?
            ORDER BY horse_no
            LIMIT 2""",
        (prev_race_key, horse_id),
    ).fetchall()
    if not rows:
        return "LINK_NOT_RESOLVED", None
    if len(rows) > 1:
        raise CurrentFactError(
            f"ambiguous Analysis previous link: race_key={prev_race_key} horse_id={horse_id}"
        )
    row = rows[0]
    previous_date = _text(row[0])
    if previous_date is None or previous_date >= target_date:
        raise CurrentFactError(
            f"previous race is not strictly prior: {prev_race_key} {previous_date!r} >= {target_date}"
        )
    return "RESOLVED", {
        "race_date": previous_date,
        "surface_code": _text(row[1]),
        "distance_m": _int(row[2]),
        "frame_no": _int(row[3]),
    }


def select_profile_asof(
    profiles: list[Mapping[str, Any]], target_date: str
) -> tuple[str, Mapping[str, Any] | None]:
    """Select the newest PACI UKC profile that is not later than the race date."""
    usable: list[tuple[str, Mapping[str, Any]]] = []
    undated: list[Mapping[str, Any]] = []
    for profile in profiles:
        raw_date = _text(profile.get("data_date"))
        if raw_date is None:
            undated.append(profile)
            continue
        iso = ymd(raw_date)
        if iso is None:
            raise CurrentFactError(f"invalid UKC data_date: {raw_date!r}")
        if iso <= target_date:
            usable.append((iso, profile))
    if usable:
        usable.sort(key=lambda item: item[0])
        return "MATCHED", usable[-1][1]
    if undated:
        # The enclosing PACI is itself a pre-race source. Undated UKC may be used,
        # while a positively future-dated profile is never used.
        return "MATCHED_UNDATED", undated[-1]
    return "MISSING_ASOF", None


def build_runner_fact(
    race: Mapping[str, Any],
    entry: Mapping[str, Any],
    profile: Mapping[str, Any] | None,
    previous: Mapping[str, Any] | None,
    *,
    profile_status: str,
    previous_status: str,
) -> dict[str, Any]:
    """Project parsed pre-race inputs into the canonical Matcher fact contract."""
    features = derive_transition_features(
        current_distance=race.get("distance_m"),
        current_surface_code=race.get("surface_code"),
        current_frame_no=entry.get("frame_no"),
        previous_distance=previous.get("distance_m") if previous else None,
        previous_surface_code=previous.get("surface_code") if previous else None,
        previous_frame_no=previous.get("frame_no") if previous else None,
    )
    profile = profile or {}
    return {
        "race_date": race["race_date"],
        "race_key": race["race_key"],
        "race_horse_key": entry["race_horse_key"],
        "venue_code": race["venue_code"],
        "race_no": race["race_no"],
        "horse_no": entry["horse_no"],
        "horse_id": entry.get("horse_id"),
        "horse_name": entry.get("horse_name"),
        "distance_m": race.get("distance_m"),
        "surface_code": race.get("surface_code"),
        "turn_code": race.get("turn_code"),
        "frame_no": entry.get("frame_no"),
        "frame_zone": features["frame_zone"],
        "sire_name": profile.get("sire_name"),
        "sire_line_code": profile.get("sire_line_code"),
        "broodmare_sire_name": profile.get("broodmare_sire_name"),
        "broodmare_sire_line_code": profile.get("broodmare_sire_line_code"),
        "profile_asof_date": ymd(_text(profile.get("data_date"))) if profile.get("data_date") else None,
        "jockey_code": entry.get("jockey_code"),
        "trainer_code": entry.get("trainer_code"),
        "prev1_race_key": entry.get("prev1_race_key"),
        "previous_lookup_status": previous_status,
        "previous_race_date": previous.get("race_date") if previous else None,
        "previous_distance_m": previous.get("distance_m") if previous else None,
        "previous_surface_code": previous.get("surface_code") if previous else None,
        "previous_frame_no": previous.get("frame_no") if previous else None,
        "profile_status": profile_status,
        "distance_change_m": features["distance_change_m"],
        "distance_change_bucket": features["distance_change_bucket"],
        "surface_transition": features["surface_transition"],
        "frame_transition": features["frame_transition"],
        "source_availability_class": "PRE_RACE",
    }


def _records(
    archive: zipfile.ZipFile, kind: str, audit: ReaderAudit, *, required: bool
) -> list[bytes]:
    members = canonical_members(archive, kind)
    if required and not members:
        raise CurrentFactError(f"PACI has no {kind} member")
    rows: list[bytes] = []
    for member in members:
        rows.extend(read_fixed_records(archive, member, kind, audit))
    return rows


def build_current_facts(
    paci_path: str | Path, analysis_db: str | Path | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse PACI and optionally enrich exact prev1 facts from Analysis Lite."""
    audit = ReaderAudit()
    parser = Parser(audit)
    races: dict[str, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    profiles: dict[str, list[dict[str, Any]]] = {}

    with zipfile.ZipFile(paci_path) as archive:
        for raw in _records(archive, "BAC", audit, required=True):
            parsed = parser.bac(raw)
            key = str(parsed["race_key_raw"])
            race_date = ymd(_text(parsed.get("date_raw")))
            if race_date is None:
                raise CurrentFactError(f"invalid BAC race date: race_key={key}")
            parts = race_key_parts(key)
            race = {
                "race_key": key,
                "race_date": race_date,
                "venue_code": parts["venue_code"],
                "race_no": parts["race_no"],
                "distance_m": _int(parsed.get("distance_raw")),
                "surface_code": _text(parsed.get("surface_code")),
                "turn_code": _text(parsed.get("turn_code")),
            }
            if key in races and races[key] != race:
                raise CurrentFactError(f"conflicting BAC race row: {key}")
            races[key] = race

        for raw in _records(archive, "UKC", audit, required=False):
            parsed = parser.ukc(raw)
            horse_id = _text(parsed.get("horse_id"))
            if horse_id:
                profiles.setdefault(horse_id, []).append(parsed)

        for raw in _records(archive, "KYI", audit, required=True):
            parsed = parser.kyi(raw)
            race_key = str(parsed["race_key_raw"])
            if race_key not in races:
                raise CurrentFactError(f"KYI race_key missing from BAC: {race_key}")
            horse_no = _int(parsed.get("horse_no"))
            if horse_no is None:
                raise CurrentFactError(f"KYI horse_no is blank: {race_key}")
            previous_rows = parsed.get("previous")
            first_previous: Mapping[str, Any] = {}
            if isinstance(previous_rows, list) and previous_rows and isinstance(previous_rows[0], Mapping):
                first_previous = previous_rows[0]
            entries.append({
                "race_key": race_key,
                "race_horse_key": str(parsed["race_horse_key"]),
                "horse_no": horse_no,
                "horse_id": _text(parsed.get("blood_registration_no")),
                "horse_name": _text(parsed.get("horse_name")),
                "frame_no": _int(parsed.get("frame_no")),
                "jockey_code": _text(parsed.get("jockey_code")),
                "trainer_code": _text(parsed.get("trainer_code")),
                "prev1_race_key": _text(first_previous.get("race_key_raw")),
            })

    if audit.record_length_errors:
        raise CurrentFactError(f"PACI fixed-record length error: {dict(audit.record_length_errors)}")

    if analysis_db is not None and not Path(analysis_db).is_file():
        raise CurrentFactError(f"Analysis Lite DB not found: {analysis_db}")
    analysis = sqlite3.connect(analysis_db) if analysis_db is not None else None
    if analysis is not None:
        validate_analysis(analysis)
    try:
        output: list[dict[str, Any]] = []
        counters: Counter[str] = Counter()
        seen: set[str] = set()
        for entry in entries:
            identity = str(entry["race_horse_key"])
            if identity in seen:
                raise CurrentFactError(f"duplicate KYI race_horse_key: {identity}")
            seen.add(identity)
            race = races[str(entry["race_key"])]
            profile_status, profile = select_profile_asof(
                profiles.get(str(entry.get("horse_id") or ""), []), str(race["race_date"])
            )
            previous_status, previous = lookup_previous_fact(
                analysis,
                prev_race_key=_text(entry.get("prev1_race_key")),
                horse_id=_text(entry.get("horse_id")),
                target_date=str(race["race_date"]),
            )
            counters[f"profile_{profile_status}"] += 1
            counters[f"previous_{previous_status}"] += 1
            output.append(build_runner_fact(
                race, entry, profile, previous,
                profile_status=profile_status,
                previous_status=previous_status,
            ))
        output.sort(key=lambda row: (str(row["race_key"]), int(row["horse_no"])))
        summary = {
            "status": "PASS",
            "builder_version": VERSION,
            "races": len(races),
            "runner_rows": len(output),
            **dict(sorted(counters.items())),
        }
        return output, summary
    finally:
        if analysis is not None:
            analysis.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paci", required=True)
    parser.add_argument("--analysis-db")
    parser.add_argument("--output-jsonl", required=True)
    args = parser.parse_args()
    rows, summary = build_current_facts(args.paci, args.analysis_db)
    with Path(args.output_jsonl).open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
