#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build sparse RaceReviewDB recommendation handoff for Newspaper/PWA.

Input is the audited output of jrdb_recommendation_reverse.py.
Only matched target horses are written. Internal signal IDs and strength values
are deliberately not exported to the Newspaper/PWA contract; RRDB owns their
translation into reader-facing short prose.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

COLUMNS = (
    "date",
    "venue_code",
    "race_no",
    "race_key",
    "horse_no",
    "horse_name",
    "recommendation_comment",
    "recommendation_version",
)


class HandoffError(RuntimeError):
    pass


def build_handoff(reverse_json: Path, output_csv: Path) -> dict[str, object]:
    payload = json.loads(reverse_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("status") != "PASS":
        raise HandoffError("RRDB reverse result must be a PASS object")

    target_date = str(payload.get("race_date") or "").strip()
    version = str(payload.get("recommendation_contract_version") or "").strip()
    recommendations = payload.get("recommendations")
    if not target_date or not version or not isinstance(recommendations, list):
        raise HandoffError("RRDB reverse result is missing provenance")

    rows: list[dict[str, object]] = []
    seen: set[tuple[str, int, int]] = set()
    for item in recommendations:
        if not isinstance(item, dict):
            raise HandoffError("recommendation row must be an object")
        venue_code = str(item.get("venue_code") or "").strip().zfill(2)
        race_no = int(item.get("race_no") or 0)
        horse_no = int(item.get("horse_no") or 0)
        race_key = str(item.get("target_race_key") or "").strip()
        horse_name = str(item.get("horse_name_paci") or "").strip()
        comment = str(item.get("newspaper_comment") or "").strip()
        if not (
            len(venue_code) == 2
            and 1 <= race_no <= 12
            and horse_no >= 1
            and race_key
            and horse_name
            and comment
        ):
            raise HandoffError(f"invalid recommendation handoff row: {item!r}")
        key = (venue_code, race_no, horse_no)
        if key in seen:
            raise HandoffError(f"duplicate recommendation handoff key: {key}")
        seen.add(key)
        rows.append({
            "date": target_date,
            "venue_code": venue_code,
            "race_no": race_no,
            "race_key": race_key,
            "horse_no": horse_no,
            "horse_name": horse_name,
            "recommendation_comment": comment,
            "recommendation_version": version,
        })

    rows.sort(key=lambda r: (str(r["venue_code"]), int(r["race_no"]), int(r["horse_no"])))
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    return {
        "status": "PASS",
        "date": target_date,
        "recommendation_version": version,
        "targeted_horses": len(rows),
        "output": str(output_csv),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reverse-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(
        build_handoff(args.reverse_json, args.output_csv),
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
