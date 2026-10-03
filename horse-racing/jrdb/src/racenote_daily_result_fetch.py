#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch same-day JRA top-3 finishers and payouts for RaceNote settlement.

This is a post-freeze convenience source.  Detailed post-race review continues to
use JRDB SED/HJC.  The default source is Sponichi Keiba Web's daily result page,
which exposes all races on one page and can be re-run while racing is in progress.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass, field
from datetime import date as Date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

VERSION = "racenote-daily-result-fetch-0.1.0"
BASE_URL = "https://keiba.sponichi.co.jp"
RESULT_URL = BASE_URL + "/race_result/{yyyymmdd}"
VENUES = ("札幌", "函館", "福島", "新潟", "東京", "中山", "中京", "京都", "阪神", "小倉")
WAGER_LABELS = {
    "単勝": "win",
    "複勝": "place",
    "枠連": "frame_quinella",
    "馬連": "quinella",
    "ワイド": "wide",
    "馬単": "exacta",
    "三連複": "trio",
    "3連複": "trio",
    "三連単": "trifecta",
    "3連単": "trifecta",
}
RACE_HREF_RE = re.compile(r"/race/(?P<date>\d{8})/(?P<field>\d+)/(?P<race>\d{1,2})(?:\?|$)")
RACE_TITLE_RE = re.compile(r"^\s*(?P<race>\d{1,2})R(?:\s+|$)(?P<name>.*)$")
YEN_RE = re.compile(r"([\d,]+)\s*円")
SETTLEMENT_REQUIRED_WAGERS = ("win", "place", "quinella", "wide", "exacta", "trio", "trifecta")


class DailyResultSource(Protocol):
    def fetch(self, target_date: Date) -> dict[str, Any]: ...


@dataclass
class RaceCard:
    field_id: str
    race_no: int
    href: str
    title: str = ""
    tables: list[list[list[str]]] = field(default_factory=list)


class _SponichiPageParser(HTMLParser):
    """Collect race-card tables without depending on site CSS class names."""

    def __init__(self, yyyymmdd: str) -> None:
        super().__init__(convert_charrefs=True)
        self.yyyymmdd = yyyymmdd
        self.cards: dict[tuple[str, int], RaceCard] = {}
        self.card_order: list[tuple[str, int]] = []
        self.pre_race_text: list[str] = []
        self.all_text: list[str] = []
        self.current_card: tuple[str, int] | None = None

        self._anchor_href: str | None = None
        self._anchor_parts: list[str] = []
        self._in_table = 0
        self._table_rows: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "a":
            self._anchor_href = attrs_dict.get("href")
            self._anchor_parts = []
        elif tag == "table":
            self._in_table += 1
            if self._in_table == 1:
                self._table_rows = []
        elif tag == "tr" and self._in_table:
            self._row = []
        elif tag in {"td", "th"} and self._in_table and self._row is not None:
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        self.all_text.append(text)
        if not self.card_order:
            self.pre_race_text.append(text)
        if self._anchor_href is not None:
            self._anchor_parts.append(text)
        if self._cell_parts is not None:
            self._cell_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell_parts is not None and self._row is not None:
            self._row.append(" ".join(self._cell_parts).strip())
            self._cell_parts = None
        elif tag == "tr" and self._row is not None and self._in_table:
            if self._table_rows is not None and any(self._row):
                self._table_rows.append(self._row)
            self._row = None
        elif tag == "table" and self._in_table:
            if self._in_table == 1 and self._table_rows is not None and self.current_card is not None:
                self.cards[self.current_card].tables.append(self._table_rows)
            self._table_rows = None
            self._in_table -= 1
        elif tag == "a" and self._anchor_href is not None:
            href = self._anchor_href
            text = " ".join(self._anchor_parts).strip()
            match = RACE_HREF_RE.search(href)
            title_match = RACE_TITLE_RE.match(text)
            if match and title_match and match.group("date") == self.yyyymmdd:
                field_id = match.group("field")
                race_no = int(match.group("race"))
                if race_no == int(title_match.group("race")):
                    key = (field_id, race_no)
                    if key not in self.cards:
                        self.cards[key] = RaceCard(field_id=field_id, race_no=race_no, href=href, title=text)
                        self.card_order.append(key)
                    self.current_card = key
            self._anchor_href = None
            self._anchor_parts = []


def _currency_values(text: str) -> list[int]:
    return [int(value.replace(",", "")) for value in YEN_RE.findall(text)]


