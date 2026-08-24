#!/usr/bin/env python3
"""JRA結果・払戻CSVの定型検証を行う。"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

REQUIRED_COLUMNS = [
    "日付", "会場", "R", "レース名", "出走頭数",
    "1着馬番", "1着馬名", "2着馬番", "2着馬名", "3着馬番", "3着馬名",
    "単勝", "複勝", "枠連", "ワイド", "馬連", "馬単", "3連複", "3連単",
    "取得元URL", "取得状態", "エラー詳細",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JRA結果・払戻CSVを検証します。")
    parser.add_argument("csv_path", help="検証対象CSV")
    parser.add_argument("--report", help="JSONレポート出力先")
    return parser.parse_args()


def validate(csv_path: Path) -> tuple[dict, bool]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    keys = [(row.get("日付", ""), row.get("会場", ""), row.get("R", "")) for row in rows]
    duplicate_keys = [list(key) for key, count in Counter(keys).items() if count > 1]

    success_rows = [row for row in rows if row.get("取得状態") == "成功"]
    failed_rows = [row for row in rows if row.get("取得状態") != "成功"]

    invalid_field_size_rows = []
    missing_win_rows = []
    missing_place_rows = []
    error_detail_on_success_rows = []
    missing_result_rows = []

    for index, row in enumerate(rows, start=2):
        field_size = row.get("出走頭数", "").strip()
        if not field_size.isdigit() or int(field_size) <= 0:
            invalid_field_size_rows.append(index)
        if not row.get("単勝", "").strip():
            missing_win_rows.append(index)
        if not row.get("複勝", "").strip():
            missing_place_rows.append(index)
        if row.get("取得状態") == "成功" and row.get("エラー詳細", "").strip():
            error_detail_on_success_rows.append(index)
        if any(not row.get(column, "").strip() for column in ("1着馬番", "1着馬名", "2着馬番", "2着馬名", "3着馬番", "3着馬名")):
            missing_result_rows.append(index)

    report = {
        "csv_path": str(csv_path),
        "row_count": len(rows),
        "success_count": len(success_rows),
        "failure_count": len(failed_rows),
        "missing_columns": missing_columns,
        "duplicate_key_count": len(duplicate_keys),
        "duplicate_keys": duplicate_keys,
        "invalid_field_size_count": len(invalid_field_size_rows),
        "invalid_field_size_rows": invalid_field_size_rows,
        "missing_win_count": len(missing_win_rows),
        "missing_win_rows": missing_win_rows,
        "missing_place_count": len(missing_place_rows),
        "missing_place_rows": missing_place_rows,
        "error_detail_on_success_count": len(error_detail_on_success_rows),
        "error_detail_on_success_rows": error_detail_on_success_rows,
        "missing_result_count": len(missing_result_rows),
        "missing_result_rows": missing_result_rows,
    }

    ok = (
        not missing_columns
        and len(rows) > 0
        and len(failed_rows) == 0
        and len(duplicate_keys) == 0
        and len(invalid_field_size_rows) == 0
        and len(missing_win_rows) == 0
        and len(missing_place_rows) == 0
        and len(error_detail_on_success_rows) == 0
        and len(missing_result_rows) == 0
    )
    report["validation_status"] = "success" if ok else "failure"
    return report, ok


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        raise SystemExit(f"CSVが見つかりません: {csv_path}")

    report, ok = validate(csv_path)
    report_text = json.dumps(report, ensure_ascii=False, indent=2)
    print(report_text)

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text + "\n", encoding="utf-8")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
