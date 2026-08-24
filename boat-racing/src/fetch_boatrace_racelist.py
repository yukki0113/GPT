#!/usr/bin/env python3
"""BOAT RACE公式出走表を、予想前の入力CSVへ保存するツール。

取得対象は公式racelistページだけです。展示・オッズ・気象・結果ページ等は
アクセスも解析もしません。今節成績は公式出走表に表示される既走情報のみを
文字列として保存します。
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from bs4 import BeautifulSoup, Tag

JST = timezone(timedelta(hours=9))
OFFICIAL_HOST = "www.boatrace.jp"
OFFICIAL_VENUES = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川", "06": "浜名湖",
    "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
    "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島", "17": "宮島", "18": "徳山",
    "19": "下関", "20": "若松", "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}
PC_URL = "https://www.boatrace.jp/owpc/pc/race/racelist"
SP_URL = "https://www.boatrace.jp/owsp/sp/race/racelist"
RAW_COLUMNS = [
    "日付", "会場", "場コード", "R", "締切時刻", "開催日目", "レース種別", "艇番", "登録番号", "選手名", "級別",
    "全国勝率", "全国2連率", "当地勝率", "当地2連率", "平均ST", "コース別進入数", "コース別1着率",
    "コース別2連率", "コース別3連率", "モーター番号", "モーター2連率", "ボート番号", "ボート2連率",
    "今節成績", "欠場状態", "取得元区分", "取得元URL", "取得確認日時", "取得状態", "備考",
]
INPUT_COLUMNS = [
    "日付", "会場", "場コード", "R", "締切時刻", "開催日目", "レース種別", "艇番", "登録番号", "選手名", "級別",
    "全国勝率", "当地勝率", "平均ST", "コース別成績", "モーター番号", "モーター2連率", "今節成績", "欠場状態",
]
STATUS_COLUMNS = [
    "日付", "会場", "場コード", "R", "取得状態", "取得艇数", "PC版取得", "スマホ版取得", "不足項目",
    "取得元URL", "取得確認日時", "エラー内容", "備考",
]
# 取得成否は「ページをレースとして正しく解析できたか」で判定する。
# 平均STの `-`、今節成績を含む各成績項目の空欄は、公式ページに値がない
# ことを表す有効な表示であり、取得失敗ではない。CSVには公式表示のまま残す。
REQUIRED_STRUCTURAL = ["日付", "会場", "R", "締切時刻", "艇番", "登録番号", "選手名", "級別"]
FORBIDDEN = ("AI予想", "コンピューター予想", "予想印", "買い目", "予想確率", "独自指数", "オッズ", "人気", "展示", "直前", "レース結果", "着順", "払戻")
RETRYABLE_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class FetchResult:
    html: str | None
    status_code: int | None
    retries: int
    error: str
    final_url: str
    content_type: str


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def lines(tag: Tag) -> list[str]:
    return [clean(x) for x in tag.stripped_strings if clean(x)]


def cell_lines(cells: list[Tag], index: int) -> list[str]:
    return lines(cells[index]) if len(cells) > index else []


def value_at(cells: list[Tag], index: int, line: int = 0) -> str:
    values = cell_lines(cells, index)
    return values[line] if len(values) > line else ""


def is_missing(value: str) -> bool:
    return not value or value in {"-", "－", "欠", "不"}


def is_valid_time(value: str) -> bool:
    if not re.fullmatch(r"\d{1,2}:\d{2}", value):
        return False
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        return False
    return True


def parse_pc_soup(soup: BeautifulSoup) -> tuple[str, list[dict[str, str]]]:
    """解析済みPC版HTMLから、出走表テーブルの6個のtbodyを艇として読む。"""
    title = soup.select_one(".title16_titleDetail__add2020")
    race_type = clean(title.get_text(" ", strip=True)).replace("1800m", "").strip() if title else ""
    boats: list[dict[str, str]] = []
    for body in soup.select("tbody.is-fs12"):
        rows = body.find_all("tr", recursive=False)
        if len(rows) < 4:
            continue
        cells = rows[0].find_all(["td", "th"], recursive=False)
        if len(cells) < 9:
            continue
        boat_no = value_at(cells, 0)
        profile = cell_lines(cells, 2)
        registration = re.search(r"\b(\d{4})\b", " ".join(profile))
        grade = next((x for x in profile if re.fullmatch(r"[AB][12]", x)), "")
        name = next((x for x in profile if x not in {grade} and not re.search(r"\d", x) and "/" not in x and "歳" not in x), "")
        st = cell_lines(cells, 3)
        national, local, motor, boat = (cell_lines(cells, i) for i in range(4, 8))
        # 4行×14日程セル。前走の着順だけでなく、進入・STとセットで公式表示を保存する。
        history: list[str] = []
        # 先頭行だけは選手基本情報（9セル）が前置され、2～4行目は日程セルから始まる。
        day_cells = [cells[9:23]] + [r.find_all("td", recursive=False)[:14] for r in rows[1:4]]
        for col in range(14):
            one = [value_at(row, col) for row in day_cells if len(row) > col and value_at(row, col)]
            if one:
                history.append("/".join(one))
        status_text = " ".join(lines(body))
        withdrawal = "欠場" if "欠場" in status_text else ("不出走" if "不出走" in status_text else "")
        boats.append({
            "艇番": boat_no.translate(str.maketrans("１２３４５６", "123456")),
            "登録番号": registration.group(1) if registration else "",
            "選手名": name, "級別": grade,
            "全国勝率": national[0] if national else "", "全国2連率": national[1] if len(national) > 1 else "",
            "当地勝率": local[0] if local else "", "当地2連率": local[1] if len(local) > 1 else "",
            "平均ST": (st[-1].replace("−", "-").replace("－", "-") if st else ""), "モーター番号": motor[0] if motor else "",
            "モーター2連率": motor[1] if len(motor) > 1 else "", "ボート番号": boat[0] if boat else "",
            "ボート2連率": boat[1] if len(boat) > 1 else "", "今節成績": " | ".join(history), "欠場状態": withdrawal,
        })
    return race_type, boats


def parse_pc(html: str) -> tuple[str, list[dict[str, str]]]:
    """PC版の1レースページを解析する（外部呼出しとの互換用）。"""
    return parse_pc_soup(BeautifulSoup(html, "html.parser"))


def parse_cutoff_time_soup(soup: BeautifulSoup, rno: int) -> str:
    """解析済みPC版HTMLの締切予定時刻一覧から、対象Rの時刻を取得する。"""
    label = soup.find(string=lambda value: clean(value) == "締切予定時刻")
    row = label.find_parent("tr") if label else None
    if not row:
        return ""
    cells = row.find_all("td", recursive=False)
    # 先頭のtdは見出し（colspan=2）のため、R番のセルは2番目以降となる。
    value_index = rno
    value = value_at(cells, value_index)
    return value if is_valid_time(value) else ""


def parse_cutoff_time(html: str, rno: int) -> str:
    """PC版の締切予定時刻一覧から対象Rの時刻を取得する（互換用）。"""
    return parse_cutoff_time_soup(BeautifulSoup(html, "html.parser"), rno)


def normalize_day(value: Any) -> str:
    text = clean(value).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if text == "初日":
        return "1"
    if text == "最終日":
        return "最終"
    match = re.fullmatch(r"([1-9])(?:日目)?", text)
    return match.group(1) if match else text


def parse_page_identity(soup: BeautifulSoup) -> dict[str, str]:
    """公式ページ自身が示す会場・場コード・開催日付・開催日目を抽出する。"""
    result = {"venue": "", "code": "", "month_day": "", "day": ""}
    venue_img = soup.select_one(".heading2_area img[alt]")
    if venue_img:
        result["venue"] = clean(venue_img.get("alt", ""))
        match = re.search(r"text_place2_(\d{2})\.png", str(venue_img.get("src", "")))
        if match:
            result["code"] = match.group(1)
    tabs = soup.select(".tab2_tabs li")
    for index, tab in enumerate(tabs, start=1):
        if "is-active2" not in tab.get("class", []):
            continue
        tab_text = clean(tab.get_text(" ", strip=True)).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        match = re.search(r"(\d{1,2})月(\d{1,2})日", tab_text)
        if match:
            result["month_day"] = f"{int(match.group(1)):02d}{int(match.group(2)):02d}"
        result["day"] = str(index)
        break
    return result


def identity_errors(identity: dict[str, str], date: str, venue: dict[str, Any], final_url: str) -> list[str]:
    expected_code = str(venue["code"]).zfill(2)
    expected_day = normalize_day(venue["day"])
    expected = {"venue": str(venue["name"]), "code": expected_code, "month_day": date[4:], "day": expected_day}
    errors = [f"ページ{key}不一致({identity.get(key) or '未取得'}!={value})" for key, value in expected.items() if identity.get(key) != value and not (key == "day" and expected_day == "最終")]
    parsed = urlparse(final_url)
    query = parse_qs(parsed.query)
    if query.get("hd", [""])[0] != date or query.get("jcd", [""])[0] != expected_code:
        errors.append("最終URLの対象日または場コードが不一致")
    return errors


def parse_sp(html: str) -> tuple[str, list[dict[str, str]]]:
    """スマホ版の構造差に備えたフォールバック。

    スマホ版がPC版と同じ表構造を返す場合はPCパーサーを再利用する。現行の
    スマホ版はHTTP応答がJavaScript用の空コンテナであり、通常HTTPだけでは
    選手情報を安全に抽出できない。必須項目を取得できなければ成功扱いにしない。
    """
    race_type, boats = parse_pc(html)
    if boats:
        return race_type, boats
    return "", []  # JS描画ページを推測解析しない。


def request_page(session: requests.Session, url: str, logger: logging.Logger, wait: float) -> FetchResult:
    error = ""
    last_status: int | None = None
    last_url = url
    last_content_type = ""
    for attempt in range(3):
        try:
            response = session.get(url, timeout=(10, 30))
            final_url = response.url
            content_type = response.headers.get("Content-Type", "")
            last_status, last_url, last_content_type = response.status_code, final_url, content_type
            logger.info("url=%s final_url=%s status=%s content_type=%s retry=%s", url, final_url, response.status_code, content_type, attempt)
            if response.status_code == 200:
                parsed = urlparse(final_url)
                if parsed.scheme != "https" or parsed.hostname != OFFICIAL_HOST:
                    error = f"公式ドメイン外へ遷移: {final_url}"
                elif not content_type.lower().startswith("text/html"):
                    error = f"HTML以外の応答: {content_type or '不明'}"
                elif not response.text.strip():
                    error = "HTTP 200だが応答本文が空"
                else:
                    return FetchResult(response.text, response.status_code, attempt, "", final_url, content_type)
                logger.warning("url=%s error=%s", url, error)
                return FetchResult(None, response.status_code, attempt, error, final_url, content_type)
            error = f"HTTP {response.status_code}"
            if response.status_code not in RETRYABLE_HTTP_STATUS:
                return FetchResult(None, response.status_code, attempt, error, final_url, content_type)
        except requests.RequestException as exc:
            error = f"{type(exc).__name__}: {exc}"
            logger.warning("url=%s retry=%s error=%s", url, attempt, error)
        if attempt < 2:
            retry_after = 0.0
            if last_status is not None and response.headers.get("Retry-After", "").isdigit():
                retry_after = min(float(response.headers["Retry-After"]), 60.0)
            time.sleep(max(retry_after, max(wait, 1.0) * (2 ** attempt)))
    return FetchResult(None, last_status, 2, error, last_url, last_content_type)


def missing_fields(rows: list[dict[str, str]]) -> list[str]:
    """解析失敗を示す構造項目だけを検査する。

    成績・率・平均ST・今節成績などの値は、公式ページ側で未掲載の場合がある。
    それらは空欄や `-` でも正常取得とし、不足項目には記載しない。
    """
    missing = {field for row in rows for field in REQUIRED_STRUCTURAL if is_missing(row.get(field, ""))}
    if sorted(row.get("艇番", "") for row in rows) != ["1", "2", "3", "4", "5", "6"]:
        missing.add("艇番1〜6")
    for row in rows:
        boat = row.get("艇番", "?")
        if row.get("登録番号") and not re.fullmatch(r"\d{4}", row["登録番号"]):
            missing.add(f"登録番号形式(艇{boat})")
        if row.get("級別") and not re.fullmatch(r"[AB][12]", row["級別"]):
            missing.add(f"級別形式(艇{boat})")
        for field in ("全国勝率", "当地勝率"):
            value = row.get(field, "")
            if value and value not in {"-", "－"} and (not re.fullmatch(r"\d+(?:\.\d+)?", value) or not 0 <= float(value) <= 10):
                missing.add(f"{field}形式(艇{boat})")
        for field in ("モーター2連率", "全国2連率", "当地2連率", "ボート2連率"):
            value = row.get(field, "").rstrip("%")
            if value and value not in {"-", "－"} and (not re.fullmatch(r"\d+(?:\.\d+)?", value) or not 0 <= float(value) <= 100):
                missing.add(f"{field}形式(艇{boat})")
    return sorted(missing)


def collect_race(session: requests.Session, date: str, venue: dict[str, Any], rno: int, logger: logging.Logger, delay: float) -> tuple[list[dict[str, str]], dict[str, str], int]:
    params = {"hd": date, "jcd": str(venue["code"]).zfill(2), "rno": rno}
    pc_url = f"{PC_URL}?{urlencode(params)}"
    sp_url = f"{SP_URL}?{urlencode(params)}"
    stamp = datetime.now(JST).isoformat(timespec="seconds")
    pc_result = request_page(session, pc_url, logger, delay)
    retries, pc_error = pc_result.retries, pc_result.error
    race_type, boats, cutoff_time = "", [], ""
    if pc_result.html:
        soup = BeautifulSoup(pc_result.html, "html.parser")
        race_type, boats = parse_pc_soup(soup)
        cutoff_time = parse_cutoff_time_soup(soup, rno)
        page_errors = identity_errors(parse_page_identity(soup), date, venue, pc_result.final_url)
        if page_errors:
            boats = []
            pc_error = "; ".join(page_errors)
        elif not boats:
            pc_error = "HTTP 200だが出走表テーブルを解析できません"
    source, source_url, sp_flag, error = "PC", pc_result.final_url or pc_url, "未使用", pc_error
    if not boats:
        sp_result = request_page(session, sp_url, logger, delay)
        retries += sp_result.retries
        sp_error = sp_result.error
        race_type, boats = parse_sp(sp_result.html) if sp_result.html else ("", [])
        if boats and sp_result.html:
            sp_soup = BeautifulSoup(sp_result.html, "html.parser")
            page_errors = identity_errors(parse_page_identity(sp_soup), date, venue, sp_result.final_url)
            if page_errors:
                boats = []
                sp_error = "; ".join(page_errors)
            if not cutoff_time:
                cutoff_time = parse_cutoff_time_soup(sp_soup, rno)
        elif sp_result.html and not sp_error:
            sp_error = "HTTP 200だが出走表テーブルを解析できません"
        source, source_url, sp_flag = "スマホ", sp_result.final_url or sp_url, "成功" if boats else "失敗"
        error = "; ".join(x for x in (pc_error, sp_error) if x)
    else:
        sp_flag = "未使用"
    base = {"日付": date, "会場": venue["name"], "場コード": str(venue["code"]).zfill(2), "R": str(rno), "締切時刻": cutoff_time, "開催日目": str(venue["day"]), "レース種別": race_type,
            "コース別進入数": "", "コース別1着率": "", "コース別2連率": "", "コース別3連率": "", "取得元区分": source, "取得元URL": source_url, "取得確認日時": stamp, "取得状態": "", "備考": ""}
    rows = [{**base, **boat} for boat in boats]
    missing = missing_fields(rows) if rows else REQUIRED_STRUCTURAL
    status = "取得不能" if not rows else ("一部取得" if missing else ("欠場あり" if any(row["欠場状態"] for row in rows) else "成功"))
    for row in rows:
        row["取得状態"] = status
        if missing:
            row["備考"] = "構造必須項目不足: " + ", ".join(missing)
    report = {"日付": date, "会場": venue["name"], "場コード": str(venue["code"]).zfill(2), "R": str(rno), "取得状態": status, "取得艇数": str(len(rows)),
              "PC版取得": "成功" if source == "PC" else "失敗", "スマホ版取得": sp_flag, "不足項目": ", ".join(missing), "取得元URL": source_url,
              "取得確認日時": stamp, "エラー内容": error, "備考": "再試行回数: " + str(retries)}
    logger.info("venue=%s r=%s parsed=%s status=%s missing=%s error=%s", venue["name"], rno, len(rows), status, report["不足項目"], error)
    return rows, report, retries


def validate(rows: list[dict[str, str]], reports: list[dict[str, str]], venue_count: int) -> list[str]:
    errors: list[str] = []
    if len(reports) != venue_count * 12: errors.append(f"レース数が不正: {len(reports)}")
    keys = [(r["日付"], r["会場"], r["R"], r["艇番"]) for r in rows]
    if len(keys) != len(set(keys)): errors.append("日付・会場・R・艇番の重複")
    if any(len(r) != len(RAW_COLUMNS) for r in rows): errors.append("原本CSV列数不正")
    if any(c in FORBIDDEN for c in RAW_COLUMNS + INPUT_COLUMNS): errors.append("禁止情報の列を検出")
    if any(urlparse(r["取得元URL"]).hostname != OFFICIAL_HOST for r in rows): errors.append("公式ドメイン外URLを検出")
    rows_by_race: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        rows_by_race.setdefault((row["会場"], row["R"]), []).append(row)
    for report in reports:
        race_rows = rows_by_race.get((report["会場"], report["R"]), [])
        nums = [r["艇番"] for r in race_rows]
        if any(n not in {"1", "2", "3", "4", "5", "6"} for n in nums): errors.append(f"艇番範囲外: {report['会場']} {report['R']}R")
        if sorted(nums) != ["1", "2", "3", "4", "5", "6"]: errors.append(f"艇番1〜6が各1艇ずつ揃わない: {report['会場']} {report['R']}R")
        regs = [r["登録番号"] for r in race_rows if r["登録番号"]]
        if len(regs) != len(set(regs)): errors.append(f"登録番号重複: {report['会場']} {report['R']}R")
    return errors


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    """同一ディレクトリの一時ファイルへ完書きしてから置換する。"""
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_config(args: argparse.Namespace) -> dict[str, Any]:
    config = json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {}
    if args.date: config["date"] = args.date
    if args.output: config["output_dir"] = args.output
    if not re.fullmatch(r"\d{8}", str(config.get("date", ""))): raise ValueError("date は YYYYMMDD で指定してください")
    try:
        datetime.strptime(str(config["date"]), "%Y%m%d")
    except ValueError as exc:
        raise ValueError("date は実在する日付を YYYYMMDD で指定してください") from exc
    if not config.get("venues"): raise ValueError("venues が必要です")
    codes: list[str] = []
    for venue in config["venues"]:
        if not all(k in venue for k in ("name", "code", "day")): raise ValueError("各venueに name, code, day が必要です")
        code = str(venue["code"]).zfill(2)
        if code not in OFFICIAL_VENUES:
            raise ValueError(f"場コードが不正です: {venue['code']}")
        if venue["name"] != OFFICIAL_VENUES[code]:
            raise ValueError(f"会場名と場コードが一致しません: {venue['name']} / {code}")
        if normalize_day(venue["day"]) not in {str(n) for n in range(1, 8)} | {"最終"}:
            raise ValueError(f"開催日目が不正です: {venue['day']}")
        codes.append(code)
    if len(codes) != len(set(codes)):
        raise ValueError("venues に場コードの重複があります")
    try:
        delay = float(config.get("request_interval_seconds", 1.0))
    except (TypeError, ValueError) as exc:
        raise ValueError("request_interval_seconds は0以上の数値で指定してください") from exc
    if not 0 <= delay <= 60:
        raise ValueError("request_interval_seconds は0以上60以下で指定してください")
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description="BOAT RACE公式出走表をCSVへ保存")
    parser.add_argument("--config", help="設定JSON")
    parser.add_argument("--date", help="YYYYMMDD（設定JSONを上書き）")
    parser.add_argument("--output", help="出力先フォルダ（設定JSONを上書き）")
    args = parser.parse_args()
    try: config = load_config(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc: parser.error(str(exc))
    date, venues = str(config["date"]), config["venues"]
    names = "_".join(v["name"] for v in venues)
    output = Path(config.get("output_dir", "output")); output.mkdir(parents=True, exist_ok=True)
    log_path = output / f"{date}_出走表取得ログ_{names}.log"
    # CSVと同様、同一設定での再実行は前回分へ追記せず再生成する。
    logging.basicConfig(filename=log_path, filemode="w", encoding="utf-8", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("boatrace"); logger.info("開始 date=%s venues=%s", date, venues)
    session = requests.Session(); session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BoatraceRacelistFetcher/1.0", "Accept-Language": "ja-JP,ja;q=0.9"})
    delay = float(config.get("request_interval_seconds", 1.0))
    raw_rows: list[dict[str, str]] = []; reports: list[dict[str, str]] = []; retry_total = 0
    total_races = len(venues) * 12
    print("=" * 60, flush=True)
    print("BOAT RACE公式出走表 CSV取得を開始します", flush=True)
    print(f"対象日: {date} / 会場数: {len(venues)} / レース数: {total_races}", flush=True)
    print("※ 各レースは公式サイトへの配慮として、1回ずつ順番に取得します。", flush=True)
    print("=" * 60, flush=True)
    for venue_index, venue in enumerate(venues, start=1):
        print(f"\n[{venue_index}/{len(venues)}会場] {venue['name']}（場コード {str(venue['code']).zfill(2)}・{venue['day']}日目）を開始", flush=True)
        for rno in range(1, 13):
            current = (venue_index - 1) * 12 + rno
            print(f"  [{current}/{total_races}] {venue['name']} {rno}R を取得中...", end="", flush=True)
            rows, report, retries = collect_race(session, date, venue, rno, logger, delay)
            raw_rows.extend(rows); reports.append(report); retry_total += retries
            detail = f"{report['取得状態']} / {report['取得艇数']}艇 / {report['PC版取得']}"
            if report["スマホ版取得"] != "未使用": detail += f" / スマホ版: {report['スマホ版取得']}"
            if report["不足項目"]: detail += f" / 不足: {report['不足項目']}"
            print(f" 完了（{detail}）", flush=True)
            if not (venue is venues[-1] and rno == 12): time.sleep(delay)
        venue_reports = reports[-12:]
        print(f"  → {venue['name']} 出力対象の取得完了（成功 {sum(x['取得状態'] == '成功' for x in venue_reports)}/12レース）", flush=True)
    errors = validate(raw_rows, reports, len(venues))
    for error in errors: logger.error("検査失敗: %s", error)
    input_rows = [{**row, "コース別成績": ""} for row in raw_rows]
    raw_path = output / f"{date}_公式出走表原本_{names}.csv"
    input_path = output / f"{date}_公式出走表_{names}.csv"
    status_path = output / f"{date}_出走表取得状況_{names}.csv"
    print("\nCSVファイルを出力中...", flush=True)
    write_csv(raw_path, RAW_COLUMNS, raw_rows); write_csv(input_path, INPUT_COLUMNS, input_rows); write_csv(status_path, STATUS_COLUMNS, reports)
    logger.info("終了 rows=%s success=%s retries=%s validation_errors=%s", len(raw_rows), sum(r["取得状態"] == "成功" for r in reports), retry_total, errors)
    print("CSV出力完了", flush=True)
    print(f"原本CSV: {raw_path}\n予想入力CSV: {input_path}\n取得状況CSV: {status_path}\nログ: {log_path}", flush=True)
    print(f"対象 {len(reports)}レース / 行数 {len(raw_rows)} / 成功 {sum(r['取得状態'] == '成功' for r in reports)} / 再試行 {retry_total}", flush=True)
    if errors or any(r["取得状態"] != "成功" for r in reports):
        print("警告: 一部取得または検査エラーがあります。取得状況CSV・ログを確認してください。", file=sys.stderr, flush=True); return 2
    print("すべてのレースを正常に取得しました。", flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
