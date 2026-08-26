#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JRDB Raw -> Eval race-level integrated CSV exporter.

Analysis Lite / Core SQLiteには依存せず、BAC + SED Rawのみから
Eval表検証用の1レース1行CSVを生成する。
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
import re
import sys
import zipfile

from export_jrdb_eval_race_conditions import (
    ExportError,
    RaceTarget,
    SourceRecord,
    decode_text,
    load_targets_csv,
    make_row_key,
    normalize_date_yyyymmdd,
    normalize_venue_code,
    parse_bac_record_full,
    parse_int,
    parse_optional_date,
    row_matches,
)

VERSION = "1.0.0"

OUTPUT_COLUMNS = (
    "race_date", "venue_code", "race_no", "race_name",
    "race_type_code", "race_condition_code", "race_symbol_code",
    "weight_condition_code", "grade_code", "track_type", "distance",
    "track_condition_code", "declared_field_size", "turn_direction_code",
    "inner_outer_code", "course_code", "event_region_code",
    "venue_name", "track_label", "class_label", "grade_label",
    "track_condition_label", "race_type_label", "sex_condition_label",
    "is_filly_only", "weight_condition_label", "turn_direction_label",
    "inner_outer_label", "course_label",
)

SED_MIN_LENGTH = 133
SED_OFFSETS = {
    "venue_code": (0, 2), "race_no": (6, 2), "race_date": (18, 8),
    "distance": (62, 4), "track_type": (66, 1),
    "turn_direction_code": (67, 1), "inner_outer_code": (68, 1),
    "track_condition_code": (69, 2), "race_type_code": (71, 2),
    "race_condition_code": (73, 2), "race_symbol_code": (75, 3),
    "weight_condition_code": (78, 1), "grade_code": (79, 1),
    "race_name": (80, 50), "declared_field_size": (130, 2),
}

BAC_MEMBER_RE = re.compile(r"^BAC\d{6}\.txt$", re.IGNORECASE)
SED_MEMBER_RE = re.compile(r"^SED\d{6}\.txt$", re.IGNORECASE)
RAW_ARCHIVE_RE = re.compile(
    r"^(?:BAC|SED)_\d{4}\.zip$|^(?:BAC|SED|PACI)\d{6}\.zip$",
    re.IGNORECASE,
)
RAW_TEXT_RE = re.compile(r"^(?:BAC|SED)\d{6}\.txt$", re.IGNORECASE)

VENUE_LABELS = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}
TRACK_LABELS = {"1": "芝", "2": "ダート", "3": "障害"}
CLASS_LABELS = {
    "A1": "新馬", "A2": "未出走", "A3": "未勝利",
    "04": "1勝クラス", "05": "1勝クラス",
    "08": "2勝クラス", "09": "2勝クラス", "10": "2勝クラス",
    "15": "3勝クラス", "16": "3勝クラス", "OP": "オープン",
}
GRADE_LABELS = {"1": "G1", "2": "G2", "3": "G3", "4": "重賞", "5": "特別", "6": "L"}
TRACK_CONDITION_LABELS = {
    "10": "良", "11": "良", "12": "良",
    "20": "稍重", "21": "稍重", "22": "稍重",
    "30": "重", "31": "重", "32": "重",
    "40": "不良", "41": "不良", "42": "不良",
}
RACE_TYPE_LABELS = {
    "11": "2歳", "12": "3歳", "13": "3歳以上", "14": "4歳以上",
    "20": "障害", "99": "その他",
}
SEX_LABELS = {
    "0": "指定なし", "1": "牡馬限定", "2": "牝馬限定",
    "3": "牡・せん馬限定", "4": "牡・牝馬限定",
}
WEIGHT_LABELS = {"1": "ハンデ", "2": "別定", "3": "馬齢", "4": "定量"}
TURN_LABELS = {"1": "右", "2": "左", "3": "直", "9": "他"}
INNER_OUTER_LABELS = {"1": "通常(内)", "2": "外", "3": "直ダ", "9": "他"}
COURSE_LABELS = {"1": "A", "2": "A1", "3": "A2", "4": "B", "5": "C", "6": "D"}