def _unique_in_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _infer_venue_by_field(parser: _SponichiPageParser) -> dict[str, str]:
    venue_order = _unique_in_order([text for text in parser.pre_race_text if text in VENUES])
    field_order = _unique_in_order([field_id for field_id, _ in parser.card_order])
    if len(venue_order) != len(field_order) or not field_order:
        raise ValueError(
            "スポニチ結果ページから開催場とfieldの対応を確定できませんでした: "
            f"venues={venue_order}, fields={field_order}"
        )
    return dict(zip(field_order, venue_order))


def _find_finishers(card: RaceCard) -> list[dict[str, Any]]:
    finishers: list[dict[str, Any]] = []
    for table in card.tables:
        for row in table:
            if len(row) < 4 or row[0] not in {"1", "2", "3"}:
                continue
            if not row[1].isdigit() or not row[2].isdigit():
                continue
            finishers.append({
                "finish": int(row[0]),
                "frame_no": int(row[1]),
                "horse_no": int(row[2]),
                "horse_name": row[3].strip(),
            })
    # A standard race must have one horse at each of 1st/2nd/3rd.  Dead heats are
    # retained and marked review_required rather than guessed by settlement code.
    return finishers


def _find_raw_payouts(card: RaceCard) -> dict[str, list[int]]:
    payouts = {value: [] for value in dict.fromkeys(WAGER_LABELS.values())}
    for table in card.tables:
        for row in table:
            i = 0
            while i < len(row):
                label = row[i].replace(" ", "")
                wager = WAGER_LABELS.get(label)
                if wager is not None and i + 1 < len(row):
                    payouts[wager].extend(_currency_values(row[i + 1]))
                    i += 2
                else:
                    i += 1
    return payouts


def _payout_entry(combination: tuple[int, ...], payout: int) -> dict[str, Any]:
    return {"combination": list(combination), "payout_jpy": payout}


def _canonical_payouts(finishers: list[dict[str, Any]], raw: dict[str, list[int]]) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    payouts: dict[str, list[dict[str, Any]]] = {key: [] for key in raw}
    warnings: list[str] = []
    by_finish: dict[int, list[dict[str, Any]]] = {place: [] for place in (1, 2, 3)}
    for row in finishers:
        if row["finish"] in by_finish:
            by_finish[row["finish"]].append(row)
    if any(len(by_finish[p]) != 1 for p in (1, 2, 3)):
        warnings.append("1〜3着に同着または欠損があり、払戻組合せを一意に復元できません")
        return payouts, warnings

    first, second, third = (by_finish[p][0] for p in (1, 2, 3))
    h1, h2, h3 = first["horse_no"], second["horse_no"], third["horse_no"]
    f1, f2 = first["frame_no"], second["frame_no"]

    expected_single = {
        "win": (h1,),
        "frame_quinella": tuple(sorted((f1, f2))),
        "quinella": tuple(sorted((h1, h2))),
        "exacta": (h1, h2),
        "trio": tuple(sorted((h1, h2, h3))),
        "trifecta": (h1, h2, h3),
    }
    for wager, combination in expected_single.items():
        values = raw[wager]
        if not values:
            continue
        if len(values) != 1:
            warnings.append(f"{wager} の払戻件数が標準形ではありません: {values}")
            continue
        payouts[wager].append(_payout_entry(combination, values[0]))

    # Sponichi lists place payouts in finish order and wide payouts as 1-2,
    # 1-3, 2-3.  Low-runner races may expose only two place payouts.
    place_horses = (h1, h2, h3)
    if len(raw["place"]) in {2, 3}:
        for horse_no, value in zip(place_horses, raw["place"]):
            payouts["place"].append(_payout_entry((horse_no,), value))
    elif raw["place"]:
        warnings.append(f"place の払戻件数が標準形ではありません: {raw['place']}")

    wide_pairs = (
        tuple(sorted((h1, h2))),
        tuple(sorted((h1, h3))),
        tuple(sorted((h2, h3))),
    )
    if len(raw["wide"]) == 3:
        for combination, value in zip(wide_pairs, raw["wide"]):
            payouts["wide"].append(_payout_entry(combination, value))
    elif raw["wide"]:
        warnings.append(f"wide の払戻件数が標準形ではありません: {raw['wide']}")

    return payouts, warnings


