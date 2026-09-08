#!/usr/bin/env python3
"""Audit frozen RaceNote marks against HJC at the betting-role level.

This tool does not alter prediction marks or the frozen settlement protocol. It
splits current v0.1 quinella and trio tickets by mark role, and compares the
six-ticket trio axis with the five-ticket formation that excludes ◎-△1-△2.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jrdb_raw import Parser, read_fixed_records

VENUE_CODES = {
    "札幌": "01", "函館": "02", "福島": "03", "新潟": "04", "東京": "05",
    "中山": "06", "中京": "07", "京都": "08", "阪神": "09", "小倉": "10",
}
RACE_RE = re.compile(r"^(札幌|函館|福島|新潟|東京|中山|中京|京都|阪神|小倉)(\d{1,2})R$")
DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")


def _horse_no(cell: str) -> int:
    m = re.match(r"\s*(\d{1,2})(?:\s|$)", cell)
    if not m:
        raise ValueError(f"horse number not found in cell: {cell!r}")
    return int(m.group(1))


def _race_from_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for race in payload["races"]:
        by_mark: dict[str, list[int]] = defaultdict(list)
        for mark in race["prediction"]["marks"]:
            by_mark[str(mark["mark"])].append(int(mark["horse_no"]))
        if not by_mark["◎"] or not by_mark["○"] or not by_mark["▲"] or len(by_mark["△"]) < 2:
            raise ValueError(f"missing required marks in {path}: {race.get('venue')} {race.get('race_no')}")
        rows.append({
            "date": str(race["date"]),
            "venue": str(race["venue"]),
            "race_no": int(race["race_no"]),
            "confidence": race.get("prediction", {}).get("confidence"),
            "marks": [by_mark["◎"][0], by_mark["○"][0], by_mark["▲"][0], by_mark["△"][0], by_mark["△"][1]],
            "source_file": str(path),
        })
    return rows


def _race_from_markdown(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    single_date = None
    title_dates = DATE_RE.findall(lines[0] if lines else "")
    if len(title_dates) == 1:
        single_date = title_dates[0]

    header_idx = None
    headers: list[str] = []
    for i, line in enumerate(lines):
        if line.startswith("|") and "◎" in line and "○" in line and "▲" in line and "△1" in line and "△2" in line:
            headers = [c.strip() for c in line.strip().strip("|").split("|")]
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"prediction table not found: {path}")

    required = ["Race", "◎", "○", "▲", "△1", "△2"]
    for name in required:
        if name not in headers:
            raise ValueError(f"missing column {name!r}: {path}")
    index = {name: headers.index(name) for name in headers}

    out = []
    for line in lines[header_idx + 1:]:
        if not line.startswith("|"):
            if out:
                break
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or all(set(c) <= {"-", ":"} for c in cells if c):
            continue
        if len(cells) != len(headers):
            continue
        race_cell = cells[index["Race"]]
        m = RACE_RE.match(race_cell)
        if not m:
            continue
        venue, race_no_s = m.groups()
        date = cells[index["Date"]] if "Date" in index else single_date
        if not date or not DATE_RE.fullmatch(date):
            raise ValueError(f"date unresolved for {race_cell} in {path}")
        out.append({
            "date": date,
            "venue": venue,
            "race_no": int(race_no_s),
            "confidence": cells[index["Conf"]] if "Conf" in index else None,
            "marks": [
                _horse_no(cells[index["◎"]]),
                _horse_no(cells[index["○"]]),
                _horse_no(cells[index["▲"]]),
                _horse_no(cells[index["△1"]]),
                _horse_no(cells[index["△2"]]),
            ],
            "source_file": str(path),
        })
    return out


def load_predictions(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.suffix.lower() == ".json":
            rows.extend(_race_from_json(path))
        else:
            rows.extend(_race_from_markdown(path))
    seen = set()
    for row in rows:
        key = (row["date"], row["venue"], row["race_no"])
        if key in seen:
            raise ValueError(f"duplicate prediction race: {key}")
        seen.add(key)
    return rows


def load_hjc_zip(path: Path) -> dict[str, dict[str, Any]]:
    parser = Parser()
    out: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path) as zf:
        members = [n for n in zf.namelist() if Path(n).name.upper().startswith("HJC") and n.lower().endswith(".txt")]
        if len(members) != 1:
            raise ValueError(f"expected exactly one HJC txt member in {path}, got {members}")
        for record in read_fixed_records(zf, members[0], "HJC"):
            parsed = parser.hjc(record)
            out[parsed["race_key_raw"]] = parsed
    return out


def load_hjc_map(items: Iterable[str]) -> dict[str, dict[str, dict[str, Any]]]:
    out = {}
    for item in items:
        if "=" not in item:
            raise ValueError("--hjc must be DATE=PATH")
        date, raw_path = item.split("=", 1)
        out[date] = load_hjc_zip(Path(raw_path))
    return out


def normalized_slot(slot: dict[str, Any]) -> tuple[int, ...] | None:
    nums = slot["numbers"]
    if any(n in (None, 0) for n in nums):
        return None
    return tuple(sorted(int(n) for n in nums))


def settle_ticket(ticket: tuple[int, ...], slots: list[dict[str, Any]]) -> int:
    key = tuple(sorted(ticket))
    return sum(int(slot.get("payout") or 0) for slot in slots if normalized_slot(slot) == key)


def race_key_for(race: dict[str, Any], candidates: dict[str, dict[str, Any]]) -> str:
    venue_code = VENUE_CODES[race["venue"]]
    yy = race["date"][2:4]
    race_no = int(race["race_no"])
    matches = [key for key in candidates if key[:2] == venue_code and key[2:4] == yy and key[6:8] == f"{race_no:02d}"]
    if len(matches) != 1:
        raise ValueError(f"expected one HJC race for {race['date']} {race['venue']}{race_no}R, got {matches}")
    return matches[0]


def metric_row(investment: int, payout: int, hits: int, races: int) -> dict[str, Any]:
    return {
        "race_count": races,
        "investment_jpy": investment,
        "payout_jpy": payout,
        "hit_races": hits,
        "hit_rate": hits / races if races else None,
        "return_rate": payout / investment if investment else None,
    }


def audit(predictions: list[dict[str, Any]], hjc_by_date: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    q_labels = ["◎-○", "◎-▲"]
    trio_labels = ["◎○▲", "◎○△", "◎▲△", "◎△△"]
    q_payout = defaultdict(int); q_hits = defaultdict(int)
    trio_payout = defaultdict(int); trio_hits = defaultdict(int)
    block = defaultdict(lambda: {
        "races": 0,
        "q_payout": defaultdict(int), "q_hits": defaultdict(int),
        "trio_payout": defaultdict(int), "trio_hits": defaultdict(int),
    })
    race_rows = []

    for race in predictions:
        date = race["date"]
        if date not in hjc_by_date:
            raise ValueError(f"HJC not supplied for {date}")
        hjc_map = hjc_by_date[date]
        key = race_key_for(race, hjc_map)
        payout = hjc_map[key]
        o, maru, ana, d1, d2 = race["marks"]
        q_tickets = {
            "◎-○": tuple(sorted((o, maru))),
            "◎-▲": tuple(sorted((o, ana))),
        }
        trio_tickets = {
            "◎○▲": [tuple(sorted((o, maru, ana)))],
            "◎○△": [tuple(sorted((o, maru, d1))), tuple(sorted((o, maru, d2)))],
            "◎▲△": [tuple(sorted((o, ana, d1))), tuple(sorted((o, ana, d2)))],
            "◎△△": [tuple(sorted((o, d1, d2)))],
        }
        q_result = {}
        for label, ticket in q_tickets.items():
            value = settle_ticket(ticket, payout["quinella"])
            q_result[label] = value
            q_payout[label] += value
            q_hits[label] += int(value > 0)
        trio_result = {}
        for label, tickets in trio_tickets.items():
            value = sum(settle_ticket(t, payout["trio"]) for t in tickets)
            trio_result[label] = value
            trio_payout[label] += value
            trio_hits[label] += int(value > 0)

        b = block[date]
        b["races"] += 1
        for label, value in q_result.items():
            b["q_payout"][label] += value
            b["q_hits"][label] += int(value > 0)
        for label, value in trio_result.items():
            b["trio_payout"][label] += value
            b["trio_hits"][label] += int(value > 0)

        race_rows.append({
            "date": date, "venue": race["venue"], "race_no": race["race_no"],
            "marks": {"◎": o, "○": maru, "▲": ana, "△1": d1, "△2": d2},
            "quinella_role_payout_jpy": q_result,
            "trio_role_payout_jpy": trio_result,
        })

    n = len(predictions)
    quinella = {
        "◎-○": metric_row(n * 100, q_payout["◎-○"], q_hits["◎-○"], n),
        "◎-▲": metric_row(n * 100, q_payout["◎-▲"], q_hits["◎-▲"], n),
    }
    quinella["current_2_ticket"] = metric_row(
        n * 200,
        q_payout["◎-○"] + q_payout["◎-▲"],
        sum(1 for r in race_rows if sum(r["quinella_role_payout_jpy"].values()) > 0),
        n,
    )

    trio_ticket_counts = {"◎○▲": 1, "◎○△": 2, "◎▲△": 2, "◎△△": 1}
    trio = {
        label: metric_row(n * 100 * trio_ticket_counts[label], trio_payout[label], trio_hits[label], n)
        for label in trio_labels
    }
    current_trio_payout = sum(trio_payout.values())
    current_trio_hits = sum(1 for r in race_rows if sum(r["trio_role_payout_jpy"].values()) > 0)
    formation5_payout = current_trio_payout - trio_payout["◎△△"]
    formation5_hits = sum(1 for r in race_rows if (
        r["trio_role_payout_jpy"]["◎○▲"] + r["trio_role_payout_jpy"]["◎○△"] + r["trio_role_payout_jpy"]["◎▲△"]
    ) > 0)
    trio["current_6_ticket"] = metric_row(n * 600, current_trio_payout, current_trio_hits, n)
    trio["formation_5_ticket_no_◎△△"] = metric_row(n * 500, formation5_payout, formation5_hits, n)
    trio["◎△△_increment"] = {
        "incremental_investment_jpy": n * 100,
        "incremental_payout_jpy": trio_payout["◎△△"],
        "incremental_hit_races": trio_hits["◎△△"],
        "incremental_return_rate": trio_payout["◎△△"] / (n * 100) if n else None,
        "return_rate_delta_vs_5_ticket": trio["current_6_ticket"]["return_rate"] - trio["formation_5_ticket_no_◎△△"]["return_rate"],
    }

    by_date = {}
    for date, b in sorted(block.items()):
        bn = b["races"]
        q_total = b["q_payout"]["◎-○"] + b["q_payout"]["◎-▲"]
        t_total = sum(b["trio_payout"][x] for x in trio_labels)
        t5 = t_total - b["trio_payout"]["◎△△"]
        by_date[date] = {
            "race_count": bn,
            "quinella": {
                "◎-○": metric_row(bn*100, b["q_payout"]["◎-○"], b["q_hits"]["◎-○"], bn),
                "◎-▲": metric_row(bn*100, b["q_payout"]["◎-▲"], b["q_hits"]["◎-▲"], bn),
                "current_2_ticket": {"investment_jpy": bn*200, "payout_jpy": q_total, "return_rate": q_total/(bn*200)},
            },
            "trio": {
                **{label: metric_row(bn*100*trio_ticket_counts[label], b["trio_payout"][label], b["trio_hits"][label], bn) for label in trio_labels},
                "current_6_ticket": {"investment_jpy": bn*600, "payout_jpy": t_total, "return_rate": t_total/(bn*600)},
                "formation_5_ticket_no_◎△△": {"investment_jpy": bn*500, "payout_jpy": t5, "return_rate": t5/(bn*500)},
            },
        }

    top_q_ana = sorted(
        [r for r in race_rows if r["quinella_role_payout_jpy"]["◎-▲"] > 0],
        key=lambda r: r["quinella_role_payout_jpy"]["◎-▲"], reverse=True,
    )[:10]
    top_trio_dd = sorted(
        [r for r in race_rows if r["trio_role_payout_jpy"]["◎△△"] > 0],
        key=lambda r: r["trio_role_payout_jpy"]["◎△△"], reverse=True,
    )[:10]

    return {
        "status": "BETTING_LAYER_AUDIT_ONLY_NO_PREDICTION_CHANGE",
        "race_count": n,
        "quinella_role_decomposition": quinella,
        "trio_role_decomposition": trio,
        "by_date": by_date,
        "top_◎-▲_payout_races": top_q_ana,
        "top_◎△△_payout_races": top_trio_dd,
        "races": race_rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prediction", action="append", type=Path, required=True)
    ap.add_argument("--hjc", action="append", required=True, help="DATE=HJC_ZIP")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    predictions = load_predictions(args.prediction)
    hjc_by_date = load_hjc_map(args.hjc)
    result = audit(predictions, hjc_by_date)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
