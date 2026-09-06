#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JRDB SED Raw -> Eval horse-level result CSV exporter.

Google Sheets「Eval表集計・検証 / 全馬データ」への結果取込前に使う
馬単位の中間CSVと監査JSONを生成する。

Raw探索・ZIP/TXT読込は既存 export_jrdb_eval_dataset.py の共通処理を再利用する。
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sys
import zipfile
from jrdb_eval_horse_result_adapter import project_eval_horse_result

from export_jrdb_eval_dataset import (
    ExportError,
    VENUE_LABELS,
    discover_raw_sources,
    iter_source_records,
)
from export_jrdb_eval_race_conditions import (
    SourceRecord,
    decode_text,
    normalize_date_yyyymmdd,
    normalize_venue_code,
    parse_int,
)

VERSION = "1.0.0"

OUTPUT_COLUMNS = (
    "race_date",
    "venue_code",
    "venue_name",
    "race_no",
    "horse_no",
    "horse_name",
    "blood_registration_no",
    "finish_position_raw",
    "finish_position_eval",
    "abnormality_code",
    "abnormality_label",
    "review_required",
    "review_reason",
    "in_top3",
    "place_payout",
    "final_place_odds_lower",
    "final_place_odds_upper",
    "source_kind",
    "source_file",
    "source_member",
    "source_record_no",
)

# SED固定長仕様。offsetは0始まり。splitlines後の本体長は374 BYTE。
SED_MIN_LENGTH = 374
SED_OFFSETS = {
    "venue_code": (0, 2),
    "race_no": (6, 2),
    "horse_no": (8, 2),
    "blood_registration_no": (10, 8),
    "race_date": (18, 8),
    "horse_name": (26, 36),
    "finish_position": (140, 2),
    "abnormality_code": (142, 1),
    "final_place_odds_lower": (290, 6),
    "place_payout": (348, 7),
}

JRA_VENUE_CODES = set(VENUE_LABELS)
ABNORMALITY_LABELS = {
    "0": "異常なし",
    "1": "取消",
    "2": "除外",
    "3": "中止",
    "4": "失格",
    "5": "降着",
    "6": "再騎乗",
}


def parse_optional_decimal(raw: bytes, offset: int, width: int) -> str:
    """固定長小数を検証し、CSV向けの文字列で返す。空欄は空文字。"""
    value = decode_text(raw, offset, width)
    if value == "":
        return ""
    try:
        decimal_value = Decimal(value)
    except InvalidOperation as exc:
        raise ExportError(f"invalid decimal field: {value!r}") from exc
    return format(decimal_value, "f")


def parse_optional_int_text(raw: bytes, offset: int, width: int) -> int | str:
    """固定長整数を読み取り、空欄は空文字で返す。"""
    value = decode_text(raw, offset, width)
    if value == "":
        return ""
    try:
        return int(value)
    except ValueError as exc:
        raise ExportError(f"invalid integer field: {value!r}") from exc