def parse_sponichi_html(html: str, target_date: Date, *, source_url: str | None = None) -> dict[str, Any]:
    yyyymmdd = target_date.strftime("%Y%m%d")
    parser = _SponichiPageParser(yyyymmdd)
    parser.feed(html)
    if not parser.cards:
        raise ValueError("スポニチ結果ページから対象レースを検出できませんでした")

    expected_date_text = target_date.strftime("%Y/%m/%d")
    page_text = " ".join(parser.all_text)
    if expected_date_text not in page_text:
        raise ValueError(f"取得ページの日付を確認できません: expected={expected_date_text}")

    venue_by_field = _infer_venue_by_field(parser)
    races: list[dict[str, Any]] = []
    review_count = 0
    official_count = 0
    pending_count = 0
    for key in parser.card_order:
        card = parser.cards[key]
        finishers = _find_finishers(card)
        raw_payouts = _find_raw_payouts(card)
        has_any_payout = any(raw_payouts.values())
        warnings: list[str] = []
        canonical = {key: [] for key in raw_payouts}
        pending_reason = ""
        if not finishers and not has_any_payout:
            status = "pending"
            pending_reason = "result_not_posted"
            pending_count += 1
        else:
            canonical, warnings = _canonical_payouts(finishers, raw_payouts)
            if warnings:
                status = "review_required"
                review_count += 1
            else:
                missing = [wager for wager in SETTLEMENT_REQUIRED_WAGERS if not canonical[wager]]
                if missing:
                    status = "pending"
                    pending_reason = "payouts_not_complete:" + ",".join(missing)
                    pending_count += 1
                else:
                    status = "official"
                    official_count += 1
        title_match = RACE_TITLE_RE.match(card.title)
        race_name = title_match.group("name").strip() if title_match else ""
        races.append({
            "date": target_date.isoformat(),
            "venue": venue_by_field[card.field_id],
            "race_no": card.race_no,
            "race_name": race_name,
            "status": status,
            "top3": finishers,
            "payouts": canonical,
            "raw_payout_amounts": raw_payouts,
            "warnings": warnings,
            "pending_reason": pending_reason,
            "source_race_url": urljoin(BASE_URL + "/", card.href),
        })

    races.sort(key=lambda row: (VENUES.index(row["venue"]), row["race_no"]))
    overall_status = "complete" if official_count == len(races) else "partial"
    return {
        "schema_version": "RaceNote-SameDay-Result-0.1",
        "fetcher_version": VERSION,
        "target_date": target_date.isoformat(),
        "status": overall_status,
        "source": {
            "provider": "sponichi_keiba_web",
            "url": source_url or RESULT_URL.format(yyyymmdd=yyyymmdd),
        },
        "race_count": len(races),
        "official_race_count": official_count,
        "pending_race_count": pending_count,
        "review_required_race_count": review_count,
        "races": races,
    }


class SponichiDailyResultSource:
    def __init__(self, *, timeout: float = 30.0, retries: int = 3, retry_wait: float = 1.0) -> None:
        self.timeout = timeout
        self.retries = retries
        self.retry_wait = retry_wait

    def _get(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                request = Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; RaceNoteSameDayResult/0.1; personal-research)",
                        "Accept-Language": "ja,en-US;q=0.8",
                    },
                )
                with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - fixed HTTPS source
                    charset = response.headers.get_content_charset() or "utf-8"
                    return response.read().decode(charset, errors="replace")
            except (HTTPError, URLError, TimeoutError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(self.retry_wait * attempt)
        raise RuntimeError(f"スポニチ結果ページを取得できませんでした: {last_error}")

    def fetch(self, target_date: Date) -> dict[str, Any]:
        url = RESULT_URL.format(yyyymmdd=target_date.strftime("%Y%m%d"))
        html = self._get(url)
        payload = parse_sponichi_html(html, target_date, source_url=url)
        payload["source"]["fetched_at"] = datetime.now(timezone.utc).isoformat()
        return payload


def parse_date(value: str) -> Date:
    try:
        return Date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日付は YYYY-MM-DD 形式で指定してください") from exc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", type=parse_date, required=True, help="対象日 YYYY-MM-DD")
    ap.add_argument("--output", type=Path, help="出力JSON。省略時は result_cache/YYYYMMDD_SameDay_Result.json")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--retries", type=int, default=3)
    args = ap.parse_args()

    output = args.output or (Path(__file__).resolve().parents[1] / "result_cache" / f"{args.date:%Y%m%d}_SameDay_Result.json")
    payload = SponichiDailyResultSource(timeout=args.timeout, retries=args.retries).fetch(args.date)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": payload["status"],
        "output": str(output),
        "races": payload["race_count"],
        "official": payload["official_race_count"],
        "pending": payload["pending_race_count"],
        "review_required": payload["review_required_race_count"],
    }, ensure_ascii=False, indent=2))
    return 0 if payload["review_required_race_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
