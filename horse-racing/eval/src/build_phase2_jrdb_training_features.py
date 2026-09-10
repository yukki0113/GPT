#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Eval Phase2 pre-race training features from JRDB CHA/CYB.

KYI is used only as the authoritative runner identity set. CHA/CYB are optional
per runner and are LEFT JOINed onto that set. Fixed-width parsing and established
field normalization remain owned by JRDB common adapters.
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

from jrdb_index_base_adapter import (
    parse_cha as parse_cha_adapted,
    parse_cyb as parse_cyb_adapted,
)
from jrdb_raw import (
    VERSION as JRDB_RAW_VERSION,
    Parser,
    ReaderAudit,
    canonical_members,
    read_fixed_records,
)


VERSION = "0.1.0"

OUTPUT_COLUMNS = (
    "race_key",
    "horse_no",
    "race_horse_key",
    "cha_status",
    "cha_training_date",
    "cha_weekday",
    "cha_workout_count",
    "cha_course_code",
    "cha_effort_code",
    "cha_chase_state_code",
    "cha_rider_type_code",
    "cha_furlong_count",
    "cha_first_segment_sec",
    "cha_middle_segment_sec",
    "cha_final_segment_sec",
    "cha_first_segment_index",
    "cha_middle_segment_index",
    "cha_final_segment_index",
    "cha_workout_index",
    "cha_pair_result_code",
    "cha_pair_effort_code",
    "cha_pair_age",
    "cha_pair_class_code",
    "cha_source_member",
    "cha_record_hash",
    "cyb_status",
    "cyb_training_type_code",
    "cyb_training_course_type_code",
    "cyb_used_slope",
    "cyb_used_wood",
    "cyb_used_dirt",
    "cyb_used_turf",
    "cyb_used_pool",
    "cyb_used_jump",
    "cyb_used_polytrack",
    "cyb_training_distance_code",
    "cyb_training_focus_code",
    "cyb_workout_index",
    "cyb_finish_index",
    "cyb_training_volume_code",
    "cyb_finish_change_code",
    "cyb_training_evaluation_code",
    "cyb_week_ago_workout_index",
    "cyb_week_ago_course_code",
    "cyb_source_member",
    "cyb_record_hash",
    "workout_index_relation",
    "source_availability_class",
    "source_file",
    "jrdb_raw_version",
)


class Phase2TrainingFeatureError(RuntimeError):
    """Raised when PACI training records are structurally ambiguous."""


def text_or_blank(value: object) -> str:
    """Normalize one optional field to stripped text or blank."""
    if value is None:
        return ""
    return str(value).strip()


def make_key(race_key: object, horse_no: object) -> str:
    """Build the canonical JRDB race-horse key from normalized parts."""
    race = text_or_blank(race_key)
    if not race:
        raise Phase2TrainingFeatureError("race_key is blank")
    if horse_no is None or horse_no == "":
        raise Phase2TrainingFeatureError(f"horse_no is blank: race_key={race}")
    try:
        number = int(horse_no)
    except (TypeError, ValueError) as exc:
        raise Phase2TrainingFeatureError(
            f"invalid horse_no: race_key={race} horse_no={horse_no!r}"
        ) from exc
    return race + str(number).zfill(2)


def load_runner_keys(
    archive: zipfile.ZipFile,
    audit: ReaderAudit,
) -> dict[str, dict[str, object]]:
    """Load the authoritative KYI runner identity set."""
    parser = Parser(audit)
    members = canonical_members(archive, "KYI")
    if not members:
        raise Phase2TrainingFeatureError("PACI has no KYI member")

    runners: dict[str, dict[str, object]] = {}
    for member in members:
        records = read_fixed_records(archive, member, "KYI", audit)
        for raw in records:
            parsed = parser.kyi(raw)
            race_key = text_or_blank(parsed.get("race_key_raw"))
            horse_no = parsed.get("horse_no")
            key = make_key(race_key, horse_no)
            if key in runners:
                raise Phase2TrainingFeatureError(
                    f"duplicate KYI race_horse_key: {key}"
                )
            runners[key] = {
                "race_key": race_key,
                "horse_no": int(horse_no),
                "race_horse_key": key,
            }
    return runners


