#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministically settle frozen RaceNote predictions against JRDB HJC."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jrdb_raw import Parser, race_key_parts, read_fixed_records

PROTOCOL_VERSION = "0.1"
UNIT_STAKE_JPY = 100
JRA_VENUE_CODES = {
    "札幌": "01", "函館": "02", "福島": "03", "新潟": "04", "東京": "05",
    "中山": "06", "中京": "07", "京都": "08", "阪神": "09", "小倉": "10",
}

@dataclass(frozen=True)
class Ticket:
    group: str
    wager: str
    horses: tuple[int, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"group": self.group, "wager": self.wager, "horses": list(self.horses), "stake_jpy": UNIT_STAKE_JPY}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _member_name_for_date(date: str) -> str:
    digits = date.replace("-", "")
    if len(digits) != 8 or not digits.isdigit():
        raise ValueError(f"invalid race date: {date!r}")
    return f"HJC{digits[2:]}.txt"


def _extract_mark_horses(race: dict[str, Any]) -> dict[str, int]:
    marks = race.get("prediction", {}).get("marks")
    if not isinstance(marks, list):
        raise ValueError("prediction.marks must be a list")
    singles: dict[str, int] = {}
    deltas: list[int] = []
    for row in marks:
        if not isinstance(row, dict):
            continue
        mark = row.get("mark")
        horse_no = row.get("horse_no")
        if not isinstance(horse_no, int) or horse_no <= 0:
            raise ValueError(f"invalid horse_no in marks: {horse_no!r}")
        if mark in {"◎", "○", "▲"} and mark not in singles:
            singles[mark] = horse_no
        elif mark == "△":
            deltas.append(horse_no)
    missing = [mark for mark in ("◎", "○", "▲") if mark not in singles]
    if missing:
        raise ValueError(f"missing required marks: {missing}")
    if len(deltas) < 2:
        raise ValueError("settlement protocol v0.1 requires at least two △ marks")
    return {"honmei": singles["◎"], "taikou": singles["○"], "tanana": singles["▲"], "delta1": deltas[0], "delta2": deltas[1]}


def build_tickets(race: dict[str, Any]) -> list[Ticket]:
    m = _extract_mark_horses(race)
    honmei = m["honmei"]
    opponents = [m["taikou"], m["tanana"], m["delta1"], m["delta2"]]
    tickets = [
        Ticket("1", "win", (honmei,)),
        Ticket("2", "quinella", tuple(sorted((honmei, m["taikou"])))),
        Ticket("2", "quinella", tuple(sorted((honmei, m["tanana"])))),
    ]
    for left in range(len(opponents)):
        for right in range(left + 1, len(opponents)):
            tickets.append(Ticket("3", "trio", tuple(sorted((honmei, opponents[left], opponents[right])))))
    if sum(ticket.group == "3" for ticket in tickets) != 6:
        raise AssertionError("protocol v0.1 trio construction must yield six tickets")
    return tickets


def _normalize_numbers(numbers: Iterable[Any]) -> tuple[int, ...] | None:
    normalized: list[int] = []
    for value in numbers:
        if not isinstance(value, int) or value <= 0:
            return None
        normalized.append(value)
    return tuple(sorted(normalized))


def payout_for_ticket(ticket: Ticket, parsed_hjc: dict[str, Any]) -> int:
    slots = parsed_hjc.get(ticket.wager)
    if not isinstance(slots, list):
        raise ValueError(f"HJC parsed payload missing wager list: {ticket.wager}")
    payout = 0
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        normalized = _normalize_numbers(slot.get("numbers") or [])
        slot_payout = slot.get("payout")
        if normalized == ticket.horses and isinstance(slot_payout, int) and slot_payout > 0:
            payout += slot_payout
    return payout


def find_hjc_race(archive: Path, *, date: str, venue: str, race_no: int, parser: Parser | None = None) -> tuple[str, bytes, dict[str, Any]]:
    venue_code = JRA_VENUE_CODES.get(venue)
    if venue_code is None:
        raise ValueError(f"unsupported JRA venue label: {venue!r}")
    if not isinstance(race_no, int) or not 1 <= race_no <= 12:
        raise ValueError(f"invalid race number: {race_no!r}")
    expected_member = _member_name_for_date(date)
    parser = parser or Parser()
    matches: list[tuple[str, bytes, dict[str, Any]]] = []
    with zipfile.ZipFile(archive) as zf:
        member = next((name for name in zf.namelist() if Path(name).name.upper() == expected_member.upper()), None)
        if member is None:
            raise LookupError(f"{expected_member} not found in {archive}")
        for record in read_fixed_records(zf, member, "HJC"):
            parsed = parser.hjc(record)
            parts = race_key_parts(parsed["race_key_raw"])
            if parts["venue_code"] == venue_code and parts["race_no"] == race_no:
                matches.append((member, record, parsed))
    if len(matches) != 1:
        raise LookupError(f"expected exactly one HJC race for {date} {venue}{race_no}R; found {len(matches)}")
    return matches[0]