def parse_sed_horse_record(record: SourceRecord) -> dict[str, object]:
    """SED 1レコードをEval全馬データ結果用の馬単位行へ変換する。"""
    raw = record.raw
    if len(raw) < SED_MIN_LENGTH:
        raise ExportError(
            f"SED record too short: {record.source_path} {record.member_name} "
            f"record={record.record_no} bytes={len(raw)}"
        )

    try:
        row = project_eval_horse_result(raw, VENUE_LABELS, ABNORMALITY_LABELS)
    except ValueError as exc:
        raise ExportError(
            f"{exc}: {record.source_path} record={record.record_no}"
        ) from exc
    row.update({
        "source_kind": "SED",
        "source_file": record.source_path,
        "source_member": record.member_name,
        "source_record_no": record.record_no,
    })
    return row

    venue_code = normalize_venue_code(
        decode_text(raw, *SED_OFFSETS["venue_code"])
    )
    race_no = parse_int(raw, *SED_OFFSETS["race_no"])
    horse_no = parse_int(raw, *SED_OFFSETS["horse_no"])
    finish_position = parse_int(raw, *SED_OFFSETS["finish_position"])
    abnormality_code = decode_text(raw, *SED_OFFSETS["abnormality_code"])

    if race_no is None:
        raise ExportError(
            f"SED race_no is blank: {record.source_path} record={record.record_no}"
        )
    if horse_no is None:
        raise ExportError(
            f"SED horse_no is blank: {record.source_path} record={record.record_no}"
        )
    if abnormality_code == "":
        raise ExportError(
            f"SED abnormality_code is blank: {record.source_path} "
            f"record={record.record_no}"
        )
    if abnormality_code not in ABNORMALITY_LABELS:
        raise ExportError(
            f"unknown SED abnormality_code={abnormality_code!r}: "
            f"{record.source_path} record={record.record_no}"
        )

    finish_position_raw: int | str = ""
    finish_position_eval: int | str = ""
    in_top3 = ""
    review_required = 0
    review_reason = ""

    if finish_position is not None:
        finish_position_raw = finish_position

    if abnormality_code == "0":
        if finish_position is None or finish_position <= 0:
            raise ExportError(
                "normal SED row has invalid finish position: "
                f"{record.source_path} record={record.record_no} "
                f"finish={finish_position!r}"
            )
        finish_position_eval = finish_position if finish_position <= 3 else 4
        in_top3 = "○" if finish_position <= 3 else "×"
    else:
        review_required = 1
        review_reason = (
            "SED異常区分のため台帳着順を自動確定しない: "
            + ABNORMALITY_LABELS[abnormality_code]
        )

    return {
        "race_date": normalize_date_yyyymmdd(
            decode_text(raw, *SED_OFFSETS["race_date"])
        ),
        "venue_code": venue_code,
        "venue_name": VENUE_LABELS.get(venue_code, ""),
        "race_no": race_no,
        "horse_no": horse_no,
        "horse_name": decode_text(raw, *SED_OFFSETS["horse_name"]),
        "blood_registration_no": decode_text(
            raw, *SED_OFFSETS["blood_registration_no"]
        ),
        "finish_position_raw": finish_position_raw,
        "finish_position_eval": finish_position_eval,
        "abnormality_code": abnormality_code,
        "abnormality_label": ABNORMALITY_LABELS[abnormality_code],
        "review_required": review_required,
        "review_reason": review_reason,
        "in_top3": in_top3,
        "place_payout": parse_optional_int_text(
            raw, *SED_OFFSETS["place_payout"]
        ),
        "final_place_odds_lower": parse_optional_decimal(
            raw, *SED_OFFSETS["final_place_odds_lower"]
        ),
        # 現行SED仕様に上限フィールドは確認できないため、推測せず空欄固定。
        "final_place_odds_upper": "",
        "source_kind": "SED",
        "source_file": record.source_path,
        "source_member": record.member_name,
        "source_record_no": record.record_no,
    }


def make_key(row: dict[str, object]) -> tuple[str, str, int, int]:
    """Eval全馬データとの外部結合キーを返す。"""
    return (
        str(row["race_date"]),
        str(row["venue_code"]),
        int(row["race_no"]),
        int(row["horse_no"]),
    )


def parse_date(value: str) -> dt.date:
    """YYYY-MM-DDをdateへ変換する。"""
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ExportError(f"invalid date: {value!r}") from exc


def row_is_selected(
    row: dict[str, object],
    dates: set[str] | None,
    start_date: dt.date | None,
    end_date: dt.date | None,
    include_non_jra: bool,
) -> bool:
    """日付条件とJRA場条件で出力対象か判定する。"""
    race_date = str(row["race_date"])
    venue_code = str(row["venue_code"])

    if not include_non_jra and venue_code not in JRA_VENUE_CODES:
        return False
    if dates is not None and race_date not in dates:
        return False

    parsed_date = parse_date(race_date)
    if start_date is not None and parsed_date < start_date:
        return False
    if end_date is not None and parsed_date > end_date:
        return False
    return True


