#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract result-side JRDB SED/HJC data for frozen RaceNote Gen0 races.

This tool is deliberately result-side only. It consumes already-downloaded annual
JRDB artifacts, filters them to an explicit race allow-list, and emits a compact
JSON payload suitable for post-freeze evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from jrdb_raw import Parser, read_fixed_records  # noqa: E402


VERSION = "racenote-gen0-result-acquire-0.1.0"
SUPPORTED_WAGERS = ("win", "place", "quinella", "trio")


def require(condition: bool, message: str) -> None:
    """Raise a value error when one result-acquisition invariant is violated."""
    if not condition:
        raise ValueError(message)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for one local file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    """Read UTF-8 JSON from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, value: Any) -> None:
    """Write stable UTF-8 JSON to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def normalize_date(value: str) -> str:
    """Normalize an explicit race date to YYYYMMDD without guessing."""
    normalized = str(value).replace("-", "")
    require(len(normalized) == 8 and normalized.isdigit(), f"invalid date: {value}")
    return normalized


def find_unique(root: Path, name: str) -> Path:
    """Find exactly one artifact member file by basename under a run directory."""
    matches = [path for path in root.rglob(name) if path.is_file()]
    require(
        len(matches) == 1,
        f"expected exactly one {name} under {root}; found {len(matches)}",
    )
    return matches[0]


def find_member(archive: zipfile.ZipFile, expected_name: str) -> str:
    """Find exactly one ZIP member by basename, case-insensitively."""
    matches = [
        name
        for name in archive.namelist()
        if Path(name).name.upper() == expected_name.upper()
    ]
    require(
        len(matches) == 1,
        f"expected exactly one {expected_name} in archive; found {len(matches)}",
    )
    return matches[0]


def positive_payout_slots(parsed_hjc: Mapping[str, Any], wager: str) -> list[dict[str, Any]]:
    """Return only populated positive-payout HJC slots for one wager type."""
    rows: list[dict[str, Any]] = []
    slots = parsed_hjc.get(wager) or []
    for slot in slots:
        if not isinstance(slot, Mapping):
            continue
        numbers = slot.get("numbers") or []
        payout = slot.get("payout")
        if not isinstance(payout, int) or payout <= 0:
            continue
        if not numbers or any(not isinstance(number, int) or number <= 0 for number in numbers):
            continue
        rows.append(
            {
                "numbers": list(numbers),
                "payout_jpy": payout,
            }
        )
    return rows


def parse_sed_race(
    archive_path: Path,
    date: str,
    race_key: str,
    parser: Parser,
) -> list[dict[str, Any]]:
    """Parse all SED horse rows for one explicit race."""
    member_name = f"SED{date[2:]}.txt"
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive_path) as archive:
        member = find_member(archive, member_name)
        for record in read_fixed_records(archive, member, "SED"):
            parsed = parser.sed(record)
            if parsed.get("race_key_raw") != race_key:
                continue
            rows.append(
                {
                    "horse_no": parsed.get("horse_no"),
                    "horse_name": parsed.get("horse_name"),
                    "finish_position": parsed.get("finish"),
                    "abnormality_code": parsed.get("abnormal_code"),
                    "final_win_odds": parsed.get("final_win_odds"),
                    "final_popularity": parsed.get("final_popularity"),
                    "final_place_odds_lower": parsed.get("final_place_odds_lower"),
                    "win_payout": parsed.get("win_payout"),
                    "place_payout": parsed.get("place_payout"),
                    "result_key": parsed.get("result_key"),
                    "record_sha256": hashlib.sha256(record).hexdigest(),
                }
            )

    rows.sort(key=lambda row: int(row["horse_no"] or 0))
    require(rows, f"SED race not found: {date}/{race_key}")
    horse_numbers = [row.get("horse_no") for row in rows]
    require(
        len(horse_numbers) == len(set(horse_numbers)),
        f"duplicate SED horse numbers: {date}/{race_key}",
    )
    return rows


