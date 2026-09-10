#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build leakage-safe Eval Phase2 features from JRDB pre-race KYI data.

The JRDB Common Raw Reader owns every fixed-width byte offset. This consumer
only projects already-parsed BAC/KYI values into an Eval Phase2 research CSV.
No SED, result, final odds, or other post-race source is read.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
JRDB_SRC = ROOT / "jrdb" / "src"
if str(JRDB_SRC) not in sys.path:
    sys.path.insert(0, str(JRDB_SRC))

from export_jrdb_eval_dataset import VENUE_LABELS
from jrdb_raw import (
    VERSION as JRDB_RAW_VERSION,
    Parser,
    ReaderAudit,
    canonical_members,
    race_key_parts,
    read_fixed_records,
)
from racenote_jrdb import (
    PACE,
    REST_REASON,
    RUNNING_STYLE,
    STABLE_EVAL,
    THREE_LEVEL,
    TRAINING_ARROW,
)


VERSION = "0.2.0"
ZERO_RESULT_KEY = "0" * 16

OUTPUT_COLUMNS = (
    "race_date",
    "venue",
    "venue_code",
    "race_no",
    "horse_no",
    "race_key",
    "race_horse_key",
    "horse_name",
    "frame_no",
    "running_style_code",
    "running_style_label",
    "training_index",
    "training_arrow_code",
    "training_arrow_label",
    "stable_index",
    "stable_evaluation_code",
    "stable_evaluation_label",
    "heavy_track_fit_code",
    "heavy_track_fit_label",
    "turf_fit_code",
    "turf_fit_label",
    "dirt_fit_code",
    "dirt_fit_label",
    "forecast_pace_code",
    "forecast_pace_label",
    "expected_front_index",
    "expected_pace_index",
    "expected_late_index",
    "expected_position_index",
    "expected_front_rank",
    "expected_pace_rank",
    "expected_late_rank",
    "expected_position_rank",
    "start_index",
    "late_break_rate",
    "prev_result_key_1",
    "prev_race_key_1",
    "previous_race_date",
    "layoff_days",
    "layoff_status",
    "rotation_interval",
    "rest_reason_code",
    "rest_reason_label",
    "stable_run_no",
    "stable_entry_date_raw",
    "stable_entry_date",
    "stable_days_before",
    "body_weight_pre_kg",
    "body_weight_change_pre_kg",
    "source_availability_class",
    "source_file",
    "source_member",
    "jrdb_raw_version",
)


class Phase2FeatureError(RuntimeError):
    """Raised when a PACI input is ambiguous or structurally invalid."""


def text_or_blank(value: object) -> str:
    """Normalize one optional parsed value to stripped text or blank."""
    if value is None:
        return ""
    return str(value).strip()


def normalize_yyyymmdd(value: object) -> str | None:
    """Return ISO date for a valid YYYYMMDD value, otherwise None."""
    text = text_or_blank(value)
    if not text:
        return None
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        parsed = dt.datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None
    return parsed.isoformat()


def first_previous(parsed: dict[str, object]) -> tuple[str, str]:
    """Return KYI previous-result/race keys for previous run 1."""
    previous = parsed.get("previous")
    if not isinstance(previous, list) or not previous:
        return "", ""

    item = previous[0]
    if not isinstance(item, dict):
        return "", ""

    result_key = text_or_blank(item.get("result_key"))
    race_key = text_or_blank(item.get("race_key_raw"))
    return result_key, race_key


def resolve_layoff(
    race_date: str,
    prev_result_key: str,
) -> tuple[str, int | None, str]:
    """Derive exact calendar layoff days from KYI previous result key.

    JRDB ``rotation_interval`` is a separate concept based on the number of
    Fridays between starts, so it is never substituted for calendar days.
    """
    key = prev_result_key.strip()
    if not key or key == ZERO_RESULT_KEY:
        return "", None, "DEBUT_NO_PREVIOUS"

    if len(key) != 16:
        return "", None, "INVALID_PREVIOUS_KEY"

    previous_date = normalize_yyyymmdd(key[-8:])
    if previous_date is None:
        return "", None, "INVALID_PREVIOUS_KEY"

    current = dt.date.fromisoformat(race_date)
    previous = dt.date.fromisoformat(previous_date)
    interval = (current - previous).days
    if interval <= 0:
        return previous_date, None, "NON_POSITIVE_INTERVAL"

    return previous_date, interval, "OK"


def normalized_stable_entry_date(value: object) -> tuple[str, bool]:
    """Normalize KYI stable-entry date while preserving invalid raw values."""
    raw = text_or_blank(value)
    if not raw:
        return "", False

    normalized = normalize_yyyymmdd(raw)
    if normalized is None:
        return "", True
    return normalized, False