def rows_equivalent_for_duplicate(
    left: dict[str, object],
    right: dict[str, object],
) -> bool:
    """取得元メタデータを除いて同一レコードか判定する。"""
    ignored = {"source_file", "source_member", "source_record_no"}
    left_value = {k: v for k, v in left.items() if k not in ignored}
    right_value = {k: v for k, v in right.items() if k not in ignored}
    return left_value == right_value


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """UTF-8 BOM付きCSVを書き出す。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    """ファイルのSHA-256を返す。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_horse_results(
    raw_inputs: list[Path],
    output_path: Path,
    audit_output_path: Path,
    dates: set[str] | None,
    start_date: dt.date | None,
    end_date: dt.date | None,
    include_non_jra: bool,
) -> dict[str, object]:
    """SED Rawから馬単位結果CSVと監査JSONを生成する。"""
    sources = discover_raw_sources(raw_inputs)
    if not sources:
        raise ExportError("no supported JRDB Raw sources found")

    rows_by_key: dict[tuple[str, str, int, int], dict[str, object]] = {}
    sed_records = 0
    selected_records = 0
    identical_duplicates_collapsed = 0
    abnormality_counts: dict[str, int] = {}
    date_counts: dict[str, int] = {}

    for source in sources:
        for kind, record in iter_source_records(source):
            if kind != "sed":
                continue

            sed_records += 1
            row = parse_sed_horse_record(record)
            if not row_is_selected(
                row,
                dates,
                start_date,
                end_date,
                include_non_jra,
            ):
                continue

            selected_records += 1
            key = make_key(row)
            previous = rows_by_key.get(key)
            if previous is not None:
                if rows_equivalent_for_duplicate(previous, row):
                    identical_duplicates_collapsed += 1
                    continue
                raise ExportError(f"conflicting SED rows for Eval horse key {key}")

            rows_by_key[key] = row
            abnormality_code = str(row["abnormality_code"])
            abnormality_counts[abnormality_code] = (
                abnormality_counts.get(abnormality_code, 0) + 1
            )
            race_date = str(row["race_date"])
            date_counts[race_date] = date_counts.get(race_date, 0) + 1

    if sed_records == 0:
        raise ExportError("no SED records found in Raw inputs")
    if selected_records == 0:
        raise ExportError("no SED records matched the requested scope")

    rows = [rows_by_key[key] for key in sorted(rows_by_key)]
    write_csv(output_path, rows)

    review_required_rows = sum(
        1 for row in rows if int(row["review_required"]) == 1
    )
    odds_lower_blank_rows = sum(
        1 for row in rows if row["final_place_odds_lower"] == ""
    )
    place_payout_rows = sum(1 for row in rows if row["place_payout"] != "")

    audit: dict[str, object] = {
        "exporter": "export_jrdb_eval_horse_results.py",
        "version": VERSION,
        "validation_status": "success",
        "source_files_discovered": len(sources),
        "sed_records_read": sed_records,
        "selected_records": selected_records,
        "exported_rows": len(rows),
        "duplicate_keys": 0,
        "identical_duplicates_collapsed": identical_duplicates_collapsed,
        "review_required_rows": review_required_rows,
        "abnormality_counts": abnormality_counts,
        "final_place_odds_lower_blank_rows": odds_lower_blank_rows,
        "place_payout_nonblank_rows": place_payout_rows,
        "date_counts": date_counts,
        "requested_dates": sorted(dates) if dates is not None else [],
        "start_date": start_date.isoformat() if start_date is not None else None,
        "end_date": end_date.isoformat() if end_date is not None else None,
        "include_non_jra": include_non_jra,
        "output_file": str(output_path),
        "output_sha256": sha256_file(output_path),
    }

    audit_output_path.parent.mkdir(parents=True, exist_ok=True)
    audit_output_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return audit


def build_argument_parser() -> argparse.ArgumentParser:
    """CLI引数定義を生成する。"""
    parser = argparse.ArgumentParser(
        description="Export Eval horse results from JRDB Raw SED."
    )
    parser.add_argument(
        "--raw",
        type=Path,
        nargs="+",
        required=True,
        help="JRDB Raw SED files/directories.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output horse-level CSV path.",
    )
    parser.add_argument(
        "--audit-output",
        type=Path,
        help="Audit JSON path. Default: <output>.audit.json",
    )
    parser.add_argument(
        "--date",
        action="append",
        dest="dates",
        help="Target date YYYY-MM-DD. Repeatable.",
    )
    parser.add_argument("--start-date", help="Inclusive start date YYYY-MM-DD.")
    parser.add_argument("--end-date", help="Inclusive end date YYYY-MM-DD.")
    parser.add_argument(
        "--include-non-jra",
        action="store_true",
        help="Include venue codes outside JRA 01-10.",
    )
    parser.add_argument(
        "--fail-on-review-required",
        action="store_true",
        help="Return failure if abnormal SED rows require manual review.",
    )
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def main() -> int:
    """CLIエントリポイント。"""
    parser = build_argument_parser()
    args = parser.parse_args()

    try:
        dates = None
        if args.dates:
            dates = {parse_date(value).isoformat() for value in args.dates}

        start_date = parse_date(args.start_date) if args.start_date else None
        end_date = parse_date(args.end_date) if args.end_date else None
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ExportError("start-date must be <= end-date")

        audit_output = args.audit_output
        if audit_output is None:
            audit_output = args.output.with_suffix(args.output.suffix + ".audit.json")

        audit = export_horse_results(
            raw_inputs=args.raw,
            output_path=args.output,
            audit_output_path=audit_output,
            dates=dates,
            start_date=start_date,
            end_date=end_date,
            include_non_jra=args.include_non_jra,
        )

        print(json.dumps(audit, ensure_ascii=False, indent=2))
        if args.fail_on_review_required and int(audit["review_required_rows"]) > 0:
            raise ExportError(
                f"{audit['review_required_rows']} row(s) require manual review"
            )
        return 0

    except (ExportError, FileNotFoundError, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
