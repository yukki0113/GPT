#!/usr/bin/env python3
"""Read-only historical KYI declaration coverage. Research only; no CURRENT writes.

Inputs are an explicitly pinned list of PACI archives and an immutable research
generation.  No assumptions about actual starters or historic publication times.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "horse-racing/jrdb/src"))
from jrdb_raw import Parser, canonical_members, split_fixed_records
from brdb_research_history_reader_v03 import ResearchHistoryReader

VERSION = "historical-race-year-coverage-v0.1"
FIELDS = ("sire_name", "dam_name", "broodmare_sire_name",
          "sire_line_code", "broodmare_sire_line_code")
AVAILABLE = {"AVAILABLE_ANNUAL_SNAPSHOT", "AVAILABLE_LATEST_DAILY",
             "AVAILABLE_HISTORICAL_DAILY"}


def valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{8}", value):
        return False
    try:
        datetime.strptime(value, "%Y%m%d")
        return True
    except ValueError:
        return False


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_archive(path, item):
    if not path.is_file() or path.stat().st_size != item["size_bytes"] or sha256(path) != item["sha256"]:
        raise ValueError("archive size/SHA mismatch: " + str(path))


def parse_paci(directory, inventory, start_year=2016, end_year=2025):
    """Parse exact, SHA-pinned KYI/BAC input, preserving duplicate evidence."""
    if not 2016 <= start_year <= end_year <= 2025:
        raise ValueError("historical year window must be within 2016..2025")
    if not inventory:
        raise ValueError("empty PACI inventory")
    parser = Parser()
    entries = {}
    provenance = Counter()
    seen_names = set()
    for item in sorted(inventory, key=lambda v: v["name"]):
        name = item["name"]
        match = re.fullmatch(r"PACI(\d{6})\.zip", name)
        if not match or name in seen_names:
            raise ValueError("invalid or duplicate archive name")
        seen_names.add(name)
        date = "20" + match.group(1)
        if not valid_date(date) or not start_year <= int(date[:4]) <= end_year:
            raise ValueError("archive outside year window")
        path = Path(directory) / name
        verify_archive(path, item)
        with zipfile.ZipFile(path) as z:
            if z.testzip():
                raise ValueError("ZIP corruption: " + name)
            races = {}
            bac_members = canonical_members(z, "BAC")
            kyi_members = canonical_members(z, "KYI")
            if not bac_members or not kyi_members:
                raise ValueError("missing BAC or KYI: " + name)
            for member in bac_members:
                raw_data = z.read(member)
                rows = split_fixed_records(raw_data, "BAC")
                if not rows:
                    raise ValueError("invalid BAC: " + member)
                for raw in rows:
                    race = parser.bac(raw)
                    key = race["race_key_raw"]
                    if key in races and races[key] != race:
                        raise ValueError("conflicting BAC duplicate")
                    races[key] = race
            for member in kyi_members:
                rows = split_fixed_records(z.read(member), "KYI")
                if not rows:
                    raise ValueError("invalid KYI: " + member)
                for i, raw in enumerate(rows, 1):
                    r = parser.kyi(raw)
                    key, hid, number = r["race_key_raw"], r["blood_registration_no"], r["horse_no"]
                    if not re.fullmatch(r"\d{8}", hid) or not isinstance(number, int) or not 1 <= number <= 18:
                        raise ValueError("invalid KYI horse identity")
                    race = races.get(key)
                    if race is None or race["date_raw"] != date or key[2:4] != date[2:4]:
                        raise ValueError("KYI/BAC race mismatch")
                    identity = (date, key, number)
                    row = {"race_date": date, "race_key": key, "horse_no": number, "horse_id": hid}
                    provenance["raw_declarations"] += 1
                    if identity in entries:
                        if entries[identity] != row:
                            raise ValueError("conflicting KYI duplicate")
                        provenance["exact_duplicates"] += 1
                    else:
                        entries[identity] = row
    return [entries[k] for k in sorted(entries)], dict(provenance)


def classify_temporal(result, race_date):
    """A selected snapshot after the race must never be backdated."""
    profile = result.get("profile")
    if profile is None:
        return "AS_OF_UNVERIFIED"
    observed = result.get("observed_date")
    profile_date = result.get("profile_data_date")
    if not valid_date(observed) or not valid_date(profile_date):
        return "AS_OF_UNVERIFIED"
    if observed > race_date or profile_date > race_date:
        return "AS_OF_UNVERIFIED"
    if result["status"] not in AVAILABLE:
        return "AS_OF_UNVERIFIED"
    return "AS_OF_VERIFIED_DATE_ONLY"


def evaluate(entries, reader):
    annual = {}
    cache = {}
    for row in entries:
        date, hid = row["race_date"], row["horse_id"]
        year = date[:4]
        group = annual.setdefault(year, {"entries": 0, "horse_ids": set(), "races": set(),
                "static_join": 0, "temporal_verified": 0, "profile_fields": Counter(),
                "statuses": Counter()})
        group["entries"] += 1
        group["horse_ids"].add(hid)
        group["races"].add((date, row["race_key"]))
        # Latest generation metadata is checked only for static ID membership.
        static = hid in reader.facts
        group["static_join"] += int(static)
        key = hid, date
        if key not in cache:
            cache[key] = reader.horse_profile(hid, as_of=date)
        result = cache[key]
        temporal = classify_temporal(result, date)
        group["statuses"][result["status"]] += 1
        group["statuses"][temporal] += 1
        if temporal == "AS_OF_VERIFIED_DATE_ONLY":
            group["temporal_verified"] += 1
            for field in FIELDS:
                group["profile_fields"][field] += int(bool(result["profile"].get(field)))
    output = []
    for year, g in sorted(annual.items()):
        output.append({"year": int(year), "kyi_declarations": g["entries"],
            "distinct_horses": len(g["horse_ids"]), "races": len(g["races"]),
            "static_join_entries": g["static_join"],
            "as_of_verified_date_only_entries": g["temporal_verified"],
            "as_of_unverified_entries": g["entries"] - g["temporal_verified"],
            **{field + "_asof_present": g["profile_fields"][field] for field in FIELDS},
            "source_status_counts": dict(sorted(g["statuses"].items()))})
    return output


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--paci-dir", type=Path, required=True)
    p.add_argument("--inventory", type=Path, required=True, help="JSON list of {name,size_bytes,sha256}")
    p.add_argument("--generation", type=Path, required=True)
    p.add_argument("--generation-id", required=True)
    p.add_argument("--manifest-sha256", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--start-year", type=int, default=2016)
    p.add_argument("--end-year", type=int, default=2025)
    args = p.parse_args(argv)
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    entries, input_counts = parse_paci(args.paci_dir, inventory, args.start_year, args.end_year)
    reader = ResearchHistoryReader(args.generation, expected_generation_id=args.generation_id,
                                   expected_manifest_sha256=args.manifest_sha256)
    annual = evaluate(entries, reader)
    covered = {v["year"] for v in annual}
    result = {"version": VERSION, "research_only": True, "generation_id": reader.generation_id,
        "source_inventory_sha256": sha256(args.inventory), "input_counts": input_counts,
        "coverage": annual,
        "unobserved_years": sorted(set(range(args.start_year, args.end_year + 1)) - covered),
        "actual_starts": None,
        "note": "KYI declarations, not confirmed starters; intraday publication time unknown. "
                "Static match is not an as-of fact; annual selected profiles are not full history."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