def settle_race(race: dict[str, Any], archive: Path, *, parser: Parser | None = None) -> dict[str, Any]:
    date, venue, race_no = race.get("date"), race.get("venue"), race.get("race_no")
    if not isinstance(date, str) or not isinstance(venue, str) or not isinstance(race_no, int):
        raise ValueError("race must contain date:str, venue:str, race_no:int")
    member, record, parsed = find_hjc_race(archive, date=date, venue=venue, race_no=race_no, parser=parser)
    settled_tickets: list[dict[str, Any]] = []
    group_payouts = {"1": 0, "2": 0, "3": 0}
    group_investments = {"1": 0, "2": 0, "3": 0}
    for ticket in build_tickets(race):
        payout = payout_for_ticket(ticket, parsed)
        row = ticket.as_dict(); row["payout_jpy"] = payout; row["hit"] = payout > 0
        settled_tickets.append(row)
        group_payouts[ticket.group] += payout
        group_investments[ticket.group] += UNIT_STAKE_JPY
    winning = {}
    for wager in ("win", "quinella", "trio"):
        winning[wager] = [{"numbers": slot["numbers"], "payout_jpy": slot["payout"]} for slot in parsed[wager]
            if _normalize_numbers(slot.get("numbers") or []) is not None and isinstance(slot.get("payout"), int) and slot["payout"] > 0]
    return {"date": date, "venue": venue, "race_no": race_no, "race_key_raw": parsed["race_key_raw"],
        "hjc_member": Path(member).name, "hjc_record_sha256": hashlib.sha256(record).hexdigest(),
        "marks_used": _extract_mark_horses(race), "tickets": settled_tickets,
        "group_investment_jpy": group_investments, "group_payout_jpy": group_payouts, "winning_hjc": winning}


PATTERNS: dict[str, tuple[str, ...]] = {"1": ("1",), "2": ("2",), "3": ("3",), "1+2": ("1", "2"), "1+3": ("1", "3"), "1+2+3": ("1", "2", "3")}


def summarize(races: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for pattern, groups in PATTERNS.items():
        investment = payout = hit_races = 0
        for race in races:
            race_investment = sum(race["group_investment_jpy"][group] for group in groups)
            race_payout = sum(race["group_payout_jpy"][group] for group in groups)
            investment += race_investment; payout += race_payout; hit_races += int(race_payout > 0)
        race_count = len(races)
        summary[pattern] = {"race_count": race_count, "investment_jpy": investment, "payout_jpy": payout,
            "hit_races": hit_races, "hit_rate": hit_races / race_count if race_count else None,
            "return_rate": payout / investment if investment else None}
    return summary


def settle_prediction_file(prediction_path: Path, hjc_archive: Path) -> dict[str, Any]:
    payload = json.loads(prediction_path.read_text(encoding="utf-8"))
    races = payload.get("races")
    if not isinstance(races, list) or not races:
        raise ValueError("prediction file must contain non-empty races[]")
    parser = Parser()
    settled = [settle_race(race, hjc_archive, parser=parser) for race in races]
    return {"settlement_protocol_version": PROTOCOL_VERSION, "status": "SETTLED_AFTER_FREEZE", "unit_stake_jpy": UNIT_STAKE_JPY,
        "prediction_source": {"file_name": prediction_path.name, "sha256": _sha256(prediction_path), "logic_profile": payload.get("logic_profile"), "freeze_status": payload.get("status")},
        "hjc_source": {"file_name": hjc_archive.name, "sha256": _sha256(hjc_archive)}, "races": settled, "summary": summarize(settled)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prediction", type=Path, required=True)
    ap.add_argument("--hjc", type=Path, required=True, help="annual or daily HJC ZIP")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = settle_prediction_file(args.prediction, args.hjc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
