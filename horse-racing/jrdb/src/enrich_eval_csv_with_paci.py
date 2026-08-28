#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enrich Eval OCR CSV with pre-race JRDB PACI data.

Input:
- Eval OCR CSV: date,venue,race_no,horse_no,eval
- JRDB PACIyymmdd.zip

Only pre-race PACI members are used. Analysis Lite, Core SQLite, SED and
post-race result data are not dependencies of this module.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import re
import sys
import zipfile

from export_jrdb_eval_dataset import add_labels
from export_jrdb_eval_race_conditions import (
    ExportError,
    SourceRecord,
    parse_bac_record_full,
)
from racenote_jrdb import (
    Audit,
    DISTANCE_FIT,
    IMPROVEMENT,
    Parser,
    RUNNING_STYLE,
    race_key,
    read_fixed_records,
)


VERSION = "1.0.0"

EVAL_REQUIRED_COLUMNS = (
    "date",
    "venue",
    "race_no",
    "horse_no",
    "eval",
)

OUTPUT_COLUMNS = (
    "date",
    "venue",
    "race_no",
    "horse_no",
    "eval",
    "venue_code",
    "join_status",
    "race_key",
    "horse_name",
    "frame_no",
    "jockey_name",
    "carried_weight",
    "running_style",
    "running_style_label",
    "distance_aptitude",
    "distance_aptitude_label",
    "uptrend",
    "uptrend_label",
    "training_index",
    "prev_result_key_1",
    "prev_race_key_1",
    "race_name",
    "race_type_code",
    "race_type_label",
    "race_condition_code",
    "class_label",
    "grade_code",
    "grade_label",
    "track_type",
    "track_label",
    "distance",
    "declared_field_size",
    "race_symbol_code",
    "sex_condition_label",
    "is_filly_only",
    "weight_condition_code",
    "weight_condition_label",
    "turn_direction_code",
    "turn_direction_label",
    "inner_outer_code",
    "inner_outer_label",
    "course_code",
    "course_label",
    "event_region_code",
)

VENUE_NAME_TO_CODE = {
    "札幌": "01",
    "函館": "02",
    "福島": "03",
    "新潟": "04",
    "東京": "05",
    "中山": "06",
    "中京": "07",
    "京都": "08",
    "阪神": "09",
    "小倉": "10",
}

BAC_MEMBER_RE = re.compile(r"^BAC\d{6}\.txt$", re.IGNORECASE)
KYI_MEMBER_RE = re.compile(r"^KYI\d{6}\.txt$", re.IGNORECASE)


class EnrichmentError(RuntimeError):
    """Eval/PACIの外部契約または結合監査に関するエラー。"""


def normalize_eval_date(value: str) -> str:
    """Eval日付を内部結合用YYYY-MM-DDへ正規化する。"""
    stripped = value.strip()
    formats = ("%Y-%m-%d", "%Y%m%d")

    for date_format in formats:
        try:
            parsed = dt.datetime.strptime(stripped, date_format).date()
            return parsed.isoformat()
        except ValueError:
            continue

    raise EnrichmentError(
        f"invalid Eval date {value!r}; expected YYYY-MM-DD or YYYYMMDD"
    )


def normalize_eval_venue(value: str) -> str:
    """Eval場名またはJRA場コードを2桁コードへ正規化する。"""
    stripped = value.strip()

    code = VENUE_NAME_TO_CODE.get(stripped)
    if code is not None:
        return code

    if stripped.isdigit():
        padded = stripped.zfill(2)
        if padded in VENUE_NAME_TO_CODE.values():
            return padded

    raise EnrichmentError(
        f"unsupported Eval venue {value!r}; expected JRA venue name or 01-10"
    )


def parse_positive_int(value: str, field_name: str, line_no: int) -> int:
    """CSVの正整数フィールドを検証して返す。"""
    stripped = value.strip()
    try:
        parsed = int(stripped)
    except ValueError as exc:
        raise EnrichmentError(
            f"invalid {field_name} at Eval CSV line {line_no}: {value!r}"
        ) from exc

    if parsed <= 0:
        raise EnrichmentError(
            f"invalid {field_name} at Eval CSV line {line_no}: {value!r}"
        )

    return parsed


