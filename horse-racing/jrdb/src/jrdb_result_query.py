#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JRDB result/payout query for GPT and deterministic consumers.

Default response: 1st-3rd finishers from SED + all eight HJC payout types.
Fixed-width interpretation remains owned by jrdb_raw.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from jrdb_raw import Parser, canonical_members, race_key_parts, read_fixed_records

VERSION = "0.1.0"
SCHEMA_VERSION = "jrdb-result-query-v0.1"
HISTORICAL_YEAR_TO = 2025

VENUES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}
VENUE_ALIASES = {
    **{k: k for k in VENUES}, **{v: k for k, v in VENUES.items()},
    "SAPPORO":"01","HAKODATE":"02","FUKUSHIMA":"03","NIIGATA":"04",
    "TOKYO":"05","NAKAYAMA":"06","CHUKYO":"07","KYOTO":"08",
    "HANSHIN":"09","KOKURA":"10",
}
ABNORMAL = {"0":"異常なし","1":"取消","2":"除外","3":"中止","4":"失格","5":"降着","6":"再騎乗"}
BET_TYPES = ("win","place","frame_quinella","quinella","wide","exacta","trio","trifecta")
BET_ALIASES = {
    "win":"win","単勝":"win","place":"place","複勝":"place",
    "frame_quinella":"frame_quinella","枠連":"frame_quinella","枠連複":"frame_quinella",
    "quinella":"quinella","馬連":"quinella","馬連複":"quinella",
    "wide":"wide","ワイド":"wide","exacta":"exacta","馬単":"exacta",
    "trio":"trio","3連複":"trio","三連複":"trio",
    "trifecta":"trifecta","3連単":"trifecta","三連単":"trifecta",
}
ORDERED = {"exacta","trifecta"}


class ResultQueryError(RuntimeError):
    pass


def parse_date(value: str) -> dt.date:
    compact = re.sub(r"[^0-9]", "", value)
    if len(compact) == 6:
        compact = "20" + compact
    try:
        return dt.datetime.strptime(compact, "%Y%m%d").date()
    except ValueError as exc:
        raise ResultQueryError(f"invalid date: {value!r}") from exc


def normalize_venue(value: str | None) -> str | None:
    if value is None:
        return None
    token = value.strip()
    code = VENUE_ALIASES.get(token) or VENUE_ALIASES.get(token.upper())
    if code is None:
        raise ResultQueryError(f"unknown JRA venue: {value!r}")
    return code


def normalize_bet_types(values: Sequence[str] | None) -> list[str]:
    if not values:
        return list(BET_TYPES)
    out = []
    for value in values:
        token = value.strip()
        key = BET_ALIASES.get(token) or BET_ALIASES.get(token.lower())
        if key is None:
            raise ResultQueryError(f"unknown bet type: {value!r}")
        if key not in out:
            out.append(key)
    return out


def _member_matches(member: str, family: str, date: dt.date) -> bool:
    name = Path(member).name.upper()
    family = family.upper()
    return name in {f"{family}{date:%y%m%d}.TXT", f"{family}{date:%Y%m%d}.TXT"}


def _archives(family: str, date: dt.date, raw_root: Path | None, explicit: Path | None) -> list[Path]:
    if explicit is not None:
        if not explicit.is_file():
            raise ResultQueryError(f"missing {family} archive: {explicit}")
        return [explicit]
    if raw_root is None:
        return []
    family = family.upper()
    names = (f"{family}{date:%y%m%d}.zip", f"{family}_{date.year}.zip")
    found = []
    for root in (raw_root / family, raw_root):
        for name in names:
            path = root / name
            if path.is_file() and path not in found:
                found.append(path)
    return found


def _read_raw_family(
    family: str, date: dt.date, *, raw_root: Path | None, explicit: Path | None
) -> tuple[list[dict[str, Any]], list[str]]:
    parser = Parser()
    rows, used = [], []
    for path in _archives(family, date, raw_root, explicit):
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise ResultQueryError(f"bad ZIP member in {path}: {bad}")
            members = [m for m in canonical_members(archive, family) if _member_matches(m, family, date)]
            if not members:
                continue
            used.append(str(path))
            for member in members:
                records = read_fixed_records(archive, member, family)
                if not records:
                    raise ResultQueryError(f"invalid {family} fixed-width member: {path}!{member}")
                for record in records:
                    parsed = getattr(parser, family.lower())(record)
                    if family == "SED" and str(parsed.get("date_raw") or "") != date.strftime("%Y%m%d"):
                        continue
                    rows.append(parsed)
    return rows, used


