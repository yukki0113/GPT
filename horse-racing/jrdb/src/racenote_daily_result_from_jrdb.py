#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build RaceNote canonical daily-result JSON from JRDB SED + HJC.

Use this path after the race day when the target-date JRDB result assets are
already available.  SED owns finishers; HJC owns all eight payout types.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Mapping

from jrdb_result_query import BET_TYPES, ResultQueryError, query_results

VERSION = "racenote-daily-result-jrdb-0.1.0"
SCHEMA_VERSION = "0.1"


def _canonical_payout(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "combination": [int(v) for v in entry.get("numbers") or []],
        "payout_jpy": int(entry["payout_yen"]),
    }


def convert_jrdb_query_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    races: list[dict[str, Any]] = []
    review_required: list[dict[str, Any]] = []

    for race in payload.get("races") or []:
        warnings: list[str] = []
        cross = race.get("cross_validation") or {}
        if cross.get("review_required"):
            warnings.append("SED/HJC win/place cross-validation mismatch")
        if race.get("result_status") != "available":
            warnings.append("SED result unavailable")
        if race.get("payouts_status") != "available":
            warnings.append("HJC payouts unavailable")

        top3 = [
            {
                "finish": row.get("finish"),
                "horse_no": row.get("horse_no"),
                "horse_name": row.get("horse_name") or "",
            }
            for row in race.get("top3") or []
        ]
        payouts = {
            bet_type: [_canonical_payout(x) for x in (race.get("payouts") or {}).get(bet_type, [])]
            for bet_type in BET_TYPES
        }

        status = "official" if not warnings else "review_required"
        item = {
            "date": race.get("race_date"),
            "venue": race.get("venue_name"),
            "race_no": race.get("race_no"),
            "status": status,
            "top3": top3,
            "payouts": payouts,
            "warnings": warnings,
            "source": {
                "provider": "JRDB",
                "result": "SED",
                "payout": "HJC",
            },
        }
        races.append(item)
        if warnings:
            review_required.append(
                {
                    "venue": item["venue"],
                    "race_no": item["race_no"],
                    "warnings": warnings,
                }
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "generator_version": VERSION,
        "target_date": (payload.get("query") or {}).get("date"),
        "status": "complete"
        if races and not review_required and payload.get("status") == "success"
        else "review_required",
        "source": {
            "provider": "JRDB",
            "result": "SED",
            "payout": "HJC",
            "web_used": False,
            "provenance": payload.get("provenance") or {},
        },
        "race_count": len(races),
        "review_required_count": len(review_required),
        "review_required": review_required,
        "races": races,
    }


def build_daily_result(
    *,
    target_date: str | dt.date,
    sed: Path,
    hjc: Path,
) -> dict[str, Any]:
    queried = query_results(
        date=target_date,
        source="raw",
        sed=sed,
        hjc=hjc,
    )
    return convert_jrdb_query_payload(queried)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Build RaceNote canonical result JSON from JRDB SED/HJC"
    )
    ap.add_argument("--date", required=True)
    ap.add_argument("--sed", required=True, type=Path)
    ap.add_argument("--hjc", required=True, type=Path)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args()

    output = args.output or (
        Path(__file__).resolve().parents[1]
        / "result_cache"
        / f"{args.date.replace('-', '')}_SameDay_Result.json"
    )
    try:
        result = build_daily_result(
            target_date=args.date,
            sed=args.sed,
            hjc=args.hjc,
        )
    except (ResultQueryError, FileNotFoundError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None) + "\n",
        encoding="utf-8",
    )
    print(str(output))
    return 0 if result["status"] == "complete" else 4


if __name__ == "__main__":
    raise SystemExit(main())