def parse_hjc_race(
    archive_path: Path,
    date: str,
    race_key: str,
    parser: Parser,
) -> dict[str, list[dict[str, Any]]]:
    """Parse supported race-level HJC payouts for one explicit race."""
    member_name = f"HJC{date[2:]}.txt"
    matched: dict[str, list[dict[str, Any]]] | None = None
    with zipfile.ZipFile(archive_path) as archive:
        member = find_member(archive, member_name)
        for record in read_fixed_records(archive, member, "HJC"):
            parsed = parser.hjc(record)
            if parsed.get("race_key_raw") != race_key:
                continue
            require(matched is None, f"duplicate HJC race row: {date}/{race_key}")
            matched = {
                wager: positive_payout_slots(parsed, wager)
                for wager in SUPPORTED_WAGERS
            }

    require(matched is not None, f"HJC race not found: {date}/{race_key}")
    return matched


def validate_request(request: Mapping[str, Any]) -> tuple[str, dict[str, Mapping[str, Any]], list[dict[str, Any]]]:
    """Validate and normalize the explicit artifact/race request."""
    request_id = str(request.get("request_id") or "").strip()
    require(request_id, "request_id is required")

    sources_raw = request.get("sources")
    require(isinstance(sources_raw, Mapping) and sources_raw, "sources must be a non-empty object")
    sources: dict[str, Mapping[str, Any]] = {}
    for raw_year, value in sources_raw.items():
        year = str(raw_year)
        require(len(year) == 4 and year.isdigit(), f"invalid source year: {raw_year}")
        require(isinstance(value, Mapping), f"invalid source entry: {year}")
        sources[year] = value

    races_raw = request.get("races")
    require(isinstance(races_raw, list) and races_raw, "races must be a non-empty list")
    races: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in races_raw:
        require(isinstance(raw, Mapping), "each race must be an object")
        date = normalize_date(str(raw.get("date") or ""))
        race_key = str(raw.get("race_key") or "").strip()
        require(len(race_key) == 8, f"race_key must be 8 chars: {race_key}")
        require(date[:4] in sources, f"missing annual source for race year {date[:4]}")
        unique_key = (date, race_key)
        require(unique_key not in seen, f"duplicate requested race: {date}/{race_key}")
        seen.add(unique_key)
        races.append(
            {
                "date": date,
                "race_key": race_key,
                "venue": raw.get("venue"),
                "race_no": raw.get("race_no"),
                "forecast_id": raw.get("forecast_id"),
            }
        )

    return request_id, sources, races


def build_payload(request: Mapping[str, Any], raw_root: Path) -> dict[str, Any]:
    """Build the compact result payload from downloaded annual artifacts."""
    request_id, sources, races = validate_request(request)
    parser = Parser()

    source_meta: dict[str, dict[str, Any]] = {}
    archive_paths: dict[str, tuple[Path, Path]] = {}
    for year, source in sources.items():
        year_root = raw_root / year
        sed_name = f"SED_{year}.zip"
        hjc_name = f"HJC_{year}.zip"
        sed_path = find_unique(year_root, sed_name)
        hjc_path = find_unique(year_root, hjc_name)
        archive_paths[year] = (sed_path, hjc_path)
        source_meta[year] = {
            "run_id": source.get("run_id"),
            "artifact_name": source.get("artifact_name"),
            "sed_file": sed_name,
            "sed_sha256": sha256_file(sed_path),
            "hjc_file": hjc_name,
            "hjc_sha256": sha256_file(hjc_path),
        }

    result_races: list[dict[str, Any]] = []
    for race in races:
        year = race["date"][:4]
        sed_path, hjc_path = archive_paths[year]
        horses = parse_sed_race(
            sed_path,
            race["date"],
            race["race_key"],
            parser,
        )
        payouts = parse_hjc_race(
            hjc_path,
            race["date"],
            race["race_key"],
            parser,
        )
        winners = [
            row
            for row in horses
            if row.get("finish_position") == 1
            and str(row.get("abnormality_code") or "0") == "0"
        ]
        require(len(winners) == 1, f"expected one normal winner: {race['date']}/{race['race_key']}")
        result_races.append(
            {
                **race,
                "source_year": year,
                "horses": horses,
                "payouts": payouts,
                "winner": {
                    "horse_no": winners[0]["horse_no"],
                    "horse_name": winners[0]["horse_name"],
                },
            }
        )

    return {
        "version": VERSION,
        "request_id": request_id,
        "status": "success",
        "sources": source_meta,
        "races": result_races,
    }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    request = load_json(Path(args.request_json))
    require(isinstance(request, Mapping), "request JSON must be an object")
    payload = build_payload(request, Path(args.raw_root))
    dump_json(Path(args.output_json), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