def load_raw_rows(
    date: dt.date, *, raw_root: Path | None = None, sed: Path | None = None, hjc: Path | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    sed_rows, sed_sources = _read_raw_family("SED", date, raw_root=raw_root, explicit=sed)
    hjc_rows, hjc_sources = _read_raw_family("HJC", date, raw_root=raw_root, explicit=hjc)
    payouts = []
    for race in hjc_rows:
        for bet_type in BET_TYPES:
            for slot_no, slot in enumerate(race[bet_type], 1):
                numbers = list(slot["numbers"])
                payouts.append({
                    "race_key_raw": race["race_key_raw"], "bet_type": bet_type,
                    "slot_no": slot_no, "combination_raw": slot["combination_raw"],
                    "horse_no_1": numbers[0] if len(numbers) > 0 else None,
                    "horse_no_2": numbers[1] if len(numbers) > 1 else None,
                    "horse_no_3": numbers[2] if len(numbers) > 2 else None,
                    "payout": slot["payout"],
                })
    return sed_rows, payouts, {
        "source_mode":"raw", "sed_archives":sed_sources, "hjc_archives":hjc_sources
    }


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResultQueryError(f"unreadable JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ResultQueryError(f"JSON object required: {path}")
    return value


def _warehouse_paths(manifest: Mapping[str, Any], root: Path, family: str, year: int) -> list[Path]:
    result = []
    for asset in manifest.get("assets") or []:
        if str(asset.get("family") or "").lower() != family.lower() or int(asset.get("year",-1)) != year:
            continue
        path = root / str(asset.get("relative_path") or "")
        if not path.is_file():
            raise ResultQueryError(f"missing Warehouse asset: {path}")
        result.append(path)
    return sorted(result)


def _duckdb_rows(paths: Sequence[Path], iso_date: str) -> list[dict[str, Any]]:
    if not paths:
        return []
    try:
        import duckdb
    except ImportError as exc:
        raise ResultQueryError("Warehouse query requires duckdb") from exc
    con = duckdb.connect(":memory:")
    try:
        placeholders = ", ".join("?" for _ in paths)
        cur = con.execute(
            f"SELECT * FROM read_parquet([{placeholders}], union_by_name=true) WHERE source_member_date=?",
            [*[str(p) for p in paths], iso_date],
        )
        names = [d[0] for d in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]
    finally:
        con.close()


def load_warehouse_rows(
    date: dt.date, *, warehouse_root: Path, warehouse_manifest: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if date.year > HISTORICAL_YEAR_TO:
        raise ResultQueryError("accepted historical Warehouse coverage ends at 2025")
    manifest = _json(warehouse_manifest)
    if manifest.get("status") != "PASS":
        raise ResultQueryError("Warehouse manifest is not PASS")
    sed_paths = _warehouse_paths(manifest, warehouse_root, "sed", date.year)
    hjc_paths = _warehouse_paths(manifest, warehouse_root, "hjc_payout", date.year)
    iso = date.isoformat()
    return (
        _duckdb_rows(sed_paths, iso),
        _duckdb_rows(hjc_paths, iso),
        {
            "source_mode":"warehouse",
            "source_generation_id":manifest.get("generation_id"),
            "warehouse_manifest":str(warehouse_manifest),
            "sed_assets":[str(p) for p in sed_paths],
            "hjc_payout_assets":[str(p) for p in hjc_paths],
        },
    )


def _empty_slot(row: Mapping[str, Any]) -> bool:
    nums = [row.get("horse_no_1"), row.get("horse_no_2"), row.get("horse_no_3")]
    return all(v in (None,0,"","0","00") for v in nums) and row.get("payout") in (None,0,"","0")


def _payout(row: Mapping[str, Any]) -> dict[str, Any]:
    bet_type = str(row["bet_type"])
    nums = [int(v) for v in (row.get("horse_no_1"),row.get("horse_no_2"),row.get("horse_no_3")) if v not in (None,"")]
    ordered = bet_type in ORDERED
    return {
        "slot_no":int(row.get("slot_no") or 0),
        "numbers":nums,
        "combination_text":("→" if ordered else "-").join(str(v) for v in nums),
        "payout_yen":int(row["payout"]) if row.get("payout") is not None else None,
        "ordered":ordered,
        "number_kind":"frame" if bet_type == "frame_quinella" else "horse",
    }


def _runner(row: Mapping[str, Any]) -> dict[str, Any]:
    abnormal = str(row.get("abnormal_code") or "")
    finish = row.get("finish")
    return {
        "finish":int(finish) if finish is not None else None,
        "horse_no":int(row["horse_no"]) if row.get("horse_no") is not None else None,
        "horse_name":str(row.get("horse_name") or "").strip(),
        "final_win_popularity":int(row["final_popularity"]) if row.get("final_popularity") is not None else None,
        "final_win_odds":row.get("final_win_odds"),
        "abnormal_code":abnormal,
        "abnormal_label":ABNORMAL.get(abnormal, "不明" if abnormal else ""),
        "completed_normally":abnormal in ("","0"),
    }


def _cross_validate(sed: Sequence[Mapping[str, Any]], payouts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    details, overall = {}, "pass"
    for bet_type, sed_field in (("win","win_payout"),("place","place_payout")):
        s = sorted(
            (int(r["horse_no"]), int(r[sed_field])) for r in sed
            if r.get("horse_no") is not None and r.get(sed_field) not in (None,0,"","0")
        )
        h = sorted(
            (int(r["horse_no_1"]), int(r["payout"])) for r in payouts
            if r.get("bet_type") == bet_type and not _empty_slot(r)
            and r.get("horse_no_1") is not None and r.get("payout") is not None
        )
        status = "not_applicable" if not s or not h else ("pass" if s == h else "mismatch")
        if status == "mismatch":
            overall = "mismatch"
        details[bet_type] = {"status":status,"sed":s,"hjc":h}
    if overall == "pass" and all(v["status"] == "not_applicable" for v in details.values()):
        overall = "not_applicable"
    return {"status":overall,"details":details,"review_required":overall == "mismatch"}


def assemble_result(
    *, date: dt.date, sed_rows: Sequence[Mapping[str, Any]], payout_rows: Sequence[Mapping[str, Any]],
    source_provenance: Mapping[str, Any], venue_code: str | None = None, race_no: int | None = None,
    bet_types: Sequence[str] | None = None, include_all_runners: bool = False,
    include_empty_slots: bool = False,
) -> dict[str, Any]:
    requested = normalize_bet_types(bet_types)
    by_sed, by_pay = defaultdict(list), defaultdict(list)
    for row in sed_rows:
        if row.get("race_key_raw"):
            by_sed[str(row["race_key_raw"])].append(row)
    for row in payout_rows:
        if row.get("race_key_raw"):
            by_pay[str(row["race_key_raw"])].append(row)
    keys = []
    for key in sorted(set(by_sed) | set(by_pay)):
        parts = race_key_parts(key)
        if venue_code and parts.get("venue_code") != venue_code:
            continue
        if race_no is not None and parts.get("race_no") != race_no:
            continue
        keys.append(key)
    if not keys:
        raise ResultQueryError("no JRDB race matched the requested scope")

    races, miss_sed, miss_hjc, mismatch = [], False, False, False
    for key in keys:
        parts, sed, pay = race_key_parts(key), list(by_sed.get(key,[])), list(by_pay.get(key,[]))
        runners = sorted((_runner(r) for r in sed), key=lambda r:(r["finish"] is None,r["finish"] or 999,r["horse_no"] or 999))
        top3 = [r for r in runners if r["finish"] is not None and 1 <= r["finish"] <= 3]
        payout_map = {}
        for bet_type in requested:
            values = [
                r for r in pay if r.get("bet_type") == bet_type and (include_empty_slots or not _empty_slot(r))
            ]
            payout_map[bet_type] = [_payout(r) for r in sorted(values,key=lambda x:int(x.get("slot_no") or 0))]
        cross = _cross_validate(sed,pay)
        mismatch = mismatch or cross["review_required"]
        miss_sed = miss_sed or not sed
        miss_hjc = miss_hjc or not pay
        item = {
            "race_date":date.isoformat(),"venue_code":parts.get("venue_code"),
            "venue_name":VENUES.get(str(parts.get("venue_code") or ""),""),
            "race_no":parts.get("race_no"),"race_key":key,"top3":top3,
            "payouts":payout_map,
            "result_status":"available" if sed else "unavailable",
            "payouts_status":"available" if pay else "unavailable",
            "cross_validation":cross,
        }
        if include_all_runners:
            item["all_runners"] = runners
        races.append(item)

    missing = (["SED"] if miss_sed else []) + (["HJC"] if miss_hjc else [])
    status = "partial" if missing else ("review_required" if mismatch else "success")
    return {
        "schema_version":SCHEMA_VERSION,"tool_version":VERSION,"status":status,
        "query":{
            "date":date.isoformat(),"venue_code":venue_code,
            "venue_name":VENUES.get(venue_code or "") if venue_code else None,
            "race_no":race_no,"bet_types":requested,"include_all_runners":include_all_runners,
        },
        "race_count":len(races),"races":races,"missing_sources":missing,
        "provenance":{**dict(source_provenance),"result_source":"SED","payout_source":"HJC","web_used":False},
    }


def query_results(
    *, date: str | dt.date, venue: str | None = None, race_no: int | None = None,
    bet_types: Sequence[str] | None = None, include_all_runners: bool = False,
    include_empty_slots: bool = False, source: str = "auto", raw_root: Path | None = None,
    sed: Path | None = None, hjc: Path | None = None, warehouse_root: Path | None = None,
    warehouse_manifest: Path | None = None,
) -> dict[str, Any]:
    target = date if isinstance(date, dt.date) else parse_date(date)
    venue_code = normalize_venue(venue)
    if race_no is not None and not 1 <= int(race_no) <= 12:
        raise ResultQueryError("race_no must be between 1 and 12")
    source = source.lower()
    if source not in {"auto","raw","warehouse"}:
        raise ResultQueryError("source must be auto, raw, or warehouse")
    if source == "auto":
        source = "warehouse" if target.year <= HISTORICAL_YEAR_TO and warehouse_root and warehouse_manifest else "raw"
    if source == "warehouse":
        if warehouse_root is None or warehouse_manifest is None:
            raise ResultQueryError("warehouse source requires --warehouse-root and --warehouse-manifest")
        sed_rows, pay_rows, provenance = load_warehouse_rows(
            target, warehouse_root=warehouse_root, warehouse_manifest=warehouse_manifest
        )
    else:
        if raw_root is None and sed is None and hjc is None:
            raise ResultQueryError("raw source requires --raw-root and/or explicit --sed/--hjc")
        sed_rows, pay_rows, provenance = load_raw_rows(target, raw_root=raw_root, sed=sed, hjc=hjc)
    return assemble_result(
        date=target,sed_rows=sed_rows,payout_rows=pay_rows,source_provenance=provenance,
        venue_code=venue_code,race_no=race_no,bet_types=bet_types,
        include_all_runners=include_all_runners,include_empty_slots=include_empty_slots,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="JRDB top-3 result + all-payout JSON query")
    ap.add_argument("--date",required=True)
    ap.add_argument("--venue")
    ap.add_argument("--race",dest="race_no",type=int)
    ap.add_argument("--bet-type",dest="bet_types",action="append")
    ap.add_argument("--include-all-runners",action="store_true")
    ap.add_argument("--include-empty-slots",action="store_true")
    ap.add_argument("--source",choices=("auto","raw","warehouse"),default="auto")
    ap.add_argument("--raw-root",type=Path)
    ap.add_argument("--sed",type=Path)
    ap.add_argument("--hjc",type=Path)
    ap.add_argument("--warehouse-root",type=Path)
    ap.add_argument("--warehouse-manifest",type=Path)
    ap.add_argument("--output",type=Path)
    ap.add_argument("--pretty",action="store_true")
    ap.add_argument("--version",action="version",version=VERSION)
    args = ap.parse_args()
    try:
        result = query_results(
            date=args.date,venue=args.venue,race_no=args.race_no,bet_types=args.bet_types,
            include_all_runners=args.include_all_runners,include_empty_slots=args.include_empty_slots,
            source=args.source,raw_root=args.raw_root,sed=args.sed,hjc=args.hjc,
            warehouse_root=args.warehouse_root,warehouse_manifest=args.warehouse_manifest,
        )
        text_value = json.dumps(result,ensure_ascii=False,indent=2 if args.pretty else None) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(text_value,encoding="utf-8")
        sys.stdout.write(text_value)
        return 3 if result["status"] == "partial" else (4 if result["status"] == "review_required" else 0)
    except (ResultQueryError,FileNotFoundError,zipfile.BadZipFile) as exc:
        print(json.dumps({"schema_version":SCHEMA_VERSION,"status":"error","error":str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