def make_horse_key(
    race_date: str,
    venue_code: str,
    race_no: int,
    horse_no: int,
) -> tuple[str, str, int, int]:
    """Eval/PACI共通の馬単位結合キーを返す。"""
    return (race_date, venue_code, race_no, horse_no)


def make_race_key(
    horse_key: tuple[str, str, int, int],
) -> tuple[str, str, int]:
    """馬単位キーからレース単位キーを返す。"""
    return horse_key[0:3]


def load_eval_csv(
    path: Path,
) -> tuple[
    list[dict[str, object]],
    dict[tuple[str, str, int, int], dict[str, object]],
]:
    """Eval OCR CSVを読み込み、元5列と内部正規化キーを保持する。

    `horse_name_ocr` を含む旧6列CSVやその他の追加列は読み取り可能だが、
    正式出力には引き継がない。
    """
    rows: list[dict[str, object]] = []
    index: dict[tuple[str, str, int, int], dict[str, object]] = {}
    duplicate_keys: list[tuple[str, str, int, int]] = []

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise EnrichmentError("Eval CSV has no header")

        missing = []
        for column in EVAL_REQUIRED_COLUMNS:
            if column not in reader.fieldnames:
                missing.append(column)

        if missing:
            raise EnrichmentError(
                "Eval CSV missing required columns: " + ", ".join(missing)
            )

        for line_no, input_row in enumerate(reader, start=2):
            date_raw = str(input_row.get("date", "")).strip()
            venue_raw = str(input_row.get("venue", "")).strip()
            race_no_raw = str(input_row.get("race_no", "")).strip()
            horse_no_raw = str(input_row.get("horse_no", "")).strip()
            eval_raw = str(input_row.get("eval", "")).strip()

            normalized_date = normalize_eval_date(date_raw)
            venue_code = normalize_eval_venue(venue_raw)
            race_no = parse_positive_int(race_no_raw, "race_no", line_no)
            horse_no = parse_positive_int(horse_no_raw, "horse_no", line_no)

            key = make_horse_key(
                normalized_date,
                venue_code,
                race_no,
                horse_no,
            )

            row: dict[str, object] = {
                "date": date_raw,
                "venue": venue_raw,
                "race_no": race_no,
                "horse_no": horse_no,
                "eval": eval_raw,
                "_normalized_date": normalized_date,
                "_venue_code": venue_code,
                "_key": key,
            }

            if key in index:
                duplicate_keys.append(key)
            else:
                index[key] = row

            rows.append(row)

    if duplicate_keys:
        unique_duplicates = sorted(set(duplicate_keys))
        raise EnrichmentError(
            "duplicate Eval join key(s): "
            + ", ".join(str(key) for key in unique_duplicates)
        )

    return rows, index


def find_single_member(
    archive: zipfile.ZipFile,
    pattern: re.Pattern[str],
    kind: str,
) -> str:
    """PACI内から対象TYPEの単一メンバーを厳密に選ぶ。"""
    matches: list[str] = []

    for member_name in archive.namelist():
        base_name = Path(member_name).name
        if pattern.fullmatch(base_name):
            matches.append(member_name)

    matches.sort()

    if not matches:
        raise EnrichmentError(f"PACI has no {kind} member")
    if len(matches) > 1:
        raise EnrichmentError(
            f"PACI has multiple {kind} members: {matches}"
        )

    return matches[0]


