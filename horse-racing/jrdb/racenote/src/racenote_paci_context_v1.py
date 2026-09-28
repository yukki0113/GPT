#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract neutral RaceNote v1 race context directly from PACI BAC.

This module is intentionally separate from the legacy RaceNote converter.
It only exposes target-race facts needed by the redesigned Evidence Note and
Trend sample selector.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[4]
JRDB_SRC = ROOT / "horse-racing" / "jrdb" / "src"
if str(JRDB_SRC) not in sys.path:
    sys.path.insert(0, str(JRDB_SRC))

from jrdb_raw import Parser, read_fixed_records

SCHEMA_VERSION = "RaceNote-PACI-Context-1.0"

VENUES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}
SURFACES = {"1": "芝", "2": "ダート", "3": "障害"}
RACE_CLASS = {
    "04": "1勝クラス", "05": "1勝クラス",
    "08": "2勝クラス", "09": "2勝クラス", "10": "2勝クラス",
    "15": "3勝クラス", "16": "3勝クラス",
    "A1": "新馬", "A2": "未出走", "A3": "未勝利", "OP": "オープン",
}
GRADES = {"1": "G1", "2": "G2", "3": "G3", "4": "重賞", "5": "特別", "6": "L"}
COURSE_RAIL = {"1": "A", "2": "A1", "3": "A2", "4": "B", "5": "C", "6": "D"}
TURN = {"1": "右", "2": "左", "3": "直線", "9": "その他"}
LAYOUT = {"1": "通常（内）", "2": "外", "3": "直線ダート", "9": "その他"}


class PaciContextError(RuntimeError):
    pass


def _ymd(raw: object) -> str | None:
    text = str(raw or "")
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return None


def _meeting_day(raw: str) -> int | None:
    try:
        return int(raw.lower(), 16)
    except (ValueError, AttributeError):
        return None


def _bac_member(archive: zipfile.ZipFile) -> str:
    matches = [
        name for name in archive.namelist()
        if Path(name).name.upper().startswith("BAC")
        and Path(name).name.upper().endswith(".TXT")
    ]
    if len(matches) != 1:
        raise PaciContextError(f"expected exactly one BAC member, found {len(matches)}")
    return matches[0]


def extract_paci_context(paci: Path) -> dict[str, Any]:
    parser = Parser()
    with zipfile.ZipFile(paci) as archive:
        member = _bac_member(archive)
        records = read_fixed_records(archive, member, "BAC")
        if not records:
            raise PaciContextError("BAC contains no valid records")
        races = []
        for record in records:
            raw = parser.bac(record)
            key = str(raw.get("race_key_raw") or "")
            if len(key) != 8:
                raise PaciContextError(f"invalid race key: {key!r}")
            venue_code = key[:2]
            meeting_no = int(key[4]) if key[4].isdigit() else None
            meeting_day = _meeting_day(key[5])
            race_no = int(key[6:8]) if key[6:8].isdigit() else None
            distance_raw = str(raw.get("distance_raw") or "")
            distance = int(distance_raw) if distance_raw.isdigit() else None
            source_codes = {
                "venue_code": venue_code,
                "surface_code": str(raw.get("surface_code") or ""),
                "race_class_code": str(raw.get("race_class_code") or ""),
                "grade_code": str(raw.get("grade_code") or ""),
                "course_code": str(raw.get("course_code") or ""),
            }
            races.append({
                "race_key": key,
                "date": _ymd(raw.get("date_raw")),
                "venue": VENUES.get(venue_code, venue_code),
                "meeting_no": meeting_no,
                "meeting_day": meeting_day,
                "race_no": race_no,
                "race_name": raw.get("race_name"),
                "surface": SURFACES.get(source_codes["surface_code"]),
                "distance_m": distance,
                "class": RACE_CLASS.get(source_codes["race_class_code"]),
                "grade": GRADES.get(source_codes["grade_code"]),
                "turn": TURN.get(str(raw.get("turn_code") or "")),
                "course_layout": LAYOUT.get(str(raw.get("layout_code") or "")),
                "course_rail": COURSE_RAIL.get(source_codes["course_code"]),
                "source_codes": source_codes,
            })
    dates = sorted({race["date"] for race in races if race.get("date")})
    return {
        "schema_version": SCHEMA_VERSION,
        "source": "JRDB PACI BAC",
        "source_file": paci.name,
        "date": dates[0] if len(dates) == 1 else None,
        "races": sorted(races, key=lambda row: (str(row["venue"]), int(row["race_no"] or 99))),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paci", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = extract_paci_context(args.paci)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "date": result["date"], "races": len(result["races"]), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
