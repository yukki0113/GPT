"""Apply the ForwardTrial publication deadline gate to a sales-selection CSV.

This module does not change prediction judgment, exacta targets, sales score, or
frozen timestamps. It only prevents races whose official scheduled closing time
has already been reached at sales freeze from being assigned to paid/free
publication slots. Expired targets remain in the CSV as CSV-only for audit and
ForwardTrial analysis.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
SALES_COLUMNS = [
    "日付","会場","R","試行仕様Ver","正式判定","1着軸","2着本線","2着押さえ",
    "2連単1点対象","2連単1点","軸警戒","比較支持項目数","全国勝率差",
    "2着候補分離度","販売スコア","内部販売評価","掲載区分","選別理由",
    "予想確定日時","販売選別確定日時","結果参照状態",
]


class DeadlineGateValidationError(ValueError):
    pass


def parse_freeze(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise DeadlineGateValidationError("販売選別確定日時 is required")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise DeadlineGateValidationError(f"invalid 販売選別確定日時: {text}") from exc
    if dt.tzinfo is None:
        raise DeadlineGateValidationError("販売選別確定日時 must include timezone offset")
    return dt.astimezone(JST)


def parse_deadline(date_text: str, time_text: str) -> datetime:
    date_text = str(date_text or "").strip()
    time_text = str(time_text or "").strip()
    if len(date_text) == 8 and date_text.isdigit():
        date_text = f"{date_text[:4]}-{date_text[4:6]}-{date_text[6:]}"
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(f"{date_text} {time_text}", fmt).replace(tzinfo=JST)
        except ValueError:
            pass
    raise DeadlineGateValidationError(f"invalid official deadline: {date_text} {time_text}")


def build_deadlines(racecard_rows):
    deadlines = {}
    for row in racecard_rows:
        venue = str(row.get("会場", "")).strip()
        race = str(row.get("R", "")).strip()
        closing = str(row.get("締切時刻", "")).strip()
        date = str(row.get("日付", "")).strip()
        if not venue or not race or not closing or not date:
            raise DeadlineGateValidationError("racecard requires 日付/会場/R/締切時刻")
        key = (venue, int(race))
        deadline = parse_deadline(date, closing)
        if key in deadlines and deadlines[key] != deadline:
            raise DeadlineGateValidationError(f"deadline mismatch for {venue} {race}R")
        deadlines[key] = deadline
    return deadlines


def sales_sort_key(row):
    return (
        -int(row["販売スコア"]),
        -float(row["2着候補分離度"]),
        row["会場"],
        int(row["R"]),
    )


def apply_deadline_gate(racecard_rows, sales_rows):
    deadlines = build_deadlines(racecard_rows)
    eligible = []
    expired = []

    for row in sales_rows:
        if row.get("結果参照状態") != "未参照":
            raise DeadlineGateValidationError("deadline gate is pre-result only")
        if row.get("2連単1点対象") != "対象":
            row["掲載区分"] = "対象外"
            row["内部販売評価"] = ""
            row["選別理由"] = "2連単1点対象条件を満たさないため販売選別対象外。"
            continue

        key = (str(row["会場"]).strip(), int(row["R"]))
        if key not in deadlines:
            raise DeadlineGateValidationError(f"missing deadline for {key[0]} {key[1]}R")
        freeze = parse_freeze(row.get("販売選別確定日時") or row.get("予想確定日時"))
        deadline = deadlines[key]
        if freeze < deadline:
            eligible.append(row)
        else:
            expired.append((row, deadline, freeze))

    eligible.sort(key=sales_sort_key)
    for rank, row in enumerate(eligible, 1):
        if rank <= 6:
            listing = "有料"
            internal = "S" if int(row["販売スコア"]) >= 7 else "A"
        elif rank <= 9:
            listing = "無料"
            internal = "A-"
        else:
            listing = "CSVのみ"
            internal = "A-"
        row["掲載区分"] = listing
        row["内部販売評価"] = internal
        row["選別理由"] = (
            f"締切前の2連単1点対象。掲載可能販売順位{rank}位。"
            f"販売スコア={row['販売スコア']}、"
            f"2着候補分離度={float(row['2着候補分離度']):.6f}。"
            f"固定順位規則により{listing}。"
        )

    for row, deadline, freeze in expired:
        row["掲載区分"] = "CSVのみ"
        row["内部販売評価"] = "A-"
        row["選別理由"] = (
            f"締切済み掲載除外。公式締切={deadline.strftime('%H:%M')}、"
            f"販売選別確定={freeze.strftime('%H:%M:%S')}。"
            "2連単1点対象・販売スコアは検証用に保持し、有料・無料には掲載しない。"
        )

    return {
        "sales": sales_rows,
        "eligible_target_count": len(eligible),
        "expired_target_count": len(expired),
        "paid_count": sum(row.get("掲載区分") == "有料" for row in sales_rows),
        "free_count": sum(row.get("掲載区分") == "無料" for row in sales_rows),
        "csv_only_count": sum(row.get("掲載区分") == "CSVのみ" for row in sales_rows),
    }


def read_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), reader.fieldnames or []


def write_sales(path, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SALES_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in SALES_COLUMNS})


def run(racecard_path, sales_path, output_path):
    racecard_rows, racecard_columns = read_csv(racecard_path)
    sales_rows, sales_columns = read_csv(sales_path)
    if "締切時刻" not in racecard_columns:
        raise DeadlineGateValidationError("racecard missing 締切時刻")
    missing = set(SALES_COLUMNS) - set(sales_columns)
    if missing:
        raise DeadlineGateValidationError(f"sales missing columns: {sorted(missing)}")
    result = apply_deadline_gate(racecard_rows, sales_rows)
    write_sales(output_path, result["sales"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--racecard", required=True, type=Path)
    parser.add_argument("--sales", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.racecard, args.sales, args.output)
    print(
        f"eligible={result['eligible_target_count']} expired={result['expired_target_count']} "
        f"paid={result['paid_count']} free={result['free_count']} csv_only={result['csv_only_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
