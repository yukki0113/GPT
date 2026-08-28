#!/usr/bin/env python3
"""BOAT RACE公式結果を事前予想CSVと突合して監査可能なCSVへ出力する。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import logging
import os
import re
import sys
import tempfile
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from lxml import html


JST = timezone(timedelta(hours=9))
BASE_URL = "https://www.boatrace.jp/owpc/pc/race/raceresult"
USER_AGENT = "Mozilla/5.0 (compatible; BOATRACEOfficialResultAudit/1.0)"
MAX_HTML_BYTES = 5 * 1024 * 1024

VENUE_CODES = {
    "桐生": "01", "戸田": "02", "江戸川": "03", "平和島": "04",
    "多摩川": "05", "浜名湖": "06", "蒲郡": "07", "常滑": "08",
    "津": "09", "三国": "10", "びわこ": "11", "住之江": "12",
    "尼崎": "13", "鳴門": "14", "丸亀": "15", "児島": "16",
    "宮島": "17", "徳山": "18", "下関": "19", "若松": "20",
    "芦屋": "21", "福岡": "22", "唐津": "23", "大村": "24",
}

TICKET_ALIASES = {
    "3連単": "3連単", "三連単": "3連単",
    "3連複": "3連複", "三連複": "3連複",
    "2連単": "2連単", "二連単": "2連単",
    "2連複": "2連複", "二連複": "2連複",
    "拡連複": "拡連複", "ワイド": "拡連複",
    "単勝": "単勝", "複勝": "複勝",
}
ORDERED_TYPES = {"3連単", "2連単"}
UNORDERED_TYPES = {"3連複", "2連複", "拡連複"}
ARITY = {"3連単": 3, "3連複": 3, "2連単": 2, "2連複": 2,
         "拡連複": 2, "単勝": 1, "複勝": 1}

OUTPUT_COLUMNS = [
    "日付", "会場", "R", "判定", "確定着順",
    "公式3連単", "公式3連単払戻", "公式3連複", "公式3連複払戻",
    "公式2連単", "公式2連単払戻", "公式2連複", "公式2連複払戻",
    "公式拡連複", "公式単勝", "公式複勝",
    "主推奨購入予定額", "主推奨返還額", "主推奨返還後投資額",
    "主推奨的中", "主推奨的中買い目", "主推奨払戻",
    "保険購入予定額", "保険返還額", "保険返還後投資額",
    "保険的中", "保険的中買い目", "保険払戻",
    "参考購入予定額", "参考返還額", "参考返還後投資額",
    "参考的中", "参考的中買い目", "参考払戻",
    "着順詳細", "返還艇", "欠場艇", "失格艇", "事故艇", "中止", "不成立", "備考",
    "取得状態", "公式URL", "HTTPステータス", "HTTP取得日時",
    "HTML_SHA256", "結果確認日時", "エラー内容",
]


class InputError(Exception):
    pass


class ParseError(Exception):
    pass


@dataclass
class FetchData:
    content: bytes
    url: str
    fetched_at: str
    http_status: int
    sha256: str
    source: str


@dataclass
class OfficialResult:
    venue: str = ""
    date_label: str = ""
    race_no: int | None = None
    finish_order: list[str] = field(default_factory=list)
    finish_rows: list[dict] = field(default_factory=list)
    payouts: dict[str, list[dict]] = field(default_factory=dict)
    special_payouts: dict[str, int] = field(default_factory=dict)
    refunded_boats: list[str] = field(default_factory=list)
    absent_boats: list[str] = field(default_factory=list)
    disqualified_boats: list[str] = field(default_factory=list)
    incident_boats: list[str] = field(default_factory=list)
    cancelled: bool = False
    invalid: bool = False
    remarks: str = ""
    determined: bool = False


def now_jst() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def normalize_space(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").split())


def text_of(node) -> str:
    return normalize_space(" ".join(node.itertext()))


def parse_date(value: str) -> datetime:
    value = unicodedata.normalize("NFKC", (value or "").strip())
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise InputError(f"日付形式が不正です: {value!r}")


def parse_race_no(value: str) -> int:
    value = unicodedata.normalize("NFKC", (value or "").strip()).upper()
    m = re.fullmatch(r"(\d{1,2})R?", value)
    if not m or not 1 <= int(m.group(1)) <= 12:
        raise InputError(f"Rが不正です: {value!r}")
    return int(m.group(1))


def official_url(date_value: datetime, venue_code: str, race_no: int) -> str:
    return (f"{BASE_URL}?rno={race_no}&jcd={venue_code}"
            f"&hd={date_value.strftime('%Y%m%d')}")


def normalize_ticket_type(value: str) -> str:
    key = unicodedata.normalize("NFKC", (value or "").strip()).replace(" ", "")
    if not key:
        return ""
    if key not in TICKET_ALIASES:
        raise InputError(f"未対応の券種です: {value!r}")
    return TICKET_ALIASES[key]


def canonical_bet(ticket_type: str, boats: Iterable[str]) -> str:
    boats = tuple(str(x) for x in boats)
    if (len(boats) != ARITY[ticket_type]
            or any(not re.fullmatch(r"[1-6]", x) for x in boats)):
        raise InputError(f"{ticket_type}の艇番数が不正です: {boats}")
    if len(set(boats)) != len(boats):
        raise InputError(f"同一艇を重複指定した買い目です: {boats}")
    if ticket_type in UNORDERED_TYPES:
        boats = tuple(sorted(boats, key=int))
    separator = "-" if ticket_type in ORDERED_TYPES else "="
    return separator.join(boats) if len(boats) > 1 else boats[0]


def _expand_arrow_expression(ticket_type: str, expr: str) -> list[str]:
    expr = expr.strip()
    if "⇔" in expr:
        left, right = expr.split("⇔", 1)
        right_parts = right.split("→")
        if len(right_parts) < 2:
            raise InputError(f"⇔表記を展開できません: {expr!r}")
        first_right = right_parts[0]
        tail = "→".join(right_parts[1:])
        return (_expand_arrow_expression(ticket_type, f"{left}→{first_right}→{tail}") +
                _expand_arrow_expression(ticket_type, f"{first_right}→{left}→{tail}"))

    parts = expr.split("→")
    if len(parts) == 1 and "-" in expr:
        parts = expr.split("-")
    if len(parts) == 1 and "=" in expr:
        parts = expr.split("=")
    if len(parts) != ARITY[ticket_type]:
        raise InputError(f"{ticket_type}として展開できません: {expr!r}")
    groups = []
    for part in parts:
        values = [x for x in re.split(r"[,、]", part) if x]
        if not values or any(not re.fullmatch(r"[1-6]", x) for x in values):
            raise InputError(f"艇番表記が不正です: {expr!r}")
        groups.append(values)
    bets = []
    for combo in itertools.product(*groups):
        if len(set(combo)) == len(combo):
            bets.append(canonical_bet(ticket_type, combo))
    return bets


def expand_bets(ticket_type_value: str, bet_text: str) -> list[str]:
    ticket_type = normalize_ticket_type(ticket_type_value)
    normalized = unicodedata.normalize("NFKC", bet_text or "")
    normalized = normalized.replace("⇒", "→").replace("->", "→")
    normalized = re.sub(r"\s+", "", normalized)
    if not ticket_type and not normalized:
        return []
    if not ticket_type or not normalized:
        raise InputError("券種と買い目の片方だけが入力されています")
    expressions = [x for x in re.split(r"[／/;；\n]+", normalized) if x]
    expanded: list[str] = []
    for expr in expressions:
        if ARITY[ticket_type] == 1:
            values = [x for x in re.split(r"[,、]", expr) if x]
            for value in values:
                expanded.append(canonical_bet(ticket_type, [value]))
        else:
            expanded.extend(_expand_arrow_expression(ticket_type, expr))
    return list(dict.fromkeys(expanded))


def parse_money(value: str) -> int:
    digits = re.sub(r"[^0-9]", "", unicodedata.normalize("NFKC", value or ""))
    if not digits:
        raise ParseError(f"払戻金を数値化できません: {value!r}")
    return int(digits)


def find_table_by_headers(doc, required: set[str]):
    for table in doc.xpath("//table"):
        headers = {text_of(x) for x in table.xpath(".//thead//th") if text_of(x)}
        if required.issubset(headers):
            return table
    return None


def validate_page_identity(doc, expected_venue: str, expected_date: datetime,
                           expected_race: int, expected_url: str) -> tuple[str, str, int]:
    venues = [normalize_space(x) for x in doc.xpath(
        '//*[contains(concat(" ", normalize-space(@class), " "), " heading2_area ")]//img/@alt')]
    if expected_venue not in venues:
        raise ParseError(f"公式ページの会場不一致: expected={expected_venue}, actual={venues}")

    active_dates = [text_of(x) for x in doc.xpath(
        '//*[contains(concat(" ", normalize-space(@class), " "), " is-active2 ")]')]
    expected_label = f"{expected_date.month}月{expected_date.day}日"
    if not any(expected_label in x for x in active_dates):
        raise ParseError(f"公式ページの日付不一致: expected={expected_label}, actual={active_dates}")

    expected_query = {k: v[0] for k, v in parse_qs(urlparse(expected_url).query).items()}
    matched = []
    selected = []
    for anchor in doc.xpath(f'//a[normalize-space()="{expected_race}R"]'):
        href = anchor.get("href", "")
        query = {k: v[0] for k, v in parse_qs(urlparse(href).query).items()}
        if query == expected_query:
            matched.append(anchor)
            parent_class = (anchor.getparent().get("class") or "").split()
            if "is-thColor2" not in parent_class:
                selected.append(anchor)
    if not matched or not selected:
        raise ParseError(f"公式ページの選択R不一致: expected={expected_race}R")
    return expected_venue, expected_label, expected_race


def parse_official_html(content: bytes, expected_venue: str, expected_date: datetime,
                        expected_race: int, expected_url: str) -> OfficialResult:
    try:
        doc = html.fromstring(content)
    except Exception as exc:
        raise ParseError(f"HTMLを解析できません: {exc}") from exc

    venue, date_label, race_no = validate_page_identity(
        doc, expected_venue, expected_date, expected_race, expected_url)
    result = OfficialResult(venue=venue, date_label=date_label, race_no=race_no)

    finish_table = find_table_by_headers(doc, {"着", "枠", "ボートレーサー"})
    numeric_finishes: list[tuple[int, str]] = []
    if finish_table is not None:
        for row in finish_table.xpath(".//tbody/tr"):
            cells = row.xpath("./td")
            if len(cells) < 2:
                continue
            rank = text_of(cells[0])
            boat = text_of(cells[1])
            if not re.fullmatch(r"[1-6]", boat):
                continue
            result.finish_rows.append({"rank": rank, "boat": boat})
            rank_ascii = unicodedata.normalize("NFKC", rank)
            if re.fullmatch(r"[1-6]", rank_ascii):
                numeric_finishes.append((int(rank_ascii), boat))
            if "欠" in rank:
                result.absent_boats.append(boat)
            if "失" in rank or "妨" in rank:
                result.disqualified_boats.append(boat)
            if any(mark in rank for mark in ("転", "落", "沈", "不完走")):
                result.incident_boats.append(boat)

    finish_boats = [x["boat"] for x in result.finish_rows]
    if len(finish_boats) != len(set(finish_boats)):
        raise ParseError(f"着順表に同一艇が重複しています: {finish_boats}")
    numeric_ranks = [x[0] for x in numeric_finishes]
    if len(numeric_ranks) != len(set(numeric_ranks)):
        raise ParseError(f"着順表に同一着順が重複しています: {numeric_ranks}")
    result.finish_order = [boat for _, boat in sorted(numeric_finishes)]

    payout_table = find_table_by_headers(doc, {"勝式", "組番", "払戻金"})
    if payout_table is not None:
        current_type = ""
        for row in payout_table.xpath(".//tbody/tr"):
            cells = row.xpath("./td")
            if not cells:
                continue
            first_text = text_of(cells[0])
            try:
                maybe_type = normalize_ticket_type(first_text)
            except InputError:
                maybe_type = ""
            if maybe_type:
                current_type = maybe_type
            if not current_type:
                continue
            row_text = text_of(row)
            special_match = re.search(r"特払い[^0-9]*([0-9][0-9,]*)\s*円?", row_text)
            if special_match:
                payout = parse_money(special_match.group(1))
                if payout <= 0:
                    raise ParseError(
                        f"公式特払いが0円以下です: 券種={current_type}, 払戻={payout}")
                if current_type in result.special_payouts:
                    raise ParseError(f"公式特払いが重複しています: 券種={current_type}")
                result.special_payouts[current_type] = payout
                continue
            number_nodes = row.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " numberSet1_number ")]')
            boats = [text_of(x) for x in number_nodes if re.fullmatch(r"[1-6]", text_of(x))]
            payout_nodes = row.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " is-payout1 ")]')
            if not payout_nodes:
                continue
            try:
                payout = parse_money(text_of(payout_nodes[0]))
            except ParseError:
                continue
            if payout <= 0:
                raise ParseError(
                    f"公式払戻が0円以下です: 券種={current_type}, 払戻={payout}")
            if not boats:
                continue
            try:
                combination = canonical_bet(current_type, boats)
            except InputError:
                continue
            result.payouts.setdefault(current_type, []).append(
                {"combination": combination, "payout": payout})

    for ticket_type, payout_rows in result.payouts.items():
        combinations = [x["combination"] for x in payout_rows]
        if len(combinations) != len(set(combinations)):
            raise ParseError(
                f"公式払戻に同一組番が重複しています: 券種={ticket_type}, 組番={combinations}")
        if ticket_type in result.special_payouts:
            raise ParseError(f"通常払戻と特払いが同一勝式に併存しています: 券種={ticket_type}")

    refund_table = find_table_by_headers(doc, {"返還"})
    if refund_table is not None:
        boats = [text_of(x) for x in refund_table.xpath(
            './/*[contains(concat(" ", normalize-space(@class), " "), " numberSet1_number ")]')]
        result.refunded_boats = list(dict.fromkeys(x for x in boats if re.fullmatch(r"[1-6]", x)))

    remarks_table = find_table_by_headers(doc, {"備考"})
    if remarks_table is not None:
        body = remarks_table.xpath(".//tbody")
        result.remarks = text_of(body[0]) if body else ""

    result_text = normalize_space(" ".join(
        text_of(x) for x in (finish_table, payout_table, remarks_table) if x is not None))
    result.cancelled = "中止" in result.remarks or "レース中止" in result_text
    # 公式結果ページでは、レース不成立時に備考ではなく各勝式の組番欄へ
    # 「不成立」と表示されるケースがある。そのためページ全体の公式表示を判定する。
    result.invalid = "不成立" in result_text
    result.determined = bool(result.finish_order and (result.payouts or result.special_payouts))
    return result


def cache_paths(cache_dir: Path, date_value: datetime, venue_code: str,
                race_no: int) -> tuple[Path, Path]:
    base = cache_dir / date_value.strftime("%Y%m%d") / venue_code
    return base / f"{race_no}R.html", base / f"{race_no}R.meta.json"


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """同一ディレクトリ内の一時ファイルから置換し、途中書込みを残さない。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=path.parent, prefix=f".{path.name}.",
                suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    atomic_write_bytes(path, content.encode(encoding))


