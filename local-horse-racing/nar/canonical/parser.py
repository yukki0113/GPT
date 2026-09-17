from __future__ import annotations

import csv
from dataclasses import dataclass
import datetime as dt
import hashlib
import io
import re
import zipfile
from collections import defaultdict

from nar.schema import HORSELIST_COLUMNS, PAYBACK_COLUMNS, RACELIST_COLUMNS


class CanonicalParseError(ValueError):
    pass


@dataclass
class CanonicalBatch:
    source_name: str
    source_yyyymm: str
    tables: dict[str, list[dict]]


_ALLOWANCE_RE = re.compile(r"^([^0-9+\-.]*)([-+]?\d+(?:\.\d+)?)$")
_BEST_TIME_RE = re.compile(r"^(?:[^0-9]*)?(?:(\d+):)?(\d{1,2})\.(\d)$")


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _int(value: str | None) -> int | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _float(value: str | None) -> float | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_yyyymmdd(value: str | None) -> str | None:
    text = _clean(value)
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return dt.date(int(text[:4]), int(text[4:6]), int(text[6:8])).isoformat()
    except ValueError:
        return None


def parse_mssf_seconds(value: str | None) -> float | None:
    """Parse NAR horselist finish time MSSF, e.g. 591 -> 59.1, 1143 -> 74.3."""
    text = _clean(value)
    if not text or not text.isdigit() or len(text) < 3:
        return None
    tenths = int(text[-1])
    seconds = int(text[-3:-1])
    minutes_text = text[:-3]
    minutes = int(minutes_text) if minutes_text else 0
    if seconds >= 60:
        return None
    return minutes * 60 + seconds + tenths / 10.0


def parse_best_time_seconds(value: str | None) -> float | None:
    text = _clean(value)
    if not text:
        return None
    match = _BEST_TIME_RE.fullmatch(text)
    if not match:
        return None
    minutes = int(match.group(1) or 0)
    seconds = int(match.group(2))
    tenths = int(match.group(3))
    if seconds >= 60:
        return None
    return minutes * 60 + seconds + tenths / 10.0


def parse_assigned_weight(value: str | None) -> tuple[str, float | None, str]:
    text = _clean(value)
    if not text:
        return "", None, ""
    match = _ALLOWANCE_RE.fullmatch(text)
    if not match:
        return text, None, ""
    mark = match.group(1)
    return text, float(match.group(2)), mark


def make_race_id(venue: str, race_date_raw: str, race_no: int | None) -> str:
    if not venue or not race_date_raw or race_no is None:
        raise CanonicalParseError("race key requires venue/date/race_no")
    return f"{race_date_raw}:{venue}:{race_no:02d}"


def make_runner_id(race_id: str, horse_no: int | None) -> str:
    if horse_no is None:
        raise CanonicalParseError("runner key requires horse_no")
    return f"{race_id}:{horse_no:02d}"


def make_horse_key(horse_name: str, birth_date_raw: str, sire_name: str) -> str:
    payload = "\x1f".join((_clean(horse_name), _clean(birth_date_raw), _clean(sire_name)))
    return "narh:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _csv_rows(archive: zipfile.ZipFile, name: str, expected_header: tuple[str, ...]) -> list[dict[str, str]]:
    try:
        raw = archive.read(name)
    except KeyError as exc:
        raise CanonicalParseError(f"missing ZIP member: {name}") from exc
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if tuple(reader.fieldnames or ()) != tuple(expected_header):
        raise CanonicalParseError(f"header mismatch: {name}")
    return list(reader)


def _race_key(row: dict[str, str]) -> tuple[str, str, int]:
    venue = _clean(row["競馬場"])
    date_raw = _clean(row["競走年月日"])
    race_no = _int(row["レース番号"])
    if race_no is None:
        raise CanonicalParseError("invalid race number")
    return venue, date_raw, race_no


def _base_race(row: dict[str, str], yyyymm: str) -> dict:
    venue, date_raw, race_no = _race_key(row)
    race_date = parse_yyyymmdd(date_raw)
    if race_date is None:
        raise CanonicalParseError(f"invalid race date: {date_raw}")
    race_id = make_race_id(venue, date_raw, race_no)
    return {
        "race_id": race_id,
        "race_date": race_date,
        "race_year": int(date_raw[:4]),
        "venue": venue,
        "race_no": race_no,
        "source_yyyymm": yyyymm,
    }