def dict_value(source: object, key: str) -> object:
    """Safely return one field from a parsed nested dictionary."""
    if not isinstance(source, dict):
        return None
    return source.get(key)


def load_races(
    archive: zipfile.ZipFile,
    parser: Parser,
    audit: ReaderAudit,
) -> dict[str, dict[str, object]]:
    """Load BAC race identity required to resolve KYI rows."""
    members = canonical_members(archive, "BAC")
    if not members:
        raise Phase2FeatureError("PACI has no BAC member")

    races: dict[str, dict[str, object]] = {}
    for member in members:
        records = read_fixed_records(archive, member, "BAC", audit)
        for raw in records:
            parsed = parser.bac(raw)
            race_key = text_or_blank(parsed.get("race_key_raw"))
            race_date = normalize_yyyymmdd(parsed.get("date_raw"))
            if not race_key or race_date is None:
                raise Phase2FeatureError(
                    f"invalid BAC race identity: member={member!r}"
                )

            parts = race_key_parts(race_key)
            venue_code = text_or_blank(parts.get("venue_code"))
            race_no_value = parts.get("race_no")
            if race_no_value is None:
                raise Phase2FeatureError(
                    f"invalid BAC race number: race_key={race_key}"
                )

            venue = VENUE_LABELS.get(venue_code)
            if venue is None:
                raise Phase2FeatureError(
                    f"unsupported JRA venue code: race_key={race_key} venue={venue_code}"
                )

            race = {
                "race_date": race_date,
                "venue": venue,
                "venue_code": venue_code,
                "race_no": int(race_no_value),
            }
            existing = races.get(race_key)
            if existing is not None and existing != race:
                raise Phase2FeatureError(
                    f"conflicting BAC race row: race_key={race_key}"
                )
            races[race_key] = race

    return races


def build_feature_row(
    parsed: dict[str, object],
    race: dict[str, object],
    source_file: str,
    source_member: str,
) -> tuple[dict[str, object], bool]:
    """Project one parsed KYI row into the Phase2 research feature contract."""
    horse_no = parsed.get("horse_no")
    if horse_no is None:
        raise Phase2FeatureError(
            f"KYI horse_no is blank: race_key={parsed.get('race_key_raw')}"
        )

    prev_result_key, prev_race_key = first_previous(parsed)
    previous_date, layoff_days, layoff_status = resolve_layoff(
        str(race["race_date"]),
        prev_result_key,
    )

    stable_entry_raw = text_or_blank(parsed.get("stable_entry_date_raw"))
    stable_entry_date, invalid_stable_date = normalized_stable_entry_date(
        stable_entry_raw
    )

    running_style_code = text_or_blank(parsed.get("running_style_code"))
    training_arrow_code = text_or_blank(parsed.get("training_arrow_code"))
    stable_evaluation_code = text_or_blank(parsed.get("stable_evaluation_code"))
    heavy_track_fit_code = text_or_blank(parsed.get("heavy_track_fit_code"))
    turf_fit_code = text_or_blank(parsed.get("turf_fit_code"))
    dirt_fit_code = text_or_blank(parsed.get("dirt_fit_code"))
    forecast_pace_code = text_or_blank(parsed.get("forecast_pace_code"))
    rest_reason_code = text_or_blank(parsed.get("rest_reason_code"))
    pace_indices = parsed.get("pace_indices")
    pace_ranks = parsed.get("pace_ranks")

    row: dict[str, object] = {
        "race_date": race["race_date"],
        "venue": race["venue"],
        "venue_code": race["venue_code"],
        "race_no": race["race_no"],
        "horse_no": int(horse_no),
        "race_key": text_or_blank(parsed.get("race_key_raw")),
        "race_horse_key": text_or_blank(parsed.get("race_horse_key")),
        "horse_name": text_or_blank(parsed.get("horse_name")),
        "frame_no": parsed.get("frame_no"),
        "running_style_code": running_style_code,
        "running_style_label": RUNNING_STYLE.get(running_style_code, ""),
        "training_index": parsed.get("training_index"),
        "training_arrow_code": training_arrow_code,
        "training_arrow_label": TRAINING_ARROW.get(training_arrow_code, ""),
        "stable_index": parsed.get("stable_index"),
        "stable_evaluation_code": stable_evaluation_code,
        "stable_evaluation_label": STABLE_EVAL.get(stable_evaluation_code, ""),
        "heavy_track_fit_code": heavy_track_fit_code,
        "heavy_track_fit_label": THREE_LEVEL.get(heavy_track_fit_code, ""),
        "turf_fit_code": turf_fit_code,
        "turf_fit_label": THREE_LEVEL.get(turf_fit_code, ""),
        "dirt_fit_code": dirt_fit_code,
        "dirt_fit_label": THREE_LEVEL.get(dirt_fit_code, ""),
        "forecast_pace_code": forecast_pace_code,
        "forecast_pace_label": PACE.get(forecast_pace_code, ""),
        "expected_front_index": dict_value(pace_indices, "front"),
        "expected_pace_index": dict_value(pace_indices, "pace"),
        "expected_late_index": dict_value(pace_indices, "late"),
        "expected_position_index": dict_value(pace_indices, "position"),
        "expected_front_rank": dict_value(pace_ranks, "front"),
        "expected_pace_rank": dict_value(pace_ranks, "pace"),
        "expected_late_rank": dict_value(pace_ranks, "late"),
        "expected_position_rank": dict_value(pace_ranks, "position"),
        "start_index": parsed.get("start_index"),
        "late_break_rate": parsed.get("late_break_rate"),
        "prev_result_key_1": prev_result_key,
        "prev_race_key_1": prev_race_key,
        "previous_race_date": previous_date,
        "layoff_days": layoff_days,
        "layoff_status": layoff_status,
        "rotation_interval": parsed.get("rotation_interval"),
        "rest_reason_code": rest_reason_code,
        "rest_reason_label": REST_REASON.get(rest_reason_code, ""),
        "stable_run_no": parsed.get("stable_run_no"),
        "stable_entry_date_raw": stable_entry_raw,
        "stable_entry_date": stable_entry_date,
        "stable_days_before": parsed.get("stable_days_before"),
        "body_weight_pre_kg": parsed.get("body_weight_pre_kg"),
        "body_weight_change_pre_kg": parsed.get("body_weight_change_pre_kg"),
        "source_availability_class": "PRE_RACE",
        "source_file": source_file,
        "source_member": source_member,
        "jrdb_raw_version": JRDB_RAW_VERSION,
    }
    return row, invalid_stable_date