def parse_paci(
    path: Path,
) -> tuple[
    dict[tuple[str, str, int], dict[str, object]],
    dict[tuple[str, str, int, int], dict[str, object]],
    int,
]:
    """PACI BAC/KYIを事前情報だけで正規化する。"""
    audit = Audit()
    parser = Parser(audit)
    races_by_internal_key: dict[str, dict[str, object]] = {}
    races_by_eval_key: dict[tuple[str, str, int], dict[str, object]] = {}
    horses: dict[tuple[str, str, int, int], dict[str, object]] = {}
    duplicate_paci_keys = 0

    with zipfile.ZipFile(path) as archive:
        bac_member = find_single_member(archive, BAC_MEMBER_RE, "BAC")
        kyi_member = find_single_member(archive, KYI_MEMBER_RE, "KYI")

        bac_records = read_fixed_records(archive, bac_member, "BAC", audit)
        kyi_records = read_fixed_records(archive, kyi_member, "KYI", audit)

        if audit.record_length_errors:
            raise EnrichmentError(
                "PACI fixed-record length error: "
                + str(dict(audit.record_length_errors))
            )

        for record_no, raw in enumerate(bac_records, start=1):
            source = SourceRecord(
                source_path=str(path),
                member_name=bac_member,
                record_no=record_no,
                raw=raw,
            )
            try:
                race_row = parse_bac_record_full(source)
            except ExportError as exc:
                raise EnrichmentError(str(exc)) from exc

            internal_race_key = race_key(raw)
            if internal_race_key in races_by_internal_key:
                raise EnrichmentError(
                    f"duplicate BAC race_key in PACI: {internal_race_key}"
                )

            race_row["track_condition_code"] = ""
            labeled_race = add_labels(race_row)
            labeled_race["race_key"] = internal_race_key

            eval_race_key = (
                str(labeled_race["race_date"]),
                str(labeled_race["venue_code"]),
                int(labeled_race["race_no"]),
            )

            if eval_race_key in races_by_eval_key:
                raise EnrichmentError(
                    f"duplicate BAC Eval race key in PACI: {eval_race_key}"
                )

            races_by_internal_key[internal_race_key] = labeled_race
            races_by_eval_key[eval_race_key] = labeled_race

        for raw in kyi_records:
            parsed = parser.kyi(raw)
            internal_race_key = str(parsed["race_key_raw"])
            race_row = races_by_internal_key.get(internal_race_key)

            if race_row is None:
                raise EnrichmentError(
                    "KYI references a race_key not found in BAC: "
                    f"{internal_race_key}"
                )

            horse_no_value = parsed.get("horse_no")
            if horse_no_value is None:
                raise EnrichmentError(
                    f"KYI horse_no is blank: race_key={internal_race_key}"
                )
            horse_no = int(horse_no_value)

            horse_key = make_horse_key(
                str(race_row["race_date"]),
                str(race_row["venue_code"]),
                int(race_row["race_no"]),
                horse_no,
            )

            if horse_key in horses:
                duplicate_paci_keys += 1
                continue

            previous = parsed.get("previous")
            prev_result_key_1 = ""
            prev_race_key_1 = ""
            if isinstance(previous, list) and previous:
                first_previous = previous[0]
                if isinstance(first_previous, dict):
                    prev_result_key_1 = str(
                        first_previous.get("result_key") or ""
                    )
                    prev_race_key_1 = str(
                        first_previous.get("race_key_raw") or ""
                    )

            carried_weight = ""
            carried_weight_tenths = parsed.get("carried_weight_tenths")
            if carried_weight_tenths is not None:
                carried_weight = float(carried_weight_tenths) / 10.0

            running_style = str(parsed.get("running_style_code") or "")
            distance_aptitude = str(parsed.get("distance_fit_code") or "")
            uptrend = str(parsed.get("improvement_code") or "")

            horses[horse_key] = {
                "race_key": internal_race_key,
                "horse_name": str(parsed.get("horse_name") or ""),
                "frame_no": parsed.get("frame_no"),
                "jockey_name": str(parsed.get("jockey") or ""),
                "carried_weight": carried_weight,
                "running_style": running_style,
                "running_style_label": RUNNING_STYLE.get(
                    running_style, ""
                ),
                "distance_aptitude": distance_aptitude,
                "distance_aptitude_label": DISTANCE_FIT.get(
                    distance_aptitude, ""
                ),
                "uptrend": uptrend,
                "uptrend_label": IMPROVEMENT.get(uptrend, ""),
                "training_index": parsed.get("training_index"),
                "prev_result_key_1": prev_result_key_1,
                "prev_race_key_1": prev_race_key_1,
                "_race": race_row,
            }

    if duplicate_paci_keys > 0:
        raise EnrichmentError(
            f"duplicate PACI horse join key(s): {duplicate_paci_keys}"
        )

    return races_by_eval_key, horses, duplicate_paci_keys