def _parse_pre_race(row: dict[str, str], yyyymm: str) -> dict:
    out = _base_race(row, yyyymm)
    out.update({
        "post_time": _clean(row["発走時刻"]),
        "race_type_name": _clean(row["競走種類名称"]),
        "race_name": _clean(row["レース名"]),
        **{f"prize_name_{i:02d}": _clean(row[f"副賞名{i}"]) for i in range(1, 16)},
        "surface": _clean(row["芝ダート区分"]),
        "direction": _clean(row["回り"]),
        "distance_m": _int(row["距離"]),
        "weather": _clean(row["天候"]),
        "track_condition": _clean(row["馬場"]),
        "field_size": _int(row["頭数"]),
        "conditions": _clean(row["条件"]),
        **{f"prize_yen_{i}": _int(row[f"{i}着賞金(円)"]) for i in range(1, 6)},
    })
    return out


def _parse_post_race(row: dict[str, str], yyyymm: str) -> dict:
    out = _base_race(row, yyyymm)
    out.update({
        "final_4f_raw": _clean(row["上がり4F"]),
        "final_3f_raw": _clean(row["上がり3F"]),
        **{f"furlong_time_{i:02d}": _clean(row[f"ハロンタイム{i}"]) for i in range(1, 16)},
        **{f"corner_name_{i:02d}": _clean(row[f"コーナー名称{i}"]) for i in range(1, 9)},
        **{f"corner_order_{i:02d}": _clean(row[f"コーナー通過順{i}"]) for i in range(1, 9)},
    })
    return out


def _runner_base(row: dict[str, str], race: dict, yyyymm: str) -> dict:
    horse_no = _int(row["馬番"])
    race_id = race["race_id"]
    runner_id = make_runner_id(race_id, horse_no)
    horse_key = make_horse_key(row["馬名"], row["生年月日"], row["父馬名"])
    return {
        "race_id": race_id,
        "race_date": race["race_date"],
        "race_year": race["race_year"],
        "venue": race["venue"],
        "race_no": race["race_no"],
        "runner_id": runner_id,
        "horse_key": horse_key,
        "horse_no": horse_no,
        "source_yyyymm": yyyymm,
    }


def _parse_pre_runner(row: dict[str, str], race: dict, yyyymm: str) -> dict:
    out = _runner_base(row, race, yyyymm)
    weight_raw, assigned_weight, allowance = parse_assigned_weight(row["負担重量"])
    body_raw = _clean(row["馬体重"])
    body_delta_raw = _clean(row["馬体重増減"])
    out.update({
        "gate": _int(row["枠番"]),
        "cap_color": _clean(row["帽色"]),
        "horse_name": _clean(row["馬名"]),
        "sex": _clean(row["性"]),
        "age": _int(row["齢"]),
        "coat_color": _clean(row["毛色"]),
        "birth_date": parse_yyyymmdd(row["生年月日"]),
        "sire_name": _clean(row["父馬名"]),
        "dam_name": _clean(row["母馬名"]),
        "damsire_name": _clean(row["母父馬名"]),
        "jockey_name": _clean(row["騎手名"]),
        "jockey_affiliation": _clean(row["騎手所属"]),
        "assigned_weight_raw": weight_raw,
        "assigned_weight": assigned_weight,
        "allowance_mark": allowance,
        "trainer_name": _clean(row["調教師"]),
        "trainer_affiliation": _clean(row["調教師所属"]),
        "owner_name": _clean(row["馬主氏名"]),
        "breeder_name": _clean(row["生産牧場名"]),
        "body_weight_raw": body_raw,
        "body_weight_kg": _int(body_raw),
        "body_weight_change_raw": body_delta_raw,
        "body_weight_change_kg": _int(body_delta_raw.replace("+", "")),
    })
    return out


def _parse_history(row: dict[str, str], race: dict, yyyymm: str) -> dict:
    out = _runner_base(row, race, yyyymm)
    out.update({
        "distance_m": race.get("distance_m"),
        "surface": race.get("surface", ""),
        "direction": race.get("direction", ""),
        "track_condition": race.get("track_condition", ""),
        "jockey_name": _clean(row["騎手名"]),
        "jockey_record_raw": _clean(row["騎手成績"]),
        "overall_record_raw": _clean(row["全成績"]),
        "dirt_left_record_raw": _clean(row["ダート左成績"]),
        "dirt_right_record_raw": _clean(row["ダート右成績"]),
        "venue_record_raw": _clean(row["当競馬場成績"]),
        "venue_distance_record_raw": _clean(row["うち当距離成績"]),
        "best_time_raw": _clean(row["最高タイム"]),
        "best_time_seconds": parse_best_time_seconds(row["最高タイム"]),
        "best_time_good_raw": _clean(row["最高タイム良馬場"]),
        "best_time_good_seconds": parse_best_time_seconds(row["最高タイム良馬場"]),
        "leakage_status": "PENDING_VALIDATION",
    })
    return out


