#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Settle frozen RaceNote marks against same-day top-3/payout results."""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

VERSION = "racenote-daily-settlement-0.1.0"
UNIT_STAKE_JPY = 100
UNORDERED_WAGERS = {"quinella", "wide", "trio", "frame_quinella"}

STRATEGIES = {
    "honmei_win": ("◎ 単勝", "win"),
    "honmei_place": ("◎ 複勝", "place"),
    "quinella_second": ("馬連 ◎－○", "quinella"),
    "quinella_shot": ("馬連 ◎－▲", "quinella"),
    "quinella_main": ("馬連 ◎－○▲", "quinella"),
    "exacta_second": ("馬単 ◎→○", "exacta"),
    "exacta_shot": ("馬単 ◎→▲", "exacta"),
    "exacta_main": ("馬単 ◎→○▲", "exacta"),
    "trio_flow": ("3連複 ◎1頭軸－他印流し", "trio"),
    "trifecta_flow": ("3連単 ◎1着固定－他印流し", "trifecta"),
}


@dataclass(frozen=True)
class MarkedHorse:
    mark: str
    horse_no: int
    horse_name: str = ""


@dataclass(frozen=True)
class Ticket:
    strategy: str
    wager: str
    horses: tuple[int, ...]
    marks: tuple[str, ...]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_forecast_records(path: Path) -> list[dict[str, Any]]:
    value = _load_json(path)
    if isinstance(value, list):
        records = value
    elif isinstance(value, dict) and isinstance(value.get("races"), list):
        records = value["races"]
    elif isinstance(value, dict):
        records = [value]
    else:
        raise ValueError("forecast JSON must be a record, list, or object containing races[]")
    if not records:
        raise ValueError("forecast contains no races")
    return records


def race_identity(record: dict[str, Any]) -> tuple[str, str, int]:
    ident = record.get("identity") if isinstance(record.get("identity"), dict) else record
    target_date = ident.get("target_date") or ident.get("date")
    venue = ident.get("venue")
    race_no = ident.get("race_no")
    if not isinstance(target_date, str) or not isinstance(venue, str) or not isinstance(race_no, int):
        raise ValueError(f"forecast race identity is incomplete: {ident}")
    return target_date, venue, race_no


def extract_marks(record: dict[str, Any]) -> list[MarkedHorse]:
    marks = (record.get("prediction") or {}).get("marks")
    out: list[MarkedHorse] = []
    if isinstance(marks, dict):
        roles = (("◎", marks.get("main")), ("○", marks.get("second")), ("▲", marks.get("third")))
        for symbol, item in roles:
            if not isinstance(item, dict):
                raise ValueError(f"missing {symbol} mark")
            out.append(MarkedHorse(symbol, int(item["horse_no"]), str(item.get("horse_name") or "")))
        others = marks.get("others") or []
        if not isinstance(others, list):
            raise ValueError("prediction.marks.others must be a list")
        for index, item in enumerate(others, start=1):
            if not isinstance(item, dict):
                continue
            out.append(MarkedHorse(f"△{index}", int(item["horse_no"]), str(item.get("horse_name") or "")))
    elif isinstance(marks, list):
        delta_index = 0
        for item in marks:
            if not isinstance(item, dict) or not isinstance(item.get("horse_no"), int):
                continue
            symbol = str(item.get("mark") or "")
            if symbol == "△":
                delta_index += 1
                symbol = f"△{delta_index}"
            out.append(MarkedHorse(symbol, item["horse_no"], str(item.get("horse_name") or "")))
    else:
        raise ValueError("prediction.marks must be dict or list")

    required = {"◎", "○", "▲"}
    found = {row.mark for row in out}
    missing = required - found
    if missing:
        raise ValueError(f"forecast marks missing: {sorted(missing)}")
    if len({row.horse_no for row in out}) != len(out):
        raise ValueError("forecast marks contain duplicate horse numbers")
    if len(out) < 3:
        raise ValueError("at least ◎○▲ are required")
    return out


def _mark_map(marks: Iterable[MarkedHorse]) -> dict[str, MarkedHorse]:
    return {row.mark: row for row in marks}


def build_tickets(record: dict[str, Any]) -> list[Ticket]:
    marks = extract_marks(record)
    by_mark = _mark_map(marks)
    honmei = by_mark["◎"]
    second = by_mark["○"]
    third = by_mark["▲"]
    opponents = [row for row in marks if row.mark != "◎"]

    tickets = [
        Ticket("honmei_win", "win", (honmei.horse_no,), (honmei.mark,)),
        Ticket("honmei_place", "place", (honmei.horse_no,), (honmei.mark,)),
        Ticket("quinella_main", "quinella", (honmei.horse_no, second.horse_no), (honmei.mark, second.mark)),
        Ticket("quinella_main", "quinella", (honmei.horse_no, third.horse_no), (honmei.mark, third.mark)),
        Ticket("exacta_main", "exacta", (honmei.horse_no, second.horse_no), (honmei.mark, second.mark)),
        Ticket("exacta_main", "exacta", (honmei.horse_no, third.horse_no), (honmei.mark, third.mark)),
    ]
    for i in range(len(opponents)):
        for j in range(i + 1, len(opponents)):
            a, b = opponents[i], opponents[j]
            tickets.append(Ticket("trio_flow", "trio", (honmei.horse_no, a.horse_no, b.horse_no), (honmei.mark, a.mark, b.mark)))
    for i, a in enumerate(opponents):
        for j, b in enumerate(opponents):
            if i == j:
                continue
            tickets.append(Ticket("trifecta_flow", "trifecta", (honmei.horse_no, a.horse_no, b.horse_no), (honmei.mark, a.mark, b.mark)))
    return tickets