def build_enriched_row(
    eval_row: dict[str, object],
    paci_horse: dict[str, object] | None,
) -> dict[str, object]:
    """Eval 1行へPACI事前情報を付与する。"""
    output: dict[str, object] = {}

    for column in EVAL_REQUIRED_COLUMNS:
        output[column] = eval_row[column]

    output["venue_code"] = eval_row["_venue_code"]

    if paci_horse is None:
        output["join_status"] = "UNMATCHED"
        for column in OUTPUT_COLUMNS:
            if column not in output:
                output[column] = ""
        return output

    output["join_status"] = "MATCHED"

    horse_columns = (
        "race_key",
        "horse_name",
        "frame_no",
        "jockey_name",
        "carried_weight",
        "running_style",
        "running_style_label",
        "distance_aptitude",
        "distance_aptitude_label",
        "uptrend",
        "uptrend_label",
        "training_index",
        "prev_result_key_1",
        "prev_race_key_1",
    )
    for column in horse_columns:
        output[column] = paci_horse.get(column, "")

    race_row = paci_horse["_race"]
    race_columns = (
        "race_name",
        "race_type_code",
        "race_type_label",
        "race_condition_code",
        "class_label",
        "grade_code",
        "grade_label",
        "track_type",
        "track_label",
        "distance",
        "declared_field_size",
        "race_symbol_code",
        "sex_condition_label",
        "is_filly_only",
        "weight_condition_code",
        "weight_condition_label",
        "turn_direction_code",
        "turn_direction_label",
        "inner_outer_code",
        "inner_outer_label",
        "course_code",
        "course_label",
        "event_region_code",
    )
    for column in race_columns:
        output[column] = race_row.get(column, "")

    return output


def build_audit(
    eval_rows: list[dict[str, object]],
    paci_races: dict[tuple[str, str, int], dict[str, object]],
    paci_horses: dict[tuple[str, str, int, int], dict[str, object]],
    duplicate_paci_keys: int,
) -> dict[str, object]:
    """指定された監査指標と詳細を生成する。"""
    eval_race_horses: dict[
        tuple[str, str, int],
        set[int],
    ] = {}

    for row in eval_rows:
        horse_key = row["_key"]
        race_key_value = make_race_key(horse_key)

        horses_for_race = eval_race_horses.get(race_key_value)
        if horses_for_race is None:
            horses_for_race = set()
            eval_race_horses[race_key_value] = horses_for_race
        horses_for_race.add(int(horse_key[3]))

    eval_race_keys = set(eval_race_horses)

    target_paci_races = {}
    for key, row in paci_races.items():
        if key in eval_race_keys:
            target_paci_races[key] = row

    target_paci_horses = {}
    for key, row in paci_horses.items():
        if make_race_key(key) in eval_race_keys:
            target_paci_horses[key] = row

    joined_keys = []
    unmatched_keys = []

    for row in eval_rows:
        key = row["_key"]
        if key in paci_horses:
            joined_keys.append(key)
        else:
            unmatched_keys.append(key)

    paci_horses_by_race: dict[
        tuple[str, str, int],
        set[int],
    ] = {}
    for horse_key in target_paci_horses:
        race_key_value = make_race_key(horse_key)
        horses_for_race = paci_horses_by_race.get(race_key_value)
        if horses_for_race is None:
            horses_for_race = set()
            paci_horses_by_race[race_key_value] = horses_for_race
        horses_for_race.add(int(horse_key[3]))

    headcount_mismatches = []

    for race_key_value in sorted(eval_race_keys):
        eval_count = len(eval_race_horses.get(race_key_value, set()))
        paci_count = len(paci_horses_by_race.get(race_key_value, set()))

        declared_field_size = None
        race_row = paci_races.get(race_key_value)
        if race_row is not None:
            declared_field_size = race_row.get("declared_field_size")

        mismatch = False
        if eval_count != paci_count:
            mismatch = True
        if declared_field_size is not None:
            if eval_count != int(declared_field_size):
                mismatch = True
            if paci_count != int(declared_field_size):
                mismatch = True

        if mismatch:
            headcount_mismatches.append(
                {
                    "race_date": race_key_value[0],
                    "venue_code": race_key_value[1],
                    "race_no": race_key_value[2],
                    "eval_horses": eval_count,
                    "paci_horses": paci_count,
                    "declared_field_size": declared_field_size,
                }
            )

    unmatched_details = []
    for key in unmatched_keys:
        unmatched_details.append(
            {
                "race_date": key[0],
                "venue_code": key[1],
                "race_no": key[2],
                "horse_no": key[3],
            }
        )

    summary = {
        "eval_input_races": len(eval_race_keys),
        "eval_input_horses": len(eval_rows),
        "paci_target_races": len(target_paci_races),
        "paci_target_horses": len(target_paci_horses),
        "joined_horses": len(joined_keys),
        "unmatched_horses": len(unmatched_keys),
        "duplicate_eval_keys": 0,
        "duplicate_paci_keys": duplicate_paci_keys,
        "duplicate_keys": duplicate_paci_keys,
        "race_headcount_mismatches": len(headcount_mismatches),
    }

    return {
        "schema_version": "1.0",
        "summary": summary,
        "unmatched_keys": unmatched_details,
        "headcount_mismatches": headcount_mismatches,
    }