def _parse_post_runner(row: dict[str, str], race: dict, yyyymm: str) -> dict:
    out = _runner_base(row, race, yyyymm)
    finish_raw = _clean(row["着順"])
    final3_raw = _clean(row["上がり3F"])
    out.update({
        "finish_position_raw": finish_raw,
        "finish_position": _int(finish_raw),
        "finish_time_raw": _clean(row["タイム"]),
        "finish_time_seconds": parse_mssf_seconds(row["タイム"]),
        "margin": _clean(row["着差"]),
        "final_3f_raw": final3_raw,
        "final_3f_seconds": _float(final3_raw),
        "popularity": _int(row["人気"]),
    })
    return out


PAYBACK_SPECS = (
    ("WIN", ("単勝組番",), "単勝払戻金（円）", "単勝人気"),
    ("PLACE", ("複勝組番1",), "複勝払戻金1（円）", "複勝人気1"),
    ("PLACE", ("複勝組番2",), "複勝払戻金2（円）", "複勝人気2"),
    ("PLACE", ("複勝組番3",), "複勝払戻金3（円）", "複勝人気3"),
    ("BRACKET_QUINELLA", ("枠複組番1", "枠複組番2"), "枠複払戻金（円）", "枠複人気"),
    ("BRACKET_EXACTA", ("枠単組番1", "枠単組番2"), "枠単払戻金（円）", "枠単人気"),
    ("QUINELLA", ("馬複組番1", "馬複組番2"), "馬複払戻金（円）", "馬複人気1"),
    ("EXACTA", ("馬単組番1", "馬単組番2"), "馬単払戻金（円）", "馬単人気1"),
    ("WIDE", ("ワイド組番1馬番1", "ワイド組番1馬番2"), "ワイド払戻金1（円）", "ワイド人気1"),
    ("WIDE", ("ワイド組番2馬番1", "ワイド組番2馬番2"), "ワイド払戻金2（円）", "ワイド人気2"),
    ("WIDE", ("ワイド組番3馬番1", "ワイド組番3馬番2"), "ワイド払戻金3（円）", "ワイド人気3"),
    ("TRIO", ("３連複組番馬番1", "３連複組番馬番2", "３連複組番馬番3"), "３連複払戻金（円）", "３連複人気"),
    ("TRIFECTA", ("３連単組番馬番1", "３連単組番馬番2", "３連単組番馬番3"), "３連単払戻金（円）", "３連単人気"),
)


def _parse_payouts(rows: list[dict[str, str]], race_lookup: dict[tuple[str, str, int], dict], yyyymm: str) -> list[dict]:
    output: list[dict] = []
    per_race_counter: dict[str, int] = defaultdict(int)
    for raw_row in rows:
        key = _race_key(raw_row)
        race = race_lookup.get(key)
        if race is None:
            raise CanonicalParseError(f"payback race not found in racelist: {key}")
        race_id = race["race_id"]
        per_race_counter[race_id] += 1
        row_no = per_race_counter[race_id]
        for bet_type, selection_fields, payout_field, popularity_field in PAYBACK_SPECS:
            payout_text = _clean(raw_row[payout_field])
            selections = [_clean(raw_row[field]) for field in selection_fields]
            if not payout_text and not any(selections):
                continue
            selection_values = (selections + ["", "", ""])[:3]
            output.append({
                **{key: race[key] for key in ("race_id", "race_date", "race_year", "venue", "race_no")},
                "payback_row_no": row_no,
                "bet_type": bet_type,
                "selection1": selection_values[0],
                "selection2": selection_values[1],
                "selection3": selection_values[2],
                "payout_yen": _int(payout_text),
                "popularity": _int(raw_row[popularity_field]),
                "source_yyyymm": yyyymm,
            })
    return output


def _refund_like(raw_payback_rows: list[dict[str, str]]) -> bool:
    if not raw_payback_rows:
        return False
    seen_payout = False
    selection_fields = {field for _, fields, _, _ in PAYBACK_SPECS for field in fields}
    payout_fields = {payout for _, _, payout, _ in PAYBACK_SPECS}
    for row in raw_payback_rows:
        if any(_clean(row[field]) for field in selection_fields):
            return False
        for field in payout_fields:
            value = _clean(row[field])
            if value:
                seen_payout = True
                if value != "100":
                    return False
    return seen_payout