def _normalize_combo(wager: str, values: Iterable[Any]) -> tuple[int, ...] | None:
    try:
        combo = tuple(int(value) for value in values)
    except (TypeError, ValueError):
        return None
    if any(value <= 0 for value in combo):
        return None
    return tuple(sorted(combo)) if wager in UNORDERED_WAGERS else combo


def payout_for_ticket(ticket: Ticket, result_race: dict[str, Any]) -> int:
    slots = (result_race.get("payouts") or {}).get(ticket.wager) or []
    expected = _normalize_combo(ticket.wager, ticket.horses)
    payout = 0
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        combo = _normalize_combo(ticket.wager, slot.get("combination") or [])
        value = slot.get("payout_jpy")
        if combo == expected and isinstance(value, int) and value > 0:
            payout += value
    return payout


def _ticket_text(ticket: Ticket) -> str:
    sep = "→" if ticket.wager in {"exacta", "trifecta"} else "－"
    return sep.join(str(value) for value in ticket.horses)


def _mark_text(ticket: Ticket) -> str:
    sep = "→" if ticket.wager in {"exacta", "trifecta"} else "－"
    return sep.join(ticket.marks)


def settle(forecast_records: list[dict[str, Any]], results: dict[str, Any], *, top_n: int = 3) -> dict[str, Any]:
    result_index: dict[tuple[str, str, int], dict[str, Any]] = {}
    for race in results.get("races") or []:
        key = (str(race.get("date")), str(race.get("venue")), int(race.get("race_no")))
        result_index[key] = race

    strategy_rows = {
        code: {
            "code": code,
            "label": label,
            "wager": wager,
            "settled_races": 0,
            "ticket_count": 0,
            "stake_jpy": 0,
            "hit_tickets": 0,
            "hit_races": 0,
            "payout_jpy": 0,
            "profit_jpy": 0,
            "return_rate_pct": None,
            "top_payout_tickets": [],
        }
        for code, (label, wager) in STRATEGIES.items()
    }
    top_candidates: dict[str, list[dict[str, Any]]] = {code: [] for code in STRATEGIES}
    race_details: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    review_required: list[dict[str, Any]] = []

    for record in forecast_records:
        key = race_identity(record)
        result_race = result_index.get(key)
        if result_race is None or result_race.get("status") == "pending":
            pending.append({"date": key[0], "venue": key[1], "race_no": key[2]})
            continue
        if result_race.get("status") != "official":
            review_required.append({"date": key[0], "venue": key[1], "race_no": key[2], "status": result_race.get("status")})
            continue

        tickets = build_tickets(record)
        by_strategy: dict[str, list[dict[str, Any]]] = {code: [] for code in STRATEGIES}
        race_ticket_items: list[dict[str, Any]] = []

        def record_strategy(code: str, item: dict[str, Any]) -> None:
            by_strategy[code].append(item)
            row = strategy_rows[code]
            row["ticket_count"] += 1
            row["stake_jpy"] += UNIT_STAKE_JPY
            row["payout_jpy"] += item["payout_jpy"]
            row["hit_tickets"] += int(item["hit"])
            if item["hit"]:
                top_candidates[code].append({
                    "date": key[0], "venue": key[1], "race_no": key[2],
                    "ticket": item["ticket"], "marks": item["mark_ticket"],
                    "payout_jpy": item["payout_jpy"],
                })

        for ticket in tickets:
            payout = payout_for_ticket(ticket, result_race)
            item = {
                "strategy": ticket.strategy,
                "wager": ticket.wager,
                "horses": list(ticket.horses),
                "marks": list(ticket.marks),
                "ticket": _ticket_text(ticket),
                "mark_ticket": _mark_text(ticket),
                "stake_jpy": UNIT_STAKE_JPY,
                "payout_jpy": payout,
                "hit": payout > 0,
            }
            race_ticket_items.append(item)
            record_strategy(ticket.strategy, item)

            # Keep the physical 24-ticket formation unchanged while exposing
            # ○ and ▲ contribution as separate analytical settlement rows.
            if ticket.strategy == "quinella_main":
                record_strategy(
                    "quinella_second" if ticket.marks == ("◎", "○") else "quinella_shot",
                    item,
                )
            elif ticket.strategy == "exacta_main":
                record_strategy(
                    "exacta_second" if ticket.marks == ("◎", "○") else "exacta_shot",
                    item,
                )

        for code in STRATEGIES:
            row = strategy_rows[code]
            row["settled_races"] += 1
            row["hit_races"] += int(any(item["hit"] for item in by_strategy[code]))
        race_details.append({
            "date": key[0], "venue": key[1], "race_no": key[2],
            "tickets": race_ticket_items,
        })

    for code, row in strategy_rows.items():
        row["profit_jpy"] = row["payout_jpy"] - row["stake_jpy"]
        row["return_rate_pct"] = round(row["payout_jpy"] / row["stake_jpy"] * 100, 1) if row["stake_jpy"] else None
        row["top_payout_tickets"] = sorted(
            top_candidates[code], key=lambda item: (-item["payout_jpy"], item["date"], item["venue"], item["race_no"])
        )[:top_n]

    return {
        "schema_version": "RaceNote-SameDay-Settlement-0.1",
        "settlement_version": VERSION,
        "unit_stake_jpy": UNIT_STAKE_JPY,
        "forecast_race_count": len(forecast_records),
        "settled_race_count": len(race_details),
        "pending_race_count": len(pending),
        "review_required_race_count": len(review_required),
        "pending_races": pending,
        "review_required_races": review_required,
        "strategies": list(strategy_rows.values()),
        "races": race_details,
    }