def enrich_eval_csv(
    eval_csv: Path,
    paci: Path,
    output: Path,
    audit_json: Path | None,
    fail_on_unmatched: bool,
) -> dict[str, object]:
    """Eval OCR CSVへPACI事前情報を結合してCSVを生成する。"""
    eval_rows, _ = load_eval_csv(eval_csv)
    paci_races, paci_horses, duplicate_paci_keys = parse_paci(paci)

    enriched_rows: list[dict[str, object]] = []

    for eval_row in eval_rows:
        key = eval_row["_key"]
        paci_horse = paci_horses.get(key)
        enriched_rows.append(build_enriched_row(eval_row, paci_horse))

    audit = build_audit(
        eval_rows,
        paci_races,
        paci_horses,
        duplicate_paci_keys,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(enriched_rows)

    if audit_json is not None:
        audit_json.parent.mkdir(parents=True, exist_ok=True)
        with audit_json.open("w", encoding="utf-8") as handle:
            json.dump(audit, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    summary = audit["summary"]
    if fail_on_unmatched and int(summary["unmatched_horses"]) > 0:
        raise EnrichmentError(
            f"{summary['unmatched_horses']} Eval horse(s) were not joined"
        )

    return audit


def build_argument_parser() -> argparse.ArgumentParser:
    """CLI引数を定義する。"""
    parser = argparse.ArgumentParser(
        description=(
            "Enrich Eval OCR CSV with pre-race JRDB PACI BAC/KYI data."
        )
    )
    parser.add_argument(
        "--eval-csv",
        type=Path,
        required=True,
        help="Eval OCR CSV: date,venue,race_no,horse_no,eval",
    )
    parser.add_argument(
        "--paci",
        type=Path,
        required=True,
        help="JRDB PACIyymmdd.zip",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="UTF-8 BOM enriched CSV output path",
    )
    parser.add_argument(
        "--audit-json",
        type=Path,
        help="Optional audit JSON output path",
    )
    parser.add_argument(
        "--fail-on-unmatched",
        action="store_true",
        help="Exit with error when one or more Eval horses cannot be joined",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=VERSION,
    )
    return parser


def main() -> int:
    """CLIエントリポイント。"""
    parser = build_argument_parser()
    args = parser.parse_args()

    try:
        audit = enrich_eval_csv(
            eval_csv=args.eval_csv,
            paci=args.paci,
            output=args.output,
            audit_json=args.audit_json,
            fail_on_unmatched=args.fail_on_unmatched,
        )

        summary = audit["summary"]
        for key, value in summary.items():
            print(f"{key}: {value}")

        return 0

    except (
        EnrichmentError,
        FileNotFoundError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
