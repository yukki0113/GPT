#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JRDB BAC -> Eval race-condition CSV exporter.

Analysis Liteを変更せず、JRDB Raw BACからEval表検証用の
1レース1行レース条件CSVを生成する。

対応入力:
- 年次ZIP: BAC_YYYY.zip
- 単日ZIP: BACyymmdd.zip
- 展開済みBAC*.txt
- 上記を含むディレクトリ（再帰探索）

抽出方法:
- 期間指定: --start-date / --end-date
- 対象レースCSV指定: --targets-csv

出力はJRDBの生コードを保持する。
コードの表示名変換はREADMEに定義する。
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


VERSION = "1.0.0"

OUTPUT_COLUMNS = (
    "race_date",
    "venue_code",
    "race_no",
    "race_name",
    "race_type_code",
    "race_symbol_code",
    "weight_condition_code",
    "declared_field_size",
    "turn_direction_code",
    "inner_outer_code",
    "course_code",
    "event_region_code",
)

# BAC固定長仕様。offsetは0始まり。
BAC_MIN_LENGTH = 98
BAC_OFFSETS = {
    "venue_code": (0, 2),
    "race_no": (6, 2),
    "race_date": (8, 8),
    "turn_direction_code": (25, 1),
    "inner_outer_code": (26, 1),
    "race_type_code": (27, 2),
    "race_symbol_code": (31, 3),
    "weight_condition_code": (34, 1),
    "race_name": (36, 50),
    "declared_field_size": (94, 2),
    "course_code": (96, 1),
    "event_region_code": (97, 1),
}

BAC_TXT_RE = re.compile(r"^BAC\d{6}\.txt$", re.IGNORECASE)
BAC_ANNUAL_ZIP_RE = re.compile(r"^BAC_\d{4}\.zip$", re.IGNORECASE)
BAC_DAILY_ZIP_RE = re.compile(r"^BAC\d{6}\.zip$", re.IGNORECASE)


class ExportError(RuntimeError):
    """入力Rawまたは抽出条件に起因する処理エラー。"""


@dataclass(frozen=True)
class RaceTarget:
    """対象レースを開催日・場・Rで表す。"""

    race_date: str
    venue_code: str
    race_no: int


@dataclass(frozen=True)
class SourceRecord:
    """監査用に取得元を保持したBACレコード。"""

    source_path: str
    member_name: str
    record_no: int
    raw: bytes


def decode_text(raw: bytes, offset: int, width: int) -> str:
    """CP932固定長文字列をトリムして返す。"""
    return raw[offset:offset + width].decode("cp932", errors="replace").strip()


def parse_int(raw: bytes, offset: int, width: int) -> int | None:
    """固定長整数を読み取り、空欄はNoneで返す。"""
    value = decode_text(raw, offset, width)
    if value == "":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ExportError(f"invalid integer field: {value!r}") from exc


def normalize_date_yyyymmdd(value: str) -> str:
    """YYYYMMDDをYYYY-MM-DDへ変換する。"""
    try:
        parsed = dt.datetime.strptime(value, "%Y%m%d").date()
    except ValueError as exc:
        raise ExportError(f"invalid BAC race date: {value!r}") from exc
    return parsed.isoformat()


def normalize_venue_code(value: str) -> str:
    """場コードを2桁文字列へ正規化する。"""
    stripped = value.strip()
    if stripped == "":
        raise ExportError("venue_code is blank")
    if stripped.isdigit():
        return stripped.zfill(2)
    return stripped


