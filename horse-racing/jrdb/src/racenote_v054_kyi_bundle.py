#!/usr/bin/env python3
"""Build a neutral v0.5.4 supplemental KYI bundle from canonical target-day KYI.

The canonical RRDB v0.5 recommendation is obtained from the *prepared*
RaceNote Reader, not recalculated here. The bundle contains only allowlisted
pre-race KYI fields and prior-result keys; no market/race result payload.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

from jrdb_raw import Parser, canonical_members, race_key_parts, read_fixed_records
from racenote_save_venue_batch_v046 import load_clean

KYI_ALLOWLIST = (
    "reference_previous_raw",
    "reference_jockey_code",
    "ticket_index",
    "ticket_mark",
    "longshot_type",
    "longshot_index",
    "previous",
)
BUNDLE_VERSION = "racenote-v054-kyi-supplemental-0.1"


def _records_for_date(archive: Path, target_date: str):
    yymmdd = target_date[2:4] + target_date[5:7] + target_date[8:10]
    parser = Parser()
    with zipfile.ZipFile(archive) as zf:
        for member in canonical_members(zf, "KYI"):
            if Path(member).name.upper() != f"KYI{yymmdd}.TXT":
                continue
            for record in read_fixed_records(zf, member, "KYI"):
                yield parser.kyi(record), archive.name, member


def build_bundle(prep_root: Path, archives: list[Path]) -> dict[str, Any]:
    handoff, _, readers = load_clean(
        prep_root,
        expected_rrdb_contract="rrdb-recommendation-signals-v0.5",
    )
    if handoff.get("market_blind") is not True:
        raise ValueError("forecast_prep must be market-blind")
    if handoff.get("result_opened") is not False or handoff.get("target_market_opened") is not False:
        raise ValueError("target result or market already opened")
    target_date = handoff["target_date"]
    allowed: dict[tuple[int, str, int], tuple[str, int]] = {}
    for (venue, race_no), row in readers.items():
        for h in row["reader"]["horses"]:
            no = int(h["basic"]["horse_no"])
            horse_id = str(h["basic"]["horse_id"])
            key = (int(race_no), horse_id, no)
            if key in allowed:
                raise ValueError(f"ambiguous target horse join: {key}")
            allowed[key] = (venue, int(race_no))
    found = {}
    for archive in archives:
        for parsed, archive_name, member in _records_for_date(archive, target_date):
            horse_id = str(parsed["blood_registration_no"])
            no = parsed.get("horse_no")
            race_no = race_key_parts(parsed["race_key_raw"])["race_no"]
            key = (race_no, horse_id, no)
            if key not in allowed:
                continue
            if key in found:
                raise ValueError(f"duplicate KYI target identity: {key}")
            found[key] = {
                "horse_no": int(no),
                "kyi": {k: parsed[k] for k in KYI_ALLOWLIST},
                "source_race_keys": [
                    previous["race_key_raw"]
                    for previous in parsed["previous"]
                    if previous.get("race_key_raw")
                ],
                "provenance": {
                    "source_kind": "JRDB_KYI",
                    "target_race_key": parsed["race_key_raw"],
                    "archive": archive_name,
                    "member": member,
                },
            }
    by_race = {}
    for key, data in found.items():
        by_race.setdefault(allowed[key], []).append(data)
    races = [
        {
            "venue": venue,
            "race_no": race_no,
            "horses": sorted(by_race.get((venue, race_no), []), key=lambda h: h["horse_no"]),
        }
        for venue, race_no in sorted(readers)
    ]
    return {
        "schema_version": BUNDLE_VERSION,
        "target_date": target_date,
        "source_selection_id": handoff["selection_id"],
        "rrdb_contract": "rrdb-recommendation-signals-v0.5",
        "rrdb_execution": "USE_PREPARED_CANONICAL_RECOMMENDATION",
        "policy": {
            "target_final_odds": False,
            "target_result": False,
            "hidden_value_role": "CORROBORATION_AND_RECHECK_ONLY",
            "additive_score": False,
        },
        "coverage": {
            "reader_horse_count": len(allowed),
            "kyi_matched_count": len(found),
            "kyi_missing_count": len(allowed) - len(found),
        },
        "races": races,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prep-root", type=Path, required=True)
    ap.add_argument("--kyi-archive", type=Path, action="append", required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    bundle = build_bundle(args.prep_root, args.kyi_archive)
    if args.output.exists():
        raise FileExistsError(f"immutable bundle already exists: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "success", "coverage": bundle["coverage"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