def render_markdown(payload: dict[str, Any], *, title_date: str | None = None) -> str:
    lines = [f"# RaceNote 当日成績{f' — {title_date}' if title_date else ''}", ""]
    lines += [
        f"- 予想対象: {payload['forecast_race_count']}R",
        f"- 精算済み: {payload['settled_race_count']}R",
        f"- 未確定: {payload['pending_race_count']}R",
        f"- 要確認: {payload['review_required_race_count']}R",
        f"- 1点: {payload['unit_stake_jpy']}円",
        "",
    ]
    for row in payload["strategies"]:
        lines.append(f"## {row['label']}")
        rate = "-" if row["return_rate_pct"] is None else f"{row['return_rate_pct']:.1f}%"
        sign_profit = f"{row['profit_jpy']:+,}円"
        lines += [
            f"- 購入: {row['ticket_count']}点 / {row['stake_jpy']:,}円",
            f"- 的中: {row['hit_tickets']}点（{row['hit_races']}R）",
            f"- 払戻: {row['payout_jpy']:,}円",
            f"- 収支: {sign_profit}",
            f"- 回収率: **{rate}**",
            "",
            "### 払戻TOP",
        ]
        if row["top_payout_tickets"]:
            for rank, item in enumerate(row["top_payout_tickets"], start=1):
                lines.append(
                    f"{rank}. {item['venue']}{item['race_no']}R "
                    f"{item['marks']}（{item['ticket']}） — **{item['payout_jpy']:,}円**"
                )
        else:
            lines.append("- 的中なし")
        lines.append("")
    if payload["pending_races"]:
        text = ", ".join(f"{r['venue']}{r['race_no']}R" for r in payload["pending_races"])
        lines += ["## 未確定R", text, ""]
    if payload["review_required_races"]:
        text = ", ".join(f"{r['venue']}{r['race_no']}R" for r in payload["review_required_races"])
        lines += ["## 要確認R", text, ""]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--forecast", type=Path, required=True, help="freeze済み forecast_*_all.json 等")
    ap.add_argument("--results", type=Path, required=True, help="racenote_daily_result_fetch.py のJSON")
    ap.add_argument("--output-json", type=Path)
    ap.add_argument("--output-md", type=Path)
    ap.add_argument("--top", type=int, default=3, help="方式ごとの払戻TOP件数")
    args = ap.parse_args()
    if args.top < 1:
        ap.error("--top は1以上を指定してください")

    forecasts = load_forecast_records(args.forecast)
    results = _load_json(args.results)
    payload = settle(forecasts, results, top_n=args.top)
    payload["sources"] = {
        "forecast": {"path": str(args.forecast), "sha256": _sha256(args.forecast)},
        "results": {"path": str(args.results), "sha256": _sha256(args.results), "provider": (results.get("source") or {}).get("provider")},
    }
    target_dates = sorted({race_identity(record)[0] for record in forecasts})
    title_date = target_dates[0] if len(target_dates) == 1 else None

    compact = title_date.replace("-", "") if title_date else "multi"
    root = Path(__file__).resolve().parents[1] / "settlement_runs"
    output_json = args.output_json or (root / f"RaceNote_{compact}_SameDay_Settlement.json")
    output_md = args.output_md or (root / f"RaceNote_{compact}_SameDay_Settlement.md")
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(render_markdown(payload, title_date=title_date), encoding="utf-8")
    print(json.dumps({
        "status": "success" if payload["review_required_race_count"] == 0 else "review_required",
        "settled_races": payload["settled_race_count"],
        "pending_races": payload["pending_race_count"],
        "output_json": str(output_json),
        "output_md": str(output_md),
        "return_rates_pct": {row["code"]: row["return_rate_pct"] for row in payload["strategies"]},
    }, ensure_ascii=False, indent=2))
    return 0 if payload["review_required_race_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