def parse_bac_record(record: SourceRecord) -> dict[str, object]:
    """BAC 1レコードをEval補助CSVの1行へ変換する。"""
    raw = record.raw

    if len(raw) < BAC_MIN_LENGTH:
        raise ExportError(
            f"BAC record too short: {record.source_path} "
            f"{record.member_name} record={record.record_no} bytes={len(raw)}"
        )

    venue_code = decode_text(raw, *BAC_OFFSETS["venue_code"])
    race_no = parse_int(raw, *BAC_OFFSETS["race_no"])
    race_date_raw = decode_text(raw, *BAC_OFFSETS["race_date"])
    declared_field_size = parse_int(raw, *BAC_OFFSETS["declared_field_size"])

    if race_no is None:
        raise ExportError(
            f"race_no is blank: {record.source_path} "
            f"{record.member_name} record={record.record_no}"
        )

    row: dict[str, object] = {
        "race_date": normalize_date_yyyymmdd(race_date_raw),
        "venue_code": normalize_venue_code(venue_code),
        "race_no": race_no,
        "race_name": decode_text(raw, *BAC_OFFSETS["race_name"]),
        "race_type_code": decode_text(raw, *BAC_OFFSETS["race_type_code"]),
        "race_symbol_code": decode_text(raw, *BAC_OFFSETS["race_symbol_code"]),
        "weight_condition_code": decode_text(
            raw, *BAC_OFFSETS["weight_condition_code"]
        ),
        "declared_field_size": declared_field_size,
        "turn_direction_code": decode_text(
            raw, *BAC_OFFSETS["turn_direction_code"]
        ),
        "inner_outer_code": decode_text(raw, *BAC_OFFSETS["inner_outer_code"]),
        "course_code": decode_text(raw, *BAC_OFFSETS["course_code"]),
        "event_region_code": decode_text(
            raw, *BAC_OFFSETS["event_region_code"]
        ),
    }
    return row


def iter_text_records(path: Path) -> list[SourceRecord]:
    """展開済みBACテキストからレコードを読む。"""
    data = path.read_bytes()
    lines = data.splitlines()
    records: list[SourceRecord] = []

    for index, raw in enumerate(lines, start=1):
        if raw == b"":
            continue
        records.append(
            SourceRecord(
                source_path=str(path),
                member_name=path.name,
                record_no=index,
                raw=raw,
            )
        )

    return records


def iter_zip_records(path: Path) -> list[SourceRecord]:
    """BAC ZIP内のBACyymmdd.txtを読む。"""
    records: list[SourceRecord] = []

    with zipfile.ZipFile(path) as archive:
        members = []
        for member_name in archive.namelist():
            base_name = Path(member_name).name
            if BAC_TXT_RE.fullmatch(base_name):
                members.append(member_name)

        members.sort(key=lambda value: Path(value).name.upper())

        for member_name in members:
            data = archive.read(member_name)
            lines = data.splitlines()

            for index, raw in enumerate(lines, start=1):
                if raw == b"":
                    continue
                records.append(
                    SourceRecord(
                        source_path=str(path),
                        member_name=member_name,
                        record_no=index,
                        raw=raw,
                    )
                )

    return records


def discover_bac_sources(raw_inputs: list[Path]) -> list[Path]:
    """入力パスからBAC年次ZIP・単日ZIP・展開済みTXTを再帰探索する。"""
    discovered: set[Path] = set()

    for raw_input in raw_inputs:
        if not raw_input.exists():
            raise FileNotFoundError(raw_input)

        candidates: list[Path] = []
        if raw_input.is_dir():
            candidates = list(raw_input.rglob("*"))
        else:
            candidates = [raw_input]

        for candidate in candidates:
            if not candidate.is_file():
                continue

            name = candidate.name
            is_bac_txt = BAC_TXT_RE.fullmatch(name) is not None
            is_annual_zip = BAC_ANNUAL_ZIP_RE.fullmatch(name) is not None
            is_daily_zip = BAC_DAILY_ZIP_RE.fullmatch(name) is not None

            if is_bac_txt or is_annual_zip or is_daily_zip:
                discovered.add(candidate.resolve())

    return sorted(discovered)


def load_targets_csv(path: Path) -> set[RaceTarget]:
    """対象レースCSVを読み込む。

    必須列:
      race_date, venue_code, race_no

    race_dateはYYYY-MM-DDまたはYYYYMMDDを許可する。
    """
    targets: set[RaceTarget] = set()

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"race_date", "venue_code", "race_no"}

        if reader.fieldnames is None:
            raise ExportError("targets CSV has no header")

        missing = required.difference(reader.fieldnames)
        if missing:
            raise ExportError(
                "targets CSV missing columns: " + ", ".join(sorted(missing))
            )

        for line_no, row in enumerate(reader, start=2):
            race_date_value = str(row["race_date"]).strip()
            if re.fullmatch(r"\d{8}", race_date_value):
                race_date_value = normalize_date_yyyymmdd(race_date_value)

            try:
                dt.date.fromisoformat(race_date_value)
            except ValueError as exc:
                raise ExportError(
                    f"targets CSV invalid race_date at line {line_no}: "
                    f"{race_date_value!r}"
                ) from exc

            venue_code = normalize_venue_code(str(row["venue_code"]))

            try:
                race_no = int(str(row["race_no"]).strip())
            except ValueError as exc:
                raise ExportError(
                    f"targets CSV invalid race_no at line {line_no}: "
                    f"{row['race_no']!r}"
                ) from exc

            targets.add(
                RaceTarget(
                    race_date=race_date_value,
                    venue_code=venue_code,
                    race_no=race_no,
                )
            )

    return targets