def load_cha(
    archive: zipfile.ZipFile,
    audit: ReaderAudit,
) -> dict[str, dict[str, object]]:
    """Load optional CHA records through the established JRDB adapter."""
    rows: dict[str, dict[str, object]] = {}
    for member in canonical_members(archive, "CHA"):
        records = read_fixed_records(archive, member, "CHA", audit)
        for raw in records:
            adapted = parse_cha_adapted(raw, Path(member).name)
            key = make_key(adapted.get("race_key"), adapted.get("horse_no"))
            if key in rows:
                raise Phase2TrainingFeatureError(
                    f"duplicate CHA race_horse_key: {key}"
                )
            rows[key] = adapted
    return rows


def load_cyb(
    archive: zipfile.ZipFile,
    audit: ReaderAudit,
) -> dict[str, dict[str, object]]:
    """Load optional CYB records through the established JRDB adapter."""
    rows: dict[str, dict[str, object]] = {}
    for member in canonical_members(archive, "CYB"):
        records = read_fixed_records(archive, member, "CYB", audit)
        for raw in records:
            adapted = parse_cyb_adapted(raw, Path(member).name)
            key = make_key(adapted.get("race_key"), adapted.get("horse_no"))
            if key in rows:
                raise Phase2TrainingFeatureError(
                    f"duplicate CYB race_horse_key: {key}"
                )
            rows[key] = adapted
    return rows


def workout_index_relation(
    cha_index: object,
    cyb_index: object,
) -> str:
    """Describe CHA/CYB workout-index availability/equality without merging them."""
    if cha_index is None and cyb_index is None:
        return "BOTH_MISSING"
    if cha_index is None:
        return "CYB_ONLY"
    if cyb_index is None:
        return "CHA_ONLY"
    if cha_index == cyb_index:
        return "MATCH"
    return "MISMATCH"


def project_cha(row: dict[str, object] | None) -> dict[str, object]:
    """Project one optional CHA adapter row with an explicit prefix."""
    if row is None:
        return {
            "cha_status": "MISSING",
            "cha_training_date": None,
            "cha_weekday": None,
            "cha_workout_count": None,
            "cha_course_code": None,
            "cha_effort_code": None,
            "cha_chase_state_code": None,
            "cha_rider_type_code": None,
            "cha_furlong_count": None,
            "cha_first_segment_sec": None,
            "cha_middle_segment_sec": None,
            "cha_final_segment_sec": None,
            "cha_first_segment_index": None,
            "cha_middle_segment_index": None,
            "cha_final_segment_index": None,
            "cha_workout_index": None,
            "cha_pair_result_code": None,
            "cha_pair_effort_code": None,
            "cha_pair_age": None,
            "cha_pair_class_code": None,
            "cha_source_member": None,
            "cha_record_hash": None,
        }

    return {
        "cha_status": "MATCHED",
        "cha_training_date": row.get("training_date"),
        "cha_weekday": row.get("weekday"),
        "cha_workout_count": row.get("workout_count"),
        "cha_course_code": row.get("course_code"),
        "cha_effort_code": row.get("effort_code"),
        "cha_chase_state_code": row.get("chase_state_code"),
        "cha_rider_type_code": row.get("rider_type_code"),
        "cha_furlong_count": row.get("furlong_count"),
        "cha_first_segment_sec": row.get("first_segment_sec"),
        "cha_middle_segment_sec": row.get("middle_segment_sec"),
        "cha_final_segment_sec": row.get("final_segment_sec"),
        "cha_first_segment_index": row.get("jrdb_first_segment_index"),
        "cha_middle_segment_index": row.get("jrdb_middle_segment_index"),
        "cha_final_segment_index": row.get("jrdb_final_segment_index"),
        "cha_workout_index": row.get("jrdb_workout_index"),
        "cha_pair_result_code": row.get("pair_result_code"),
        "cha_pair_effort_code": row.get("pair_effort_code"),
        "cha_pair_age": row.get("pair_age"),
        "cha_pair_class_code": row.get("pair_class_code"),
        "cha_source_member": row.get("source_member"),
        "cha_record_hash": row.get("record_hash"),
    }