@dataclass(frozen=True)
class RawSource:
    """RawファイルまたはZIPの種別付き参照。"""

    path: Path
    kind: str


def parse_sed_race_record(record: SourceRecord) -> dict[str, object]:
    """SED馬単位レコードからレース共通項目だけを抽出する。"""
    raw = record.raw
    if len(raw) < SED_MIN_LENGTH:
        raise ExportError(
            f"SED record too short: {record.source_path} {record.member_name} "
            f"record={record.record_no} bytes={len(raw)}"
        )

    race_no = parse_int(raw, *SED_OFFSETS["race_no"])
    distance = parse_int(raw, *SED_OFFSETS["distance"])
    field_size = parse_int(raw, *SED_OFFSETS["declared_field_size"])
    if race_no is None:
        raise ExportError(
            f"SED race_no is blank: {record.source_path} record={record.record_no}"
        )

    return {
        "race_date": normalize_date_yyyymmdd(
            decode_text(raw, *SED_OFFSETS["race_date"])
        ),
        "venue_code": normalize_venue_code(
            decode_text(raw, *SED_OFFSETS["venue_code"])
        ),
        "race_no": race_no,
        "race_name": decode_text(raw, *SED_OFFSETS["race_name"]),
        "race_type_code": decode_text(raw, *SED_OFFSETS["race_type_code"]),
        "race_condition_code": decode_text(raw, *SED_OFFSETS["race_condition_code"]),
        "race_symbol_code": decode_text(raw, *SED_OFFSETS["race_symbol_code"]),
        "weight_condition_code": decode_text(raw, *SED_OFFSETS["weight_condition_code"]),
        "grade_code": decode_text(raw, *SED_OFFSETS["grade_code"]),
        "track_type": decode_text(raw, *SED_OFFSETS["track_type"]),
        "distance": distance,
        "track_condition_code": decode_text(raw, *SED_OFFSETS["track_condition_code"]),
        "declared_field_size": field_size,
        "turn_direction_code": decode_text(raw, *SED_OFFSETS["turn_direction_code"]),
        "inner_outer_code": decode_text(raw, *SED_OFFSETS["inner_outer_code"]),
    }


def discover_raw_sources(raw_inputs: list[Path]) -> list[RawSource]:
    """BAC/SED/PACIのZIPと展開済みBAC/SEDテキストを再帰探索する。"""
    discovered: set[tuple[Path, str]] = set()

    for raw_input in raw_inputs:
        if not raw_input.exists():
            raise FileNotFoundError(raw_input)

        if raw_input.is_dir():
            candidates = list(raw_input.rglob("*"))
        else:
            candidates = [raw_input]

        for candidate in candidates:
            if not candidate.is_file():
                continue

            name = candidate.name
            if RAW_ARCHIVE_RE.fullmatch(name):
                discovered.add((candidate.resolve(), "zip"))
            elif RAW_TEXT_RE.fullmatch(name):
                if name.upper().startswith("BAC"):
                    kind = "bac"
                else:
                    kind = "sed"
                discovered.add((candidate.resolve(), kind))

    return [
        RawSource(path=item[0], kind=item[1])
        for item in sorted(discovered)
    ]


def records_from_bytes(
    data: bytes,
    source_path: str,
    member_name: str,
) -> list[SourceRecord]:
    """固定長テキストbytesを行単位SourceRecordへ変換する。"""
    records: list[SourceRecord] = []
    for index, raw in enumerate(data.splitlines(), start=1):
        if raw == b"":
            continue
        records.append(
            SourceRecord(source_path, member_name, index, raw)
        )
    return records