def parse_optional_date(value: str | None) -> dt.date | None:
    """任意の日付引数をISO日付へ変換する。"""
    if value is None:
        return None

    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ExportError(
            f"invalid date {value!r}; expected YYYY-MM-DD"
        ) from exc


def row_matches(
    row: dict[str, object],
    start_date: dt.date | None,
    end_date: dt.date | None,
    targets: set[RaceTarget] | None,
) -> bool:
    """期間条件・対象レース条件に一致するか判定する。"""
    row_date = dt.date.fromisoformat(str(row["race_date"]))

    if start_date is not None and row_date < start_date:
        return False
    if end_date is not None and row_date > end_date:
        return False

    if targets is not None:
        target = RaceTarget(
            race_date=str(row["race_date"]),
            venue_code=str(row["venue_code"]),
            race_no=int(row["race_no"]),
        )
        if target not in targets:
            return False

    return True


def make_row_key(row: dict[str, object]) -> tuple[str, str, int]:
    """Eval結合キーを生成する。"""
    return (
        str(row["race_date"]),
        str(row["venue_code"]),
        int(row["race_no"]),
    )


def export_rows(
    raw_inputs: list[Path],
    output_path: Path,
    start_date: dt.date | None,
    end_date: dt.date | None,
    targets: set[RaceTarget] | None,
) -> dict[str, int]:
    """BAC Rawを走査し、条件一致するレースをCSVへ出力する。"""
    sources = discover_bac_sources(raw_inputs)
    if not sources:
        raise ExportError("no BAC sources found")

    selected: dict[tuple[str, str, int], dict[str, object]] = {}
    source_record_count = 0
    identical_duplicate_count = 0

    for source in sources:
        if source.suffix.lower() == ".zip":
            records = iter_zip_records(source)
        else:
            records = iter_text_records(source)

        for record in records:
            source_record_count += 1
            row = parse_bac_record(record)

            if not row_matches(row, start_date, end_date, targets):
                continue

            key = make_row_key(row)
            previous = selected.get(key)

            if previous is None:
                selected[key] = row
                continue

            if previous == row:
                identical_duplicate_count += 1
                continue

            raise ExportError(
                "conflicting BAC rows for Eval key "
                f"{key}. Do not guess which revision is correct."
            )

    ordered_rows = sorted(
        selected.values(),
        key=lambda row: (
            str(row["race_date"]),
            str(row["venue_code"]),
            int(row["race_no"]),
        ),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(ordered_rows)

    missing_target_count = 0
    if targets is not None:
        found_targets = set()
        for row in ordered_rows:
            found_targets.add(
                RaceTarget(
                    race_date=str(row["race_date"]),
                    venue_code=str(row["venue_code"]),
                    race_no=int(row["race_no"]),
                )
            )
        missing_target_count = len(targets.difference(found_targets))

    return {
        "source_files": len(sources),
        "source_records": source_record_count,
        "output_rows": len(ordered_rows),
        "identical_duplicates_collapsed": identical_duplicate_count,
        "missing_targets": missing_target_count,
    }


def build_argument_parser() -> argparse.ArgumentParser:
    """CLI引数定義を生成する。"""
    parser = argparse.ArgumentParser(
        description="Export Eval race conditions from JRDB BAC Raw."
    )
    parser.add_argument(
        "--raw",
        type=Path,
        nargs="+",
        required=True,
        help="BAC ZIP/TXT file or directories containing BAC Raw.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
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
        "--targets-csv",
        type=Path,
        help="CSV with race_date,venue_code,race_no.",
    )
    parser.add_argument(
        "--fail-on-missing-target",
        action="store_true",
        help="Exit with error when targets-csv contains races not found in BAC.",
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

        metrics = export_rows(
            raw_inputs=args.raw,
            output_path=args.output,
            start_date=start_date,
            end_date=end_date,
            targets=targets,
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