def load_cache(html_path: Path, meta_path: Path, expected_url: str) -> FetchData:
    if not html_path.exists() or not meta_path.exists():
        raise FileNotFoundError(f"キャッシュがありません: {html_path}")
    content = html_path.read_bytes()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise ParseError(f"キャッシュメタデータがJSONオブジェクトではありません: {meta_path}")
    digest = hashlib.sha256(content).hexdigest()
    if meta.get("url") != expected_url:
        raise ParseError(f"キャッシュURL不一致: {meta.get('url')}")
    if meta.get("sha256") != digest:
        raise ParseError(f"キャッシュハッシュ不一致: {html_path}")
    if meta.get("byte_length") != len(content):
        raise ParseError(
            f"キャッシュバイト数不一致: meta={meta.get('byte_length')}, actual={len(content)}")
    try:
        http_status = int(meta.get("http_status", 0))
    except (TypeError, ValueError) as exc:
        raise ParseError(f"キャッシュHTTPステータス不正: {meta.get('http_status')!r}") from exc
    if http_status != 200:
        raise ParseError(f"キャッシュHTTPステータス不正: {http_status}")
    fetched_at = str(meta.get("fetched_at", "")).strip()
    try:
        parsed_at = datetime.fromisoformat(fetched_at)
    except ValueError as exc:
        raise ParseError(f"キャッシュ取得日時不正: {fetched_at!r}") from exc
    if parsed_at.tzinfo is None:
        raise ParseError(f"キャッシュ取得日時にタイムゾーンがありません: {fetched_at!r}")
    return FetchData(content, expected_url, fetched_at, http_status, digest, "cache")


