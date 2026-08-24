#!/usr/bin/env python3
"""指定日または指定期間のJRAレース結果・払戻をCSVへ出力する。"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://sports.yahoo.co.jp"
SCHEDULE_URL = BASE_URL + "/keiba/schedule/monthly?year={year}&month={month}"
RACE_LIST_URL = BASE_URL + "/keiba/race/list/{event_id}"
RESULT_URL = BASE_URL + "/keiba/race/result/{race_id}"
REQUEST_INTERVAL_SECONDS = 0.7

VENUE_NAMES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}
PAYOUT_TYPES = ("単勝", "複勝", "枠連", "ワイド", "馬連", "馬単", "3連複", "3連単")
CSV_FIELDS = (
    "日付", "会場", "R", "レース名", "出走頭数",
    "1着馬番", "1着馬名", "2着馬番", "2着馬名", "3着馬番", "3着馬名",
    "単勝", "複勝", "枠連", "ワイド", "馬連", "馬単", "3連複", "3連単",
    "取得元URL", "取得状態", "エラー詳細",
)

@dataclass(frozen=True)
class Race:
    race_id: str
    venue: str
    race_no: int

def parse_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y%m%d")
    except ValueError as error:
        raise argparse.ArgumentTypeError("日付は YYYY-MM-DD 形式で指定してください。") from error

def resolve_target_dates(args: argparse.Namespace, parser: argparse.ArgumentParser) -> list[str]:
    if args.dates:
        return sorted(set(args.dates))
    if args.date_from > args.date_to:
        parser.error("--from は --to 以前の日付を指定してください。")
    start = datetime.strptime(args.date_from, "%Y%m%d").date()
    end = datetime.strptime(args.date_to, "%Y%m%d").date()
    return [
        start.fromordinal(ordinal).strftime("%Y%m%d")
        for ordinal in range(start.toordinal(), end.toordinal() + 1)
    ]

def output_file_name(target_dates: list[str]) -> str:
    if len(target_dates) == 1:
        return f"{target_dates[0]}_JRA結果払戻.csv"
    return f"{target_dates[0]}-{target_dates[-1]}_JRA結果払戻.csv"

def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; JRA-Result-Collector/1.0; personal-research)",
        "Accept-Language": "ja,en-US;q=0.8",
    })
    retry = Retry(
        total=3, connect=3, read=3, backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",), raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session

def get_soup(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.content, "html.parser")

def normalized_text(element: Tag) -> str:
    return " ".join(element.stripped_strings).replace("\u3000", " ").strip()

def cell_texts(row: Tag) -> list[str]:
    return [normalized_text(cell) for cell in row.find_all(["th", "td"], recursive=False)]

def find_events(session: requests.Session, target_date: str) -> list[str]:
    schedule_url = SCHEDULE_URL.format(year=target_date[:4], month=int(target_date[4:6]))
    soup = get_soup(session, schedule_url)
    target_day = str(int(target_date[6:8]))
    event_ids: set[str] = set()
    pattern = re.compile(r"^/keiba/race/list/(\d{8})$")

    for anchor in soup.find_all("a", href=True):
        match = pattern.match(anchor["href"])
        if match is None:
            continue
        row = anchor.find_parent("tr")
        date_cell = row.find("td", class_=re.compile(r"--date")) if row else None
        if date_cell is None:
            continue
        day_match = re.search(r"(\d+)日", normalized_text(date_cell))
        if day_match and day_match.group(1) == target_day:
            event_ids.add(match.group(1))
    return sorted(event_ids)

def find_races(session: requests.Session, target_date: str, interval: float) -> list[Race]:
    races: dict[str, Race] = {}
    pattern = re.compile(r"^/keiba/race/index/(\d{10})$")
    for event_id in find_events(session, target_date):
        soup = get_soup(session, RACE_LIST_URL.format(event_id=event_id))
        for anchor in soup.find_all("a", href=True):
            match = pattern.match(anchor["href"])
            if match is None:
                continue
            race_id = match.group(1)
            venue_code = race_id[2:4]
            if venue_code not in VENUE_NAMES:
                continue
            races[race_id] = Race(race_id, VENUE_NAMES[venue_code], int(race_id[-2:]))
        time.sleep(max(0, interval))
    return sorted(races.values(), key=lambda item: (item.venue, item.race_no))

def parse_finishers(soup: BeautifulSoup) -> tuple[str, list[tuple[str, str]]]:
    table = None
    for candidate in soup.find_all("table"):
        headers = cell_texts(candidate.find("tr")) if candidate.find("tr") else []
        if headers[:3] == ["着順", "枠番", "馬番"] and len(headers) >= 4 and headers[3].startswith("馬名"):
            table = candidate
            break
    if table is None:
        raise ValueError("レース結果表が見つかりませんでした。")

    race_name_element = soup.find("h2", class_=re.compile(r"predictRaceInfo__title"))
    race_name = normalized_text(race_name_element) if race_name_element else ""

    finishers: list[tuple[str, str]] = []
    for row in table.find_all("tr"):
        cells = cell_texts(row)
        raw_cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) < 4 or not re.fullmatch(r"\d+", cells[0]):
            continue
        horse_number = cells[2]
        horse_link = raw_cells[3].find("a") if len(raw_cells) > 3 else None
        horse_name = normalized_text(horse_link or raw_cells[3])
        if not re.fullmatch(r"\d+", horse_number):
            continue
        finishers.append((horse_number, horse_name))
        if len(finishers) == 3:
            break

    if len(finishers) < 3:
        raise ValueError("1〜3着を十分に取得できませんでした。")
    return race_name, finishers

def parse_field_size(soup: BeautifulSoup) -> int:
    result_table = None
    for candidate in soup.find_all("table"):
        headers = cell_texts(candidate.find("tr")) if candidate.find("tr") else []
        if headers[:3] == ["着順", "枠番", "馬番"]:
            result_table = candidate
            break
    if result_table is None:
        raise ValueError("出走頭数の取得元となるレース結果表が見つかりませんでした。")

    horse_numbers: set[str] = set()
    for row in result_table.find_all("tr"):
        cells = cell_texts(row)
        if len(cells) < 3:
            continue
        horse_number = cells[2]
        if re.fullmatch(r"\d+", horse_number):
            horse_numbers.add(horse_number)

    if not horse_numbers:
        raise ValueError("枠順確定時の出走頭数を取得できませんでした。")
    return len(horse_numbers)

def parse_payouts(soup: BeautifulSoup) -> dict[str, str]:
    tables = [table for table in soup.find_all("table") if "hr-tableLeftTop" in (table.get("class") or [])]
    if not tables:
        raise ValueError("払戻表が見つかりませんでした。")

    payouts = {ticket: "" for ticket in PAYOUT_TYPES}
    for table in tables:
        current_ticket = ""
        for row in table.find_all("tr"):
            cells = cell_texts(row)
            if not cells:
                continue
            if cells[0] in payouts:
                current_ticket = cells.pop(0)
            if current_ticket not in payouts or len(cells) < 2:
                continue
            value = f"{cells[0]} {cells[1]}"
            payouts[current_ticket] = " / ".join(filter(None, [payouts[current_ticket], value]))
    return payouts

def make_row(target_date: str, race: Race, session: requests.Session) -> dict[str, str]:
    source_url = RESULT_URL.format(race_id=race.race_id)
    row = {field: "" for field in CSV_FIELDS}
    row.update({
        "日付": f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:]}",
        "会場": race.venue,
        "R": str(race.race_no),
        "取得元URL": source_url,
    })
    try:
        soup = get_soup(session, source_url)
        race_name, finishers = parse_finishers(soup)
        field_size = parse_field_size(soup)
        payouts = parse_payouts(soup)
        row["レース名"] = race_name
        row["出走頭数"] = str(field_size)
        for place, (horse_number, horse_name) in enumerate(finishers, start=1):
            row[f"{place}着馬番"] = horse_number
            row[f"{place}着馬名"] = horse_name
        row.update(payouts)
        row["取得状態"] = "成功"
    except (requests.RequestException, ValueError) as error:
        row["取得状態"] = "失敗"
        row["エラー詳細"] = str(error)
    return row

def write_csv(rows: Iterable[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

def main() -> int:
    parser = argparse.ArgumentParser(description="指定日または指定期間のJRA結果・払戻を1つのCSVへ出力します。")
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument("--dates", nargs="+", type=parse_date, help="対象日（複数指定可、YYYY-MM-DD ...）")
    date_group.add_argument("--from", dest="date_from", type=parse_date, help="対象開始日（YYYY-MM-DD、--to とセット）")
    parser.add_argument("--to", dest="date_to", type=parse_date, help="対象終了日（YYYY-MM-DD、--from とセット）")
    parser.add_argument("--output-dir", default="output", help="CSV出力先ディレクトリ")
    parser.add_argument("--interval", type=float, default=REQUEST_INTERVAL_SECONDS, help="アクセス間隔（秒）")
    args = parser.parse_args()

    if (args.date_from is None) != (args.date_to is None):
        parser.error("--from と --to はセットで指定してください。")
    target_dates = resolve_target_dates(args, parser)

    session = create_session()
    rows: list[dict[str, str]] = []
    skipped_dates: list[str] = []

    for target_date in target_dates:
        try:
            races = find_races(session, target_date, args.interval)
        except requests.RequestException as error:
            print(f"{target_date}: レース一覧を取得できませんでした: {error}", file=sys.stderr)
            return 2

        if not races:
            if args.date_from is not None:
                skipped_dates.append(target_date)
                print(f"{target_date}: JRA開催なしのためスキップします。", file=sys.stderr)
                continue
            print(f"{target_date}: JRA開催を検出できませんでした。日付または取得元の掲載状況を確認してください。", file=sys.stderr)
            return 3

        for index, race in enumerate(races, start=1):
            print(f"{target_date} [{index}/{len(races)}] {race.venue} {race.race_no}R を取得中", file=sys.stderr)
            rows.append(make_row(target_date, race, session))
            if index < len(races):
                time.sleep(max(0, args.interval))

    output_path = Path(args.output_dir) / output_file_name(target_dates)
    write_csv(rows, output_path)
    succeeded = sum(row["取得状態"] == "成功" for row in rows)
    if skipped_dates:
        print("開催なしでスキップ: " + ", ".join(skipped_dates), file=sys.stderr)
    print(f"出力完了: {output_path}（成功 {succeeded}/{len(rows)}）")
    return 0 if succeeded == len(rows) else 1

if __name__ == "__main__":
    raise SystemExit(main())
