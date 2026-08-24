#!/usr/bin/env python3
"""BOAT RACE公式サイトから、直前予想用の出走表・直前情報を取得する。

取得元は以下のPC版公式ページだけであり、結果・払戻・オッズは出力しない。
  - 出走表:    /owpc/pc/race/racelist
  - 直前情報:  /owpc/pc/race/beforeinfo

依存パッケージ: requests, beautifulsoup4
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable

import requests
from bs4 import BeautifulSoup, Tag


JST = timezone(timedelta(hours=9))
BASE_URL = "https://www.boatrace.jp/owpc/pc/race"
VENUES = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川",
    "06": "浜名湖", "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国",
    "11": "びわこ", "12": "住之江", "13": "尼崎", "14": "鳴門", "15": "丸亀",
    "16": "児島", "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}
VENUE_TO_CODE = {name: code for code, name in VENUES.items()}
USER_AGENT = "Mozilla/5.0 (compatible; BoatRacePreRaceFetcher/1.0; +https://www.boatrace.jp/)"


@dataclass
class FieldValue:
    value: Any | None
    state: str  # PRESENT / BLANK_ON_PAGE / MISSING_IN_PAGE / NOT_AVAILABLE


@dataclass
class FetchResult:
    fetch_status: str
    failure_kind: str | None
    failure_message: str | None
    target: dict[str, Any]
    fetched_at: str
    source_urls: dict[str, str]
    field_states: dict[str, FieldValue] = field(default_factory=dict)
    racecard_racers: list[dict[str, Any]] = field(default_factory=list)
    exhibition: list[dict[str, Any]] = field(default_factory=list)
    weather: dict[str, Any] = field(default_factory=dict)
    race_info: dict[str, Any] = field(default_factory=dict)


def clean(value: Any) -> str:
    # 公式ページの枠番・着順は全角数字で出力されることがあるため、解析前に
    # 半角へ統一する。選手名などの日本語文字は変換しない。
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip().translate(
        str.maketrans("０１２３４５６７８９", "0123456789")
    )


def normalized_date(value: str) -> str:
    compact = value.replace("-", "").replace("/", "")
    if not re.fullmatch(r"\d{8}", compact):
        raise ValueError("--date は YYYYMMDD または YYYY-MM-DD で指定してください。")
    datetime.strptime(compact, "%Y%m%d")
    return compact


def venue_code(value: str) -> str:
    value = value.strip()
    if value in VENUE_TO_CODE:
        return VENUE_TO_CODE[value]
    if value.zfill(2) in VENUES:
        return value.zfill(2)
    raise ValueError("--venue は会場名（例: 三国）または01〜24の会場コードで指定してください。")


def page_state(text: Any | None, found: bool = True, not_available: bool = False) -> FieldValue:
    if not_available:
        return FieldValue(None, "NOT_AVAILABLE")
    if not found:
        return FieldValue(None, "MISSING_IN_PAGE")
    value = clean(text or "")
    return FieldValue(value or None, "PRESENT" if value else "BLANK_ON_PAGE")


def null_if_blank(value: Any) -> str | None:
    """公式の空欄・ハイフンを null に統一する（値の推測はしない）。"""
    text = clean(value or "")
    return None if text in ("", "-", "－", "―") else text


def as_int(value: Any) -> int | None:
    text = null_if_blank(value)
    return int(text) if text and re.fullmatch(r"-?\d+", text) else None


def as_float(value: Any) -> float | None:
    text = null_if_blank(value)
    return float(text) if text and re.fullmatch(r"-?\d+(?:\.\d+)?", text) else None


def state_for(value: Any, *, available: bool = True) -> FieldValue:
    if not available:
        return FieldValue(None, "NOT_AVAILABLE")
    return FieldValue(value, "PRESENT" if value is not None else "BLANK_ON_PAGE")


def request_page(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=(10, 25))
    response.raise_for_status()
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def table_text_rows(table: Tag) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = [clean(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"], recursive=False)]
        if cells:
            rows.append(cells)
    return rows


def find_table(soup: BeautifulSoup, required_words: Iterable[str]) -> Tag | None:
    required = list(required_words)
    for table in soup.find_all("table"):
        text = clean(table.get_text(" ", strip=True))
        if all(word in text for word in required):
            return table
    return None


def first_number(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1) if match else None


def parse_racecard(html: str) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, FieldValue]]:
    soup = BeautifulSoup(html, "html.parser")
    table = find_table(soup, ["登録番号", "ボートレーサー"])
    if table is None:
        # 現行ページでは「全国勝率」を含む表として現れる場合もある。
        table = find_table(soup, ["全国勝率", "モーター"])
    if table is None:
        raise ValueError("出走表の選手一覧テーブルを検出できませんでした。")

    racers: list[dict[str, Any]] = []
    # 現行PC版は「1艇 = tbody（4行）」で構成される。rowspanされた枠番・
    # 選手情報を tr 単位で読むと、2行目以降と混ざるため tbody の先頭行から
    # 固定列を読む。
    for body in table.select("tbody.is-fs12"):
        rows = body.find_all("tr", recursive=False)
        if not rows:
            continue
        cells = rows[0].find_all(["th", "td"], recursive=False)
        if len(cells) < 8:
            continue
        lane = first_number(clean(cells[0].get_text(" ", strip=True)), r"^([1-6])$")
        profile = clean(cells[2].get_text(" ", strip=True))
        registration = first_number(profile, r"\b(\d{4})\b")
        # 見出し行や、枠番・登録番号がない補助行は除外する。
        if not lane or not registration:
            continue
        name_node = cells[2].select_one(".is-fs18 a") or cells[2].find("a")
        name = clean(name_node.get_text(" ", strip=True)) if name_node else None
        # この8セルは table の見出し（ボートレーサー/F・L・平均ST/全国/当地/
        # モーター/ボート）との列対応で読む。official_row_text の数値順には依存しない。
        st_values = [null_if_blank(x) for x in cells[3].stripped_strings]
        national = [null_if_blank(x) for x in cells[4].stripped_strings]
        local = [null_if_blank(x) for x in cells[5].stripped_strings]
        motor = [null_if_blank(x) for x in cells[6].stripped_strings]
        boat = [null_if_blank(x) for x in cells[7].stripped_strings]
        profile_lines = [null_if_blank(x) for x in cells[2].stripped_strings]
        # profile cell: 登録番号/級別, 氏名, 支部/出身地, 年齢/体重 の順。
        location = profile_lines[-2] if len(profile_lines) >= 4 else None
        age_weight = profile_lines[-1] if len(profile_lines) >= 4 else None
        if location and "/" in location:
            branch, birthplace = (null_if_blank(x) for x in location.split("/", 1))
        else:
            branch = birthplace = None
        if age_weight and re.search(r"歳\s*/", age_weight):
            age = as_int(first_number(age_weight, r"(\d+)歳"))
            weight = as_float(first_number(age_weight, r"/\s*([0-9.]+)kg"))
        else:
            age = weight = None
        f_count = as_int(first_number(st_values[0] or "", r"F(\d+)")) if st_values else None
        l_count = as_int(first_number(st_values[1] or "", r"L(\d+)")) if len(st_values) > 1 else None
        # 今節成績はヘッダの「各日2列 × 4行（R/進入/ST/成績）」に従う。
        # 4行・14セルの対応が確認できない場合は、対応不明の配列として残す。
        meet_rows = rows[:4]
        meet_cells = []
        for row_index, row in enumerate(meet_rows):
            row_cells = row.find_all("td", recursive=False)
            meet_cells.append(row_cells[9:23] if row_index == 0 and len(row_cells) >= 23 else row_cells[:14])
        current_meet_results: list[dict[str, Any]] = []
        current_meet_unmapped: dict[str, list[Any]] | None = None
        if len(meet_cells) == 4 and all(len(row) == 14 for row in meet_cells):
            for index in range(14):
                race_text = null_if_blank(meet_cells[0][index].get_text(" ", strip=True))
                course_text = null_if_blank(meet_cells[1][index].get_text(" ", strip=True))
                st_text = null_if_blank(meet_cells[2][index].get_text(" ", strip=True))
                finish_text = null_if_blank(meet_cells[3][index].get_text(" ", strip=True))
                if any(value is not None for value in (race_text, course_text, st_text, finish_text)):
                    current_meet_results.append({
                        "day": (index // 2) + 1 if index < 12 else None,
                        "race": as_int(race_text),
                        "course": as_int(course_text),
                        "finish": finish_text,
                        "st": st_text,
                    })
        else:
            current_meet_unmapped = {
                "current_meet_race_numbers": [null_if_blank(c.get_text(" ", strip=True)) for c in meet_cells[0]] if len(meet_cells) > 0 else [],
                "current_meet_courses": [null_if_blank(c.get_text(" ", strip=True)) for c in meet_cells[1]] if len(meet_cells) > 1 else [],
                "current_meet_start_times": [null_if_blank(c.get_text(" ", strip=True)) for c in meet_cells[2]] if len(meet_cells) > 2 else [],
                "current_meet_finishes": [null_if_blank(c.get_text(" ", strip=True)) for c in meet_cells[3]] if len(meet_cells) > 3 else [],
            }
        joined = clean(body.get_text(" ", strip=True))
        racer = {
            "lane": int(lane),
            "registration_number": registration,
            "racer_name": name,
            "class": first_number(profile, r"\b([AB][12])\b"),
            "branch": branch, "birthplace": birthplace, "age": age, "weight": weight,
            "f_count": f_count, "l_count": l_count,
            "average_st": as_float(st_values[2]) if len(st_values) > 2 else None,
            "national_win_rate": as_float(national[0]) if national else None,
            "national_2ren_rate": as_float(national[1]) if len(national) > 1 else None,
            "national_3ren_rate": as_float(national[2]) if len(national) > 2 else None,
            "local_win_rate": as_float(local[0]) if local else None,
            "local_2ren_rate": as_float(local[1]) if len(local) > 1 else None,
            "local_3ren_rate": as_float(local[2]) if len(local) > 2 else None,
            "motor_number": as_int(motor[0]) if motor else None,
            "motor_2ren_rate": as_float(motor[1]) if len(motor) > 1 else None,
            "motor_3ren_rate": as_float(motor[2]) if len(motor) > 2 else None,
            "boat_number": as_int(boat[0]) if boat else None,
            "boat_2ren_rate": as_float(boat[1]) if len(boat) > 1 else None,
            "boat_3ren_rate": as_float(boat[2]) if len(boat) > 2 else None,
            "current_meet_results": current_meet_results if current_meet_unmapped is None else None,
            "course_performance": {
                "course_entry_count": None, "course_1st_rate": None, "course_2ren_rate": None,
                "course_3ren_rate": None, "course_average_st": None, "course_average_start_rank": None,
                "state": "NOT_AVAILABLE",
            },
            # サイト改修時も情報を捨てないため、各選手行の公式表示を併記する。
            "official_row_text": joined,
        }
        if current_meet_unmapped is not None:
            racer.update(current_meet_unmapped)
        value_fields = ("branch", "birthplace", "age", "weight", "f_count", "l_count", "average_st",
                        "national_2ren_rate", "national_3ren_rate", "local_2ren_rate", "local_3ren_rate",
                        "motor_3ren_rate", "boat_3ren_rate")
        racer["field_states"] = {key: asdict(state_for(racer[key])) for key in value_fields}
        racer["field_states"]["course_performance"] = asdict(state_for(None, available=False))
        racers.append(racer)
    if len(racers) != 6 or sorted(item["lane"] for item in racers) != [1, 2, 3, 4, 5, 6]:
        raise ValueError(f"出走表から6艇を取得できませんでした（取得数: {len(racers)}）。")
    # レース名・距離は title block、締切はレース一覧の「締切予定時刻」行から取得する。
    race_name_node = soup.select_one(".title16_titleDetail__add2020")
    race_title = clean(race_name_node.get_text(" ", strip=True)) if race_name_node else ""
    distance = as_int(first_number(race_title, r"(\d{3,4})m"))
    race_name = null_if_blank(re.sub(r"\s*\d{3,4}m\s*", " ", race_title))
    deadline = None
    for table2 in soup.find_all("table"):
        for row in table2.find_all("tr"):
            cells2 = row.find_all(["th", "td"], recursive=False)
            if cells2 and clean(cells2[0].get_text(" ", strip=True)) == "締切予定時刻" and len(cells2) > 4:
                deadline = null_if_blank(cells2[4].get_text(" ", strip=True))
                break
        if deadline:
            break
    active_day = soup.select_one(".tab2 li.is-active2")
    meeting_day_text = clean(active_day.get_text(" ", strip=True)) if active_day else ""
    meeting_day = as_int(first_number(meeting_day_text, r"(\d+)日目"))
    meeting_final_day = "最終日" in meeting_day_text
    race_type = race_name if race_name in {"一般", "予選", "特選", "準優勝戦", "優勝戦", "記者選抜"} else None
    race_info = {"race_name": race_name, "race_type": race_type, "deadline": deadline,
                 "meeting_day": meeting_day, "meeting_final_day": meeting_final_day, "distance_m": distance}
    race_states = {key: state_for(value) for key, value in race_info.items()}
    return sorted(racers, key=lambda item: item["lane"]), race_info, race_states


def parse_beforeinfo(html: str) -> tuple[list[dict[str, Any]], dict[str, FieldValue], dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    states: dict[str, FieldValue] = {}
    exhib_table = find_table(soup, ["展示", "タイム"])
    if exhib_table is None:
        raise ValueError("直前情報の展示タイムテーブルを検出できませんでした。")
    exhibitors: list[dict[str, Any]] = []
    for cells in table_text_rows(exhib_table):
        joined = " ".join(cells)
        lane = first_number(joined, r"^([1-6])(?:\s|$)")
        # 直前情報の選手表では、枠番と展示タイムの両方がある行のみ使う。
        time = first_number(joined, r"\b([6-9]\.\d{2})\b")
        if lane and time:
            exhibitors.append({"lane": int(lane), "exhibition_time": time})
    if len(exhibitors) != 6:
        raise ValueError(f"展示タイムを6艇分取得できませんでした（取得数: {len(exhibitors)}）。")

    # 「スタート展示」は多くの会場でテーブル外の見出しなので、表内の見出しだけで探す。
    start_table = find_table(soup, ["コース", "ST"])
    if start_table is None:
        raise ValueError("スタート展示テーブルを検出できませんでした（直前情報未公開の可能性があります）。")
    starts: list[dict[str, Any]] = []
    # スタート展示のテーブルは1行が1コースで、艇番は span の表示値として
    # 入る。艇番とコースを同一視せず、行順をコースとして保持する。
    for course, row in enumerate(start_table.select(".table1_boatImage1"), start=1):
        boat = row.select_one(".table1_boatImage1Number")
        st_node = row.select_one(".table1_boatImage1Time")
        boat_number = clean(boat.get_text(" ", strip=True)) if boat else None
        st = clean(st_node.get_text(" ", strip=True)) if st_node else None
        if boat_number and st:
            starts.append({
                "exhibition_course": course,
                "boat_number": int(boat_number),
                "start_exhibition_st": st,
            })
    if len(starts) != 6:
        raise ValueError(f"展示進入・スタート展示STを6艇分取得できませんでした（取得数: {len(starts)}）。")

    weather_heading = soup.find(string=re.compile(r"水面気象情報"))
    weather_container = weather_heading.parent if weather_heading else None
    # 見出しから親要素へ段階的に広げる。class名へ依存しない。
    weather_text = ""
    for _ in range(4):
        if weather_container is None:
            break
        weather_text = clean(weather_container.get_text(" ", strip=True))
        if all(label in weather_text for label in ("気温", "水温", "風速", "波高")):
            break
        weather_container = weather_container.parent
    if not weather_text or "気温" not in weather_text:
        raise ValueError("水面気象情報を検出できませんでした。")

    labels = {
        "temperature_c": r"気温\s*([0-9.]+)\s*℃",
        "water_temperature_c": r"水温\s*([0-9.]+)\s*℃",
        "wind_speed_mps": r"風速\s*([0-9.]+)\s*m",
        "wave_height_cm": r"波高\s*([0-9.]+)\s*cm",
    }
    weather: dict[str, Any] = {"weather_observation": first_number(weather_text, r"水面気象情報\s*([^ ]+現在|[^ ]+時点)")}
    for key, pattern in labels.items():
        states[key] = page_state(first_number(weather_text, pattern), found=True)
        weather[key] = states[key].value
    # 天候はテキスト／alt属性、風向は公式CSSの is-direction1〜16 を用いる。
    all_alt = " ".join(clean(img.get("alt", "")) for img in (weather_container or soup).find_all("img"))
    condition = first_number(weather_text, r"(?:気温[^℃]*℃\s*)(晴|曇|雨|雪|霧)") or first_number(all_alt, r"(晴|曇|雨|雪|霧)")
    wind_direction = first_number(all_alt, r"(北北東|北東|東北東|東南東|南東|南南東|南南西|南西|西南西|西北西|北西|北北西|北|東|南|西)")
    if not wind_direction:
        direction_node = (weather_container or soup).select_one(".weather1_bodyUnit.is-direction [class*='is-direction']")
        direction_class = " ".join(direction_node.get("class", [])) if direction_node else ""
        direction_number = first_number(direction_class, r"is-direction(1[0-6]|[1-9])")
        directions = {
            "1": "北", "2": "北北東", "3": "北東", "4": "東北東", "5": "東", "6": "東南東",
            "7": "南東", "8": "南南東", "9": "南", "10": "南南西", "11": "南西", "12": "西南西",
            "13": "西", "14": "西北西", "15": "北西", "16": "北北西",
        }
        wind_direction = directions.get(direction_number or "")
    states["weather"] = page_state(condition, found=True)
    states["wind_direction"] = page_state(wind_direction, found=True)
    weather["weather"] = states["weather"].value
    weather["wind_direction"] = states["wind_direction"].value
    return exhibitors, states, weather | {"start_exhibition": starts}


def fetch(date: str, venue: str, race: int) -> FetchResult:
    code = venue_code(venue)
    date = normalized_date(date)
    if not 1 <= race <= 12:
        raise ValueError("--race は1〜12で指定してください。")
    params = f"hd={date}&jcd={code}&rno={race}"
    urls = {"racecard": f"{BASE_URL}/racelist?{params}", "beforeinfo": f"{BASE_URL}/beforeinfo?{params}"}
    target = {"date": f"{date[:4]}-{date[4:6]}-{date[6:]}", "venue": VENUES[code], "venue_code": code, "race": race}
    now = datetime.now(JST).isoformat(timespec="seconds")
    try:
        with requests.Session() as session:
            session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.8"})
            racecard_html = request_page(session, urls["racecard"])
            beforeinfo_html = request_page(session, urls["beforeinfo"])
        racers, race_info, race_states = parse_racecard(racecard_html)
        exhibitors, states, weather = parse_beforeinfo(beforeinfo_html)
        states.update(race_states)
        starts = weather.pop("start_exhibition")
        for item in exhibitors:
            states[f"exhibition_time_{item['lane']}"] = page_state(item["exhibition_time"])
        for item in starts:
            states[f"start_exhibition_course_{item['exhibition_course']}"] = page_state(str(item["exhibition_course"]))
            states[f"start_exhibition_st_{item['exhibition_course']}"] = page_state(item["start_exhibition_st"])
        required = ["temperature_c", "water_temperature_c", "wind_speed_mps", "wave_height_cm", "weather", "wind_direction"]
        blanks = [name for name in required if states[name].state != "PRESENT"]
        if blanks:
            raise ValueError("直前情報ページ上で必須項目が空欄です: " + ", ".join(blanks))
        return FetchResult("success", None, None, target, now, urls, states, racers, exhibitors,
                           weather | {"start_exhibition": starts}, race_info)
    except requests.RequestException as exc:
        return FetchResult("failed", "PAGE_FETCH_FAILED", str(exc), target, now, urls)
    except (ValueError, KeyError) as exc:
        return FetchResult("failed", "PAGE_PARSED_BUT_REQUIRED_DATA_MISSING", str(exc), target, now, urls)


def jsonable(result: FetchResult) -> dict[str, Any]:
    data = asdict(result)
    data["field_states"] = {name: asdict(value) for name, value in result.field_states.items()}
    return data


def write_csv(result: FetchResult, path: Path) -> None:
    """CSVは1艇1行。レース全体情報を各行へ重複して直前予想で扱いやすくする。"""
    rows: list[dict[str, Any]] = []
    by_lane = {item["lane"]: item["exhibition_time"] for item in result.exhibition}
    starts = result.weather.get("start_exhibition", [])
    for racer in result.racecard_racers or [{}]:
        row = {
            "fetch_status": result.fetch_status, "failure_kind": result.failure_kind,
            "failure_message": result.failure_message, **result.target,
            "fetched_at": result.fetched_at, "racecard_url": result.source_urls["racecard"],
            "beforeinfo_url": result.source_urls["beforeinfo"], **result.race_info, **result.weather,
            **racer, "exhibition_time": by_lane.get(racer.get("lane")),
            "start_exhibition": json.dumps(starts, ensure_ascii=False),
            "field_states": json.dumps({k: asdict(v) for k, v in result.field_states.items()}, ensure_ascii=False),
        }
        for key in ("current_meet_results", "current_meet_race_numbers", "current_meet_courses",
                    "current_meet_start_times", "current_meet_finishes", "course_performance"):
            if key in row:
                row[key] = json.dumps(row[key], ensure_ascii=False)
        if isinstance(row.get("field_states"), dict):
            row["field_states"] = json.dumps(row["field_states"], ensure_ascii=False)
        rows.append(row)
    keys = [
        "fetch_status", "failure_kind", "failure_message", "date", "venue", "venue_code", "race", "fetched_at",
        "racecard_url", "beforeinfo_url", "race_name", "race_type", "deadline", "meeting_day", "meeting_final_day", "distance_m",
        "lane", "registration_number", "racer_name", "class", "branch", "birthplace", "age", "weight", "f_count", "l_count",
        "national_win_rate", "national_2ren_rate", "national_3ren_rate", "local_win_rate", "local_2ren_rate", "local_3ren_rate",
        "average_st", "motor_number", "motor_2ren_rate", "motor_3ren_rate", "boat_number", "boat_2ren_rate", "boat_3ren_rate",
        "current_meet_results", "current_meet_race_numbers", "current_meet_courses", "current_meet_start_times", "current_meet_finishes",
        "course_performance", "official_row_text", "exhibition_time", "start_exhibition",
        "weather_observation", "temperature_c", "water_temperature_c", "weather", "wind_direction", "wind_speed_mps", "wave_height_cm", "field_states",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="BOAT RACE公式の出走表・直前情報を取得します。")
    parser.add_argument("--date", required=True, help="YYYYMMDD または YYYY-MM-DD")
    parser.add_argument("--venue", required=True, help="会場名または会場コード（例: 三国 / 10）")
    parser.add_argument("--race", required=True, type=int, help="レース番号（1〜12）")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--output", help="出力パス。省略時はカレントディレクトリに作成")
    args = parser.parse_args()
    result = fetch(args.date, args.venue, args.race)
    suffix = args.format
    output = Path(args.output) if args.output else Path(f"{normalized_date(args.date)}_直前情報_{venue_code(args.venue)}_{args.race}R.{suffix}")
    if args.format == "json":
        output.write_text(json.dumps(jsonable(result), ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        write_csv(result, output)
    print(output.resolve())
    return 0 if result.fetch_status == "success" else 2


if __name__ == "__main__":
    sys.exit(main())