def iter_source_records(source: RawSource) -> list[tuple[str, SourceRecord]]:
    """RawSourceから(kind, record)を返す。"""
    result: list[tuple[str, SourceRecord]] = []

    if source.kind in {"bac", "sed"}:
        data = source.path.read_bytes()
        records = records_from_bytes(data, str(source.path), source.path.name)
        for record in records:
            result.append((source.kind, record))
        return result

    with zipfile.ZipFile(source.path) as archive:
        for member_name in sorted(archive.namelist()):
            base_name = Path(member_name).name
            kind = ""
            if BAC_MEMBER_RE.fullmatch(base_name):
                kind = "bac"
            elif SED_MEMBER_RE.fullmatch(base_name):
                kind = "sed"

            if kind == "":
                continue

            data = archive.read(member_name)
            records = records_from_bytes(data, str(source.path), member_name)
            for record in records:
                result.append((kind, record))

    return result


def add_unique_race(
    rows: dict[tuple[str, str, int], dict[str, object]],
    row: dict[str, object],
    source_kind: str,
) -> int:
    """同一TYPE内で1レース1行へ集約し、矛盾時は停止する。"""
    key = make_row_key(row)
    previous = rows.get(key)

    if previous is None:
        rows[key] = row
        return 0

    if previous == row:
        return 1

    raise ExportError(
        f"conflicting {source_kind.upper()} race rows for Eval key {key}"
    )


def validate_bac_sed(
    bac: dict[str, object],
    sed: dict[str, object],
) -> None:
    """BACとSEDの共通レース条件が一致することを検証する。"""
    fields = (
        "race_date", "venue_code", "race_no", "race_name",
        "race_type_code", "race_condition_code", "race_symbol_code",
        "weight_condition_code", "grade_code", "track_type", "distance",
        "declared_field_size", "turn_direction_code", "inner_outer_code",
    )

    mismatches: list[str] = []
    for field in fields:
        if bac.get(field) != sed.get(field):
            mismatches.append(
                f"{field}: BAC={bac.get(field)!r} SED={sed.get(field)!r}"
            )

    if mismatches:
        key = make_row_key(bac)
        raise ExportError(
            f"BAC/SED mismatch for Eval key {key}: " + "; ".join(mismatches)
        )


def sex_code_from_symbol(symbol: str) -> str:
    """3桁記号コードの2桁目（性別条件）を返す。"""
    if len(symbol) < 2:
        return ""
    return symbol[1]


def add_labels(row: dict[str, object]) -> dict[str, object]:
    """生コードを残したまま表示用派生列を追加する。"""
    result = dict(row)
    symbol = str(row.get("race_symbol_code", ""))
    sex_code = sex_code_from_symbol(symbol)

    result.update({
        "venue_name": VENUE_LABELS.get(str(row.get("venue_code", "")), ""),
        "track_label": TRACK_LABELS.get(str(row.get("track_type", "")), ""),
        "class_label": CLASS_LABELS.get(str(row.get("race_condition_code", "")), ""),
        "grade_label": GRADE_LABELS.get(str(row.get("grade_code", "")), ""),
        "track_condition_label": TRACK_CONDITION_LABELS.get(
            str(row.get("track_condition_code", "")), ""
        ),
        "race_type_label": RACE_TYPE_LABELS.get(
            str(row.get("race_type_code", "")), ""
        ),
        "sex_condition_label": SEX_LABELS.get(sex_code, ""),
        "is_filly_only": "1" if sex_code == "2" else "0",
        "weight_condition_label": WEIGHT_LABELS.get(
            str(row.get("weight_condition_code", "")), ""
        ),
        "turn_direction_label": TURN_LABELS.get(
            str(row.get("turn_direction_code", "")), ""
        ),
        "inner_outer_label": INNER_OUTER_LABELS.get(
            str(row.get("inner_outer_code", "")), ""
        ),
        "course_label": COURSE_LABELS.get(str(row.get("course_code", "")), ""),
    })
    return result