def build_features(paci_path: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Build all Phase2 KYI features from one pre-race PACI archive."""
    audit = ReaderAudit()
    parser = Parser(audit)
    output: list[dict[str, object]] = []
    seen: set[str] = set()
    layoff_status_counts: dict[str, int] = {}
    invalid_stable_entry_dates = 0

    with zipfile.ZipFile(paci_path) as archive:
        races = load_races(archive, parser, audit)
        members = canonical_members(archive, "KYI")
        if not members:
            raise Phase2FeatureError("PACI has no KYI member")

        for member in members:
            records = read_fixed_records(archive, member, "KYI", audit)
            for raw in records:
                parsed = parser.kyi(raw)
                race_key = text_or_blank(parsed.get("race_key_raw"))
                race = races.get(race_key)
                if race is None:
                    raise Phase2FeatureError(
                        f"KYI race_key missing from BAC: {race_key}"
                    )

                row, invalid_stable_date = build_feature_row(
                    parsed,
                    race,
                    paci_path.name,
                    Path(member).name,
                )
                identity = str(row["race_horse_key"])
                if not identity:
                    raise Phase2FeatureError(
                        f"KYI race_horse_key is blank: race_key={race_key}"
                    )
                if identity in seen:
                    raise Phase2FeatureError(
                        f"duplicate KYI race_horse_key: {identity}"
                    )
                seen.add(identity)
                output.append(row)

                status = str(row["layoff_status"])
                layoff_status_counts[status] = layoff_status_counts.get(status, 0) + 1
                if invalid_stable_date:
                    invalid_stable_entry_dates += 1

    if audit.record_length_errors:
        raise Phase2FeatureError(
            "PACI fixed-record length error: "
            + str(dict(audit.record_length_errors))
        )

    output.sort(
        key=lambda row: (
            str(row["race_key"]),
            int(row["horse_no"]),
        )
    )

    summary: dict[str, object] = {
        "status": "success",
        "schema_version": VERSION,
        "jrdb_raw_version": JRDB_RAW_VERSION,
        "source_file": paci_path.name,
        "race_count": len({str(row["race_key"]) for row in output}),
        "runner_rows": len(output),
        "duplicate_race_horse_keys": 0,
        "invalid_stable_entry_dates": invalid_stable_entry_dates,
        "layoff_status_counts": dict(sorted(layoff_status_counts.items())),
        "source_availability_class": "PRE_RACE",
    }
    return output, summary


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write a UTF-8 BOM Phase2 feature CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_audit(path: Path, audit: dict[str, object]) -> None:
    """Write audit JSON using stable UTF-8 formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Build Eval Phase2 pre-race KYI research features from JRDB PACI."
    )
    parser.add_argument("--paci", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path)
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def main() -> int:
    """Run the Phase2 KYI feature adapter."""
    parser = build_argument_parser()
    args = parser.parse_args()

    try:
        rows, audit = build_features(args.paci)
        write_csv(args.output, rows)
        if args.audit_json is not None:
            write_audit(args.audit_json, audit)
        print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
        return 0
    except (Phase2FeatureError, FileNotFoundError, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