def _build_race_status(
    races: list[dict], runners: list[dict], raw_runner_rows: list[dict[str, str]], raw_payback_rows: list[dict[str, str]], yyyymm: str,
) -> list[dict]:
    runners_by_race: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row, parsed in zip(raw_runner_rows, runners):
        runners_by_race[parsed["race_id"]].append(row)
    payback_by_key: dict[tuple[str, str, int], list[dict[str, str]]] = defaultdict(list)
    for row in raw_payback_rows:
        payback_by_key[_race_key(row)].append(row)

    output = []
    for race in races:
        race_id = race["race_id"]
        raw_runners = runners_by_race.get(race_id, [])
        finish_count = sum(1 for row in raw_runners if _int(row["着順"]) is not None)
        key = (race["venue"], race["race_date"].replace("-", ""), race["race_no"])
        pay_rows = payback_by_key.get(key, [])
        if finish_count > 0 and pay_rows:
            status, model, returns, reason = "NORMAL", True, True, "result_and_payback_present"
        elif finish_count > 0 and not pay_rows:
            status, model, returns, reason = "DATA_MISSING", True, False, "result_present_but_payback_missing"
        elif finish_count == 0 and _refund_like(pay_rows):
            status, model, returns, reason = "REFUNDED", False, False, "no_finish_and_refund_payback"
        elif finish_count == 0 and pay_rows:
            status, model, returns, reason = "CANCELLED", False, False, "no_finish_with_nonstandard_payback"
        else:
            status, model, returns, reason = "NO_RESULT", False, False, "no_finish_and_no_payback"
        output.append({
            **{key: race[key] for key in ("race_id", "race_date", "race_year", "venue", "race_no")},
            "status": status,
            "is_model_target": model,
            "is_return_target": returns,
            "reason": reason,
            "runner_count": len(raw_runners),
            "finish_count": finish_count,
            "payback_row_count": len(pay_rows),
            "source_yyyymm": yyyymm,
        })
    return output


def parse_monthly_race_zip(content: bytes, source_name: str = "monthly_race.zip") -> CanonicalBatch:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise CanonicalParseError("not a readable ZIP") from exc

    member_names = archive.namelist()
    racelist_candidates = [name for name in member_names if name.endswith("_racelist.csv")]
    if len(racelist_candidates) != 1:
        raise CanonicalParseError("expected exactly one *_racelist.csv")
    yyyymm = racelist_candidates[0].rsplit("_racelist.csv", 1)[0][-6:]
    expected = {
        f"{yyyymm}_racelist.csv",
        f"{yyyymm}_horselist.csv",
        f"{yyyymm}_payback.csv",
    }
    if set(member_names) != expected:
        raise CanonicalParseError(f"unexpected race ZIP members: {sorted(member_names)!r}")

    race_rows = _csv_rows(archive, f"{yyyymm}_racelist.csv", RACELIST_COLUMNS)
    horse_rows = _csv_rows(archive, f"{yyyymm}_horselist.csv", HORSELIST_COLUMNS)
    payback_rows = _csv_rows(archive, f"{yyyymm}_payback.csv", PAYBACK_COLUMNS)

    pre_race = [_parse_pre_race(row, yyyymm) for row in race_rows]
    race_lookup = {
        (row["venue"], row["race_date"].replace("-", ""), row["race_no"]): row
        for row in pre_race
    }
    post_race = [_parse_post_race(row, yyyymm) for row in race_rows]

    pre_runner: list[dict] = []
    history: list[dict] = []
    post_runner: list[dict] = []
    for row in horse_rows:
        key = _race_key(row)
        race = race_lookup.get(key)
        if race is None:
            raise CanonicalParseError(f"horselist race not found in racelist: {key}")
        pre_runner.append(_parse_pre_runner(row, race, yyyymm))
        history.append(_parse_history(row, race, yyyymm))
        post_runner.append(_parse_post_runner(row, race, yyyymm))

    post_payout = _parse_payouts(payback_rows, race_lookup, yyyymm)
    race_status = _build_race_status(pre_race, pre_runner, horse_rows, payback_rows, yyyymm)

    return CanonicalBatch(source_name=source_name, source_yyyymm=yyyymm, tables={
        "pre_race": pre_race,
        "pre_runner": pre_runner,
        "pre_runner_history_snapshot": history,
        "post_race_result": post_race,
        "post_runner_result": post_runner,
        "post_payout": post_payout,
        "control_race_status": race_status,
    })