def export_dataset(
    raw_inputs: list[Path],
    output_path: Path,
    start_date: dt.date | None,
    end_date: dt.date | None,
    targets: set[RaceTarget] | None,
    allow_missing_sed: bool,
) -> dict[str, int]:
    """Raw BAC+SEDを統合しEval専用1レース1行CSVを生成する。"""
    sources = discover_raw_sources(raw_inputs)
    if not sources:
        raise ExportError("no supported JRDB Raw sources found")

    bac_rows: dict[tuple[str, str, int], dict[str, object]] = {}
    sed_rows: dict[tuple[str, str, int], dict[str, object]] = {}
    bac_records = 0
    sed_records = 0
    duplicates = 0

    for source in sources:
        for kind, record in iter_source_records(source):
            if kind == "bac":
                bac_records += 1
                row = parse_bac_record_full(record)
            else:
                sed_records += 1
                row = parse_sed_race_record(record)

            if not row_matches(row, start_date, end_date, targets):
                continue

            if kind == "bac":
                duplicates += add_unique_race(bac_rows, row, "bac")
            else:
                duplicates += add_unique_race(sed_rows, row, "sed")

    output_rows: list[dict[str, object]] = []
    missing_sed = 0

    for key in sorted(bac_rows):
        bac = bac_rows[key]
        sed = sed_rows.get(key)

        if sed is None:
            missing_sed += 1
            if not allow_missing_sed:
                raise ExportError(f"SED race not found for Eval key {key}")
            merged = dict(bac)
            merged["track_condition_code"] = ""
        else:
            validate_bac_sed(bac, sed)
            merged = dict(bac)
            merged["track_condition_code"] = sed["track_condition_code"]

        output_rows.append(add_labels(merged))

    orphan_sed = len(set(sed_rows).difference(bac_rows))
    if orphan_sed > 0:
        raise ExportError(
            f"{orphan_sed} SED race(s) have no matching BAC race"
        )

    missing_targets = 0
    if targets is not None:
        found = {
            RaceTarget(
                str(row["race_date"]),
                str(row["venue_code"]),
                int(row["race_no"]),
            )
            for row in output_rows
        }
        missing_targets = len(targets.difference(found))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(output_rows)

    return {
        "source_files": len(sources),
        "bac_records": bac_records,
        "sed_records": sed_records,
        "bac_races": len(bac_rows),
        "sed_races": len(sed_rows),
        "output_rows": len(output_rows),
        "identical_duplicates_collapsed": duplicates,
        "missing_sed_races": missing_sed,
        "missing_targets": missing_targets,
    }


def build_argument_parser() -> argparse.ArgumentParser:
    """CLI引数定義を生成する。"""
    parser = argparse.ArgumentParser(
        description="Export Eval race dataset from JRDB Raw BAC + SED."
    )
    parser.add_argument(
        "--raw", type=Path, nargs="+", required=True,
        help="JRDB Raw files/directories.",
    )
    parser.add_argument(
        "--output", type=Path, required=True,
        help="Output CSV path.",
    )
    parser.add_argument(
        "--start-date",
        help="Inclusive start date YYYY-MM-DD.",
    )
    parser.add_argument(
        "--end-date",
        help="Inclusive end date YYYY-MM-DD.",
    )
    parser.add_argument(
        "--targets-csv", type=Path,
        help="CSV with race_date,venue_code,race_no.",
    )
    parser.add_argument(
        "--allow-missing-sed", action="store_true",
        help="Allow BAC races without completed SED; track condition is blank.",
    )
    parser.add_argument(
        "--fail-on-missing-target", action="store_true",
        help="Fail if a target race was not output.",
    )
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def main() -> int:
    """CLIエントリポイント。"""
    parser = build_argument_parser()
    args = parser.parse_args()

    try:
        start_date = parse_optional_date(args.start_date)
        end_date = parse_optional_date(args.end_date)
        if (
            start_date is not None
            and end_date is not None
            and start_date > end_date
        ):
            raise ExportError("start-date must be <= end-date")

        targets = None
        if args.targets_csv is not None:
            targets = load_targets_csv(args.targets_csv)

        metrics = export_dataset(
            args.raw,
            args.output,
            start_date,
            end_date,
            targets,
            args.allow_missing_sed,
        )

        for key, value in metrics.items():
            print(f"{key}: {value}")

        if args.fail_on_missing_target and metrics["missing_targets"] > 0:
            raise ExportError(
                f"{metrics['missing_targets']} target race(s) were not found"
            )

        return 0

    except (ExportError, FileNotFoundError, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