def project_cyb(row: dict[str, object] | None) -> dict[str, object]:
    """Project one optional CYB adapter row with an explicit prefix."""
    if row is None:
        return {
            "cyb_status": "MISSING",
            "cyb_training_type_code": None,
            "cyb_training_course_type_code": None,
            "cyb_used_slope": None,
            "cyb_used_wood": None,
            "cyb_used_dirt": None,
            "cyb_used_turf": None,
            "cyb_used_pool": None,
            "cyb_used_jump": None,
            "cyb_used_polytrack": None,
            "cyb_training_distance_code": None,
            "cyb_training_focus_code": None,
            "cyb_workout_index": None,
            "cyb_finish_index": None,
            "cyb_training_volume_code": None,
            "cyb_finish_change_code": None,
            "cyb_training_evaluation_code": None,
            "cyb_week_ago_workout_index": None,
            "cyb_week_ago_course_code": None,
            "cyb_source_member": None,
            "cyb_record_hash": None,
        }

    return {
        "cyb_status": "MATCHED",
        "cyb_training_type_code": row.get("training_type_code"),
        "cyb_training_course_type_code": row.get("training_course_type_code"),
        "cyb_used_slope": row.get("used_slope"),
        "cyb_used_wood": row.get("used_wood"),
        "cyb_used_dirt": row.get("used_dirt"),
        "cyb_used_turf": row.get("used_turf"),
        "cyb_used_pool": row.get("used_pool"),
        "cyb_used_jump": row.get("used_jump"),
        "cyb_used_polytrack": row.get("used_polytrack"),
        "cyb_training_distance_code": row.get("training_distance_code"),
        "cyb_training_focus_code": row.get("training_focus_code"),
        "cyb_workout_index": row.get("jrdb_workout_index"),
        "cyb_finish_index": row.get("finish_index"),
        "cyb_training_volume_code": row.get("training_volume_code"),
        "cyb_finish_change_code": row.get("finish_change_code"),
        "cyb_training_evaluation_code": row.get("training_evaluation_code"),
        "cyb_week_ago_workout_index": row.get("week_ago_workout_index"),
        "cyb_week_ago_course_code": row.get("week_ago_course_code"),
        "cyb_source_member": row.get("source_member"),
        "cyb_record_hash": row.get("record_hash"),
    }


def build_features(paci_path: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Build a one-row-per-KYI-runner CHA/CYB research feature table."""
    audit = ReaderAudit()
    with zipfile.ZipFile(paci_path) as archive:
        runners = load_runner_keys(archive, audit)
        cha_rows = load_cha(archive, audit)
        cyb_rows = load_cyb(archive, audit)

    if audit.record_length_errors:
        raise Phase2TrainingFeatureError(
            "PACI fixed-record length error: "
            + str(dict(audit.record_length_errors))
        )

    orphan_cha = sorted(set(cha_rows) - set(runners))
    orphan_cyb = sorted(set(cyb_rows) - set(runners))
    if orphan_cha or orphan_cyb:
        raise Phase2TrainingFeatureError(
            f"training rows without KYI runner: CHA={orphan_cha[:5]} CYB={orphan_cyb[:5]}"
        )

    output: list[dict[str, object]] = []
    relation_counts: dict[str, int] = {}
    cha_matched = 0
    cyb_matched = 0

    for key in sorted(runners):
        runner = runners[key]
        cha = project_cha(cha_rows.get(key))
        cyb = project_cyb(cyb_rows.get(key))

        if cha["cha_status"] == "MATCHED":
            cha_matched += 1
        if cyb["cyb_status"] == "MATCHED":
            cyb_matched += 1

        relation = workout_index_relation(
            cha.get("cha_workout_index"),
            cyb.get("cyb_workout_index"),
        )
        relation_counts[relation] = relation_counts.get(relation, 0) + 1

        row = {
            **runner,
            **cha,
            **cyb,
            "workout_index_relation": relation,
            "source_availability_class": "PRE_RACE",
            "source_file": paci_path.name,
            "jrdb_raw_version": JRDB_RAW_VERSION,
        }
        output.append(row)

    summary: dict[str, object] = {
        "status": "success",
        "schema_version": VERSION,
        "jrdb_raw_version": JRDB_RAW_VERSION,
        "source_file": paci_path.name,
        "runner_rows": len(output),
        "cha_matched_rows": cha_matched,
        "cha_missing_rows": len(output) - cha_matched,
        "cyb_matched_rows": cyb_matched,
        "cyb_missing_rows": len(output) - cyb_matched,
        "orphan_cha_rows": 0,
        "orphan_cyb_rows": 0,
        "workout_index_relation_counts": dict(sorted(relation_counts.items())),
        "source_availability_class": "PRE_RACE",
    }
    return output, summary


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write UTF-8 BOM training feature CSV."""
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
    """Create CLI parser."""
    parser = argparse.ArgumentParser(
        description="Build Eval Phase2 pre-race CHA/CYB features from JRDB PACI."
    )
    parser.add_argument("--paci", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path)
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def main() -> int:
    """Run the Phase2 CHA/CYB feature adapter."""
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
        Phase2TrainingFeatureError,
        FileNotFoundError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