def fetch_official(url: str, html_path: Path, meta_path: Path, timeout: float,
                   retry: int) -> FetchData:
    last_exc: Exception | None = None
    attempts_made = 0
    for attempt in range(retry + 1):
        attempts_made = attempt + 1
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
            with urlopen(request, timeout=timeout) as response:
                content = response.read(MAX_HTML_BYTES + 1)
                status = int(response.status)
                final_url = response.url
                content_type = response.headers.get("Content-Type", "")
            fetched_at = now_jst()
            if status != 200:
                raise URLError(f"HTTP {status}")
            if "text/html" not in content_type.lower():
                raise URLError(f"Content-TypeがHTMLではありません: {content_type}")
            if final_url != url:
                raise URLError(f"公式URLからリダイレクトされました: {final_url}")
            if len(content) > MAX_HTML_BYTES:
                raise URLError(f"公式ページの応答が上限を超えました: {len(content)} bytes超")
            digest = hashlib.sha256(content).hexdigest()
            if not content:
                raise URLError("公式ページの応答本文が空です")
            meta = {"url": url, "fetched_at": fetched_at, "http_status": status,
                    "sha256": digest, "byte_length": len(content)}
            # HTMLを先に、メタデータを後に原子的置換する。中断時に世代がずれても、
            # 次回のSHA-256/byte_length検査で必ず失敗し、誤って成功扱いしない。
            atomic_write_bytes(html_path, content)
            atomic_write_text(meta_path, json.dumps(meta, ensure_ascii=False, indent=2))
            return FetchData(content, url, fetched_at, status, digest, "network")
        except HTTPError as exc:
            last_exc = exc
            if exc.code not in {408, 425, 429, 500, 502, 503, 504}:
                break
            if attempt < retry:
                time.sleep(min(2 ** attempt, 8))
        except (URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < retry:
                time.sleep(min(2 ** attempt, 8))
    raise URLError(f"公式ページ取得失敗（{attempts_made}回試行）: {last_exc}")


def acquire(url: str, html_path: Path, meta_path: Path, args) -> FetchData:
    if args.cache_only:
        return load_cache(html_path, meta_path, url)
    if args.use_cache and html_path.exists() and meta_path.exists():
        return load_cache(html_path, meta_path, url)
    return fetch_official(url, html_path, meta_path, args.timeout, args.retry)


def payout_map(result: OfficialResult, ticket_type: str) -> dict[str, int]:
    return {x["combination"]: x["payout"] for x in result.payouts.get(ticket_type, [])}


def bet_includes_refunded_boat(bet: str, refunded_boats: list[str]) -> bool:
    boats = re.findall(r"[1-6]", bet)
    return any(x in refunded_boats for x in boats)


def evaluate_section(ticket_type_value: str, bet_text: str, point_text: str | None,
                     result: OfficialResult, unit_stake: int,
                     all_refunded: bool = False) -> dict[str, str | int]:
    ticket_type = normalize_ticket_type(ticket_type_value)
    bets = expand_bets(ticket_type_value, bet_text)
    if point_text is not None and str(point_text).strip():
        try:
            declared_points = int(unicodedata.normalize("NFKC", str(point_text).strip()))
        except ValueError as exc:
            raise InputError(f"点数が整数ではありません: {point_text!r}") from exc
        if declared_points != len(bets):
            raise InputError(f"点数不一致: CSV={declared_points}, 展開後={len(bets)}")
    planned = len(bets) * unit_stake
    if all_refunded:
        refunded_bets = bets
    else:
        refunded_bets = [x for x in bets if bet_includes_refunded_boat(x, result.refunded_boats)]
    refund = len(refunded_bets) * unit_stake
    valid_bets = [x for x in bets if x not in set(refunded_bets)]
    official = payout_map(result, ticket_type) if ticket_type else {}
    hits = [x for x in valid_bets if x in official]
    special_payout = result.special_payouts.get(ticket_type) if ticket_type else None
    if special_payout is not None and valid_bets:
        hit_state = "特払い"
        hit_bets = valid_bets
        hit_payout = len(valid_bets) * special_payout * unit_stake // 100
    else:
        hit_state = "的中" if hits else ("対象なし" if not bets else "不的中")
        hit_bets = hits
        hit_payout = sum(official[x] * unit_stake // 100 for x in hits)
    return {
        "planned": planned,
        "refund": refund,
        "net_investment": planned - refund,
        "hit": hit_state,
        "hit_bet": "／".join(hit_bets),
        "payout": hit_payout,
        "expanded": "／".join(bets),
    }


def serialize_payouts(result: OfficialResult, ticket_type: str) -> tuple[str, str]:
    rows = result.payouts.get(ticket_type, [])
    if not rows and ticket_type in result.special_payouts:
        return "特払い", str(result.special_payouts[ticket_type])
    return ("／".join(x["combination"] for x in rows),
            "／".join(str(x["payout"]) for x in rows))


def serialize_combined_payouts(result: OfficialResult, ticket_type: str) -> str:
    if not result.payouts.get(ticket_type) and ticket_type in result.special_payouts:
        return f"特払い:{result.special_payouts[ticket_type]}"
    return "／".join(f"{x['combination']}:{x['payout']}" for x in result.payouts.get(ticket_type, []))


def blank_output(row: dict[str, str], url: str, checked_at: str) -> dict[str, str]:
    output = {name: "" for name in OUTPUT_COLUMNS}
    for name in ("日付", "会場", "R", "判定"):
        output[name] = row.get(name, "")
    output.update({"公式URL": url, "結果確認日時": checked_at,
                   "中止": "いいえ", "不成立": "いいえ"})
    return output


def result_status(result: OfficialResult) -> str:
    if result.cancelled:
        return "開催中止"
    if result.invalid:
        return "レース不成立"
    if not result.determined:
        return "公式未確定"
    required = ("3連単", "3連複", "2連単", "2連複", "拡連複", "単勝", "複勝")
    if any(not result.payouts.get(x) and x not in result.special_payouts
           for x in required):
        return "解析失敗"
    if len(result.finish_order) < 3:
        return "解析失敗"
    official_trifecta = payout_map(result, "3連単")
    expected_trifecta = canonical_bet("3連単", result.finish_order[:3])
    if expected_trifecta not in official_trifecta:
        return "解析失敗"
    return "取得成功"


def fill_result(output: dict[str, str], row: dict[str, str], fetched: FetchData,
                result: OfficialResult, args) -> None:
    output.update({
        "確定着順": "-".join(result.finish_order),
        "着順詳細": "／".join(f"{x['rank']}:{x['boat']}" for x in result.finish_rows),
        "返還艇": ",".join(result.refunded_boats),
        "欠場艇": ",".join(result.absent_boats),
        "失格艇": ",".join(result.disqualified_boats),
        "事故艇": ",".join(result.incident_boats),
        "中止": "はい" if result.cancelled else "いいえ",
        "不成立": "はい" if result.invalid else "いいえ",
        "備考": result.remarks,
        "HTTPステータス": str(fetched.http_status),
        "HTTP取得日時": fetched.fetched_at,
        "HTML_SHA256": fetched.sha256,
    })
    for ticket, combo_col, money_col in (
        ("3連単", "公式3連単", "公式3連単払戻"),
        ("3連複", "公式3連複", "公式3連複払戻"),
        ("2連単", "公式2連単", "公式2連単払戻"),
        ("2連複", "公式2連複", "公式2連複払戻"),
    ):
        output[combo_col], output[money_col] = serialize_payouts(result, ticket)
    output["公式拡連複"] = serialize_combined_payouts(result, "拡連複")
    output["公式単勝"] = serialize_combined_payouts(result, "単勝")
    output["公式複勝"] = serialize_combined_payouts(result, "複勝")

    status = result_status(result)
    all_refunded = status in {"開催中止", "レース不成立"}
    sections = (
        ("主推奨", "主推奨券種", "主推奨買い目展開後", "主推奨点数"),
        ("保険", "保険券種", "保険買い目", "保険点数"),
        ("参考", "参考券種", "参考買い目", None),
    )
    for prefix, type_col, bet_col, point_col in sections:
        evaluated = evaluate_section(row.get(type_col, ""), row.get(bet_col, ""),
                                     row.get(point_col, "") if point_col else None,
                                     result, args.unit_stake, all_refunded)
        output[f"{prefix}購入予定額"] = str(evaluated["planned"])
        output[f"{prefix}返還額"] = str(evaluated["refund"])
        output[f"{prefix}返還後投資額"] = str(evaluated["net_investment"])
        output[f"{prefix}的中"] = str(evaluated["hit"])
        output[f"{prefix}的中買い目"] = str(evaluated["hit_bet"])
        output[f"{prefix}払戻"] = str(evaluated["payout"])
    output["取得状態"] = status
    if status == "解析失敗":
        missing = [x for x in ("確定着順", "3連単", "3連複", "2連単", "2連複", "拡連複", "単勝", "複勝")
                   if (x == "確定着順" and len(result.finish_order) < 3) or
                   (x != "確定着順" and not result.payouts.get(x)
                    and x not in result.special_payouts)]
        expected = canonical_bet("3連単", result.finish_order[:3]) if len(result.finish_order) >= 3 else ""
        if expected and expected not in payout_map(result, "3連単"):
            output["エラー内容"] = f"確定着順上位3艇と公式3連単が不一致: 着順={expected}"
        else:
            output["エラー内容"] = "公式確定結果の必須項目不足: " + ",".join(missing)


def read_input(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            headers = reader.fieldnames or []
            rows = list(reader)
    except UnicodeDecodeError as exc:
        raise InputError("入力CSVはUTF-8（BOM有無どちらも可）で保存してください") from exc
    if not headers or any(not normalize_space(x or "") for x in headers):
        raise InputError("入力CSVに空の列名があります")
    duplicate_headers = sorted(
        x for x, count in Counter(headers).items() if count > 1)
    if duplicate_headers:
        raise InputError("入力CSVの列名が重複しています: " + ",".join(duplicate_headers))
    required = {"日付", "会場", "R", "判定", "主推奨券種", "主推奨買い目展開後",
                "主推奨点数", "保険券種", "保険買い目", "保険点数",
                "参考券種", "参考買い目", "予想確定日時"}
    missing = required - set(headers)
    if missing:
        raise InputError("入力CSVの必須列不足: " + ",".join(sorted(missing)))
    for line_number, row in enumerate(rows, 2):
        if None in row:
            raise InputError(f"入力CSVの{line_number}行目に列数超過があります")
        missing_cells = [name for name in required if row.get(name) is None]
        if missing_cells:
            raise InputError(
                f"入力CSVの{line_number}行目に列不足があります: " + ",".join(sorted(missing_cells)))
    return headers, rows


def derive_output_path(input_path: Path, rows: list[dict[str, str]]) -> Path:
    dates = sorted({parse_date(x["日付"]).strftime("%Y%m%d") for x in rows})
    venues = list(dict.fromkeys(x["会場"].strip() for x in rows))
    date_part = dates[0] if len(dates) == 1 else f"{dates[0]}-{dates[-1]}"
    return input_path.with_name(f"{date_part}_結果_{'_'.join(venues)}.csv")


def derive_log_path(output_path: Path) -> Path:
    return output_path.with_name(output_path.stem.replace("_結果_", "_結果取得ログ_") + ".log")


class JSTFormatter(logging.Formatter):
    """実行環境のローカル設定に依存せず、ログ接頭辞をJSTで出力する。"""

    def formatTime(self, record, datefmt=None):  # noqa: N802 - logging API名
        timestamp = datetime.fromtimestamp(record.created, JST)
        return timestamp.strftime(datefmt or "%Y-%m-%dT%H:%M:%S%z")


def configure_logging(path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("boatrace_results")
    logger.setLevel(logging.INFO)
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()
    formatter = JSTFormatter("%(asctime)s %(levelname)s %(message)s")
    # 1ファイルを1実行の証跡に限定し、再実行時に旧ログを混在させない。
    file_handler = logging.FileHandler(path, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BOAT RACE公式結果を予想CSVと突合")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--cache-dir", type=Path, default=Path("cache"))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--use-cache", action="store_true", help="キャッシュ優先（存在時は再利用）")
    modes.add_argument("--refresh", action="store_true", help="既存キャッシュを無視して公式サイトから再取得")
    modes.add_argument("--cache-only", action="store_true", help="キャッシュのみで再解析")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retry", type=int, default=2)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--unit-stake", type=int, default=100)
    parser.add_argument("--strict", action="store_true",
                        help="公式未確定・中止・不成立も終了コード非0にする")
    parser.add_argument("--limit", type=int, help="開発確認用。先頭N件のみ処理（本番禁止）")
    return parser


def validate_args(args) -> None:
    if args.timeout <= 0 or args.retry < 0 or args.interval < 0 or args.unit_stake <= 0:
        raise InputError("timeout/retry/interval/unit-stake の値が不正です")
    if args.unit_stake % 100 != 0:
        raise InputError("unit-stakeは100円単位で指定してください")
    if args.limit is not None and args.limit <= 0:
        raise InputError("limitは1以上で指定してください")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        validate_args(args)
        _, all_rows = read_input(args.input)
    except (InputError, OSError) as exc:
        print(f"入力エラー: {exc}", file=sys.stderr)
        return 2
    if not all_rows:
        print("入力エラー: CSVにデータ行がありません", file=sys.stderr)
        return 2

    output_path = args.output or derive_output_path(args.input, all_rows)
    log_path = args.log or derive_log_path(output_path)
    logger = configure_logging(log_path)
    started_at = now_jst()
    rows = all_rows[:args.limit] if args.limit else all_rows
    logger.info("実行開始日時=%s 入力ファイル=%s 入力行数=%d 処理行数=%d",
                started_at, args.input, len(all_rows), len(rows))
    mode = ("cache-only" if args.cache_only else "use-cache" if args.use_cache
            else "refresh" if args.refresh else "network")
    logger.info("取得モード=%s timeout=%.1f retry=%d interval=%.1f unit_stake=%d",
                mode, args.timeout, args.retry, args.interval, args.unit_stake)
    if args.limit:
        logger.warning("開発確認モード --limit=%d: 全件成果物ではありません", args.limit)

    def normalized_key(row):
        return (parse_date(row.get("日付", "")).strftime("%Y-%m-%d"),
                normalize_space(row.get("会場", "")), parse_race_no(row.get("R", "")))
    normalized_keys: list[tuple[str, str, int] | None] = []
    key_errors: dict[int, str] = {}
    for index, row in enumerate(rows):
        try:
            normalized_keys.append(normalized_key(row))
        except InputError as exc:
            normalized_keys.append(None)
            key_errors[index] = str(exc)
    valid_keys = [x for x in normalized_keys if x is not None]
    duplicates = {k for k, count in Counter(valid_keys).items() if count > 1}
    outputs: list[dict[str, str]] = []
    source_counts: Counter[str] = Counter()
    for index, row in enumerate(rows, 1):
        checked_at = now_jst()
        url = ""
        output = blank_output(row, url, checked_at)
        normalized = normalized_keys[index - 1]
        key_raw = normalized or (
            normalize_space(row.get("日付", "")), normalize_space(row.get("会場", "")),
            normalize_space(row.get("R", "")))
        try:
            if normalized is None:
                raise InputError(key_errors[index - 1])
            date_value = parse_date(row.get("日付", ""))
            venue = row.get("会場", "").strip()
            if venue not in VENUE_CODES:
                raise InputError(f"未対応の会場名です: {venue!r}")
            race_no = parse_race_no(row.get("R", ""))
            url = official_url(date_value, VENUE_CODES[venue], race_no)
            output["公式URL"] = url
            if key_raw in duplicates:
                raise InputError("日付＋会場＋Rが重複しています")
            # 公式取得前に買い目構造と点数を検証する。
            empty_result = OfficialResult()
            evaluate_section(row.get("主推奨券種", ""), row.get("主推奨買い目展開後", ""),
                             row.get("主推奨点数", ""), empty_result, args.unit_stake)
            evaluate_section(row.get("保険券種", ""), row.get("保険買い目", ""),
                             row.get("保険点数", ""), empty_result, args.unit_stake)
            evaluate_section(row.get("参考券種", ""), row.get("参考買い目", ""),
                             None, empty_result, args.unit_stake)

            html_path, meta_path = cache_paths(args.cache_dir, date_value,
                                               VENUE_CODES[venue], race_no)
            logger.info("対象=%s %s %sR 公式URL=%s", row["日付"], venue, race_no, url)
            fetched = acquire(url, html_path, meta_path, args)
            source_counts[fetched.source] += 1
            output.update({"HTTPステータス": str(fetched.http_status),
                           "HTTP取得日時": fetched.fetched_at,
                           "HTML_SHA256": fetched.sha256})
            result = parse_official_html(fetched.content, venue, date_value, race_no, url)
            fill_result(output, row, fetched, result, args)
            logger.info("HTTP=%d 取得日時=%s source=%s 解析結果=%s 状態=%s エラー=%s",
                        fetched.http_status, fetched.fetched_at, fetched.source,
                        output["確定着順"], output["取得状態"], output["エラー内容"])
        except InputError as exc:
            output["取得状態"] = "入力不正"
            output["エラー内容"] = str(exc)
            logger.error("対象=%s 状態=入力不正 エラー=%s", key_raw, exc)
        except (HTTPError, URLError, TimeoutError, OSError, FileNotFoundError) as exc:
            output["取得状態"] = "取得失敗"
            output["エラー内容"] = str(exc)
            logger.error("対象=%s URL=%s 状態=取得失敗 エラー=%s", key_raw, url, exc)
        except (ParseError, ValueError, json.JSONDecodeError) as exc:
            output["取得状態"] = "解析失敗"
            output["エラー内容"] = str(exc)
            logger.error("対象=%s URL=%s 状態=解析失敗 エラー=%s", key_raw, url, exc)
        except Exception as exc:  # 不明な例外も成功扱いにしない。
            output["取得状態"] = "解析失敗"
            output["エラー内容"] = f"未処理例外: {type(exc).__name__}: {exc}"
            logger.exception("対象=%s URL=%s 状態=解析失敗", key_raw, url)
        output["結果確認日時"] = now_jst()
        outputs.append(output)
        # キャッシュ読込後には待機しない。ネットワーク取得後だけアクセス間隔を置く。
        if (index < len(rows) and output.get("HTTP取得日時")
                and fetched.source == "network" and args.interval):
            time.sleep(args.interval)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8-sig", newline="", dir=output_path.parent,
                prefix=f".{output_path.name}.", suffix=".tmp", delete=False) as stream:
            temporary_output = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(outputs)
            stream.flush()
            os.fsync(stream.fileno())
        temporary_output.replace(output_path)
    finally:
        if temporary_output is not None and temporary_output.exists():
            temporary_output.unlink()

    status_counts = Counter(x["取得状態"] for x in outputs)
    output_keys = []
    for output in outputs:
        try:
            output_keys.append(normalized_key(output))
        except InputError:
            pass
    input_key_set, output_key_set = set(valid_keys), set(output_keys)
    unjoined = input_key_set - output_key_set
    surplus = output_key_set - input_key_set
    url_count = sum(bool(x["公式URL"]) for x in outputs)
    audit_ok = (
        args.limit is None and len(all_rows) == len(outputs)
        and not duplicates and not unjoined and not surplus
        and status_counts["取得失敗"] == 0
        and status_counts["解析失敗"] == 0
        and status_counts["入力不正"] == 0
        and status_counts["公式未確定"] == 0
        and url_count == len(outputs)
    )
    if args.strict:
        audit_ok = audit_ok and all(x["取得状態"] == "取得成功" for x in outputs)

    logger.info("成功件数=%d 中止件数=%d 不成立件数=%d 公式未確定件数=%d "
                "取得失敗件数=%d 解析失敗件数=%d 入力不正件数=%d",
                status_counts["取得成功"], status_counts["開催中止"],
                status_counts["レース不成立"], status_counts["公式未確定"],
                status_counts["取得失敗"], status_counts["解析失敗"],
                status_counts["入力不正"])
    logger.info("出力ファイル=%s 出力件数=%d 公式URL記録件数=%d 重複件数=%d "
                "未結合件数=%d 余剰件数=%d 仮データ生成機能=未実装 結果固定値使用機能=未実装",
                output_path, len(outputs), url_count, len(duplicates), len(unjoined), len(surplus))
    logger.info("取得元件数=network:%d cache:%d", source_counts["network"], source_counts["cache"])
    def race_label(value: str) -> str:
        normalized_value = unicodedata.normalize("NFKC", str(value or "")).strip().upper()
        return normalized_value if normalized_value.endswith("R") else f"{normalized_value}R"

    failed = [f"{x['日付']} {x['会場']} {race_label(x['R'])}:{x['取得状態']}:{x['エラー内容']}"
              for x in outputs if x["取得状態"] in {"取得失敗", "解析失敗", "入力不正", "公式未確定"}]
    if failed:
        logger.error("未完了対象=%s", " | ".join(failed))
    logger.info("実行終了日時=%s %s", now_jst(), "正常終了" if audit_ok else "異常終了")
    return 0 if audit_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
