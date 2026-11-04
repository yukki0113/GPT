#!/usr/bin/env python3
"""BRDB M6 P1-4c: research-only private 2026 PACI Drive pre-day inventory.

Input timestamps are metadata captured independently from the native Drive
connector, but the manifest itself is NOT cryptographic proof of those claims.
This audit confirms internal consistency of SHA-pinned bytes and declared
timestamps; never authorizes predictive/as-of promotion.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile, BadZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "jrdb" / "src"))
from jrdb_raw import raw_field, split_fixed_records  # canonical JRDB fixed-width parser
from jrdb_ukc import parse_ukc_record  # canonical UKC parser

VERSION = "brdb-m6-p1-4c-paci-pre-day-v0.1"
DATES = (
    "20260919","20260920","20260926","20260927",
    "20261003","20261004","20261010","20261011","20261012",
    "20261017","20261018","20261024","20261031","20261101",
)
JST = timezone(timedelta(hours=9))

def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()

def parse_provider_time(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("provider timestamp must have explicit UTC Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid provider timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp timezone required")
    return parsed

def body_records(data: bytes, kind: str, body_size: int):
    """Normalize CRLF framing after canonical JRDB split_fixed_records."""
    records = split_fixed_records(data, kind)
    if not records:
        raise ValueError("invalid fixed record framing")
    result = []
    for row in records:
        if len(row) == body_size + 2 and row.endswith(b"\\r\\n"):
            row = row[:-2]
        if len(row) != body_size:
            raise ValueError("invalid fixed record body length")
        result.append(row)
    return result

def audit(root: Path, manifest: dict) -> dict:
    root = Path(root).resolve()
    archives = manifest.get("archives")
    if not isinstance(archives, list) or tuple(item.get("date") for item in archives) != DATES:
        raise ValueError("expected fixed 14 ordered daily PACI source dates")
    result_days = []
    for item in archives:
        day = item["date"]
        local_midnight = datetime.strptime(day, "%Y%m%d").replace(tzinfo=JST)
        created = parse_provider_time(item.get("created_time"))
        modified = parse_provider_time(item.get("modified_time"))
        if created >= local_midnight or modified >= local_midnight or modified < created:
            raise ValueError("archive created/modified on or after target calendar date")
        if item.get("revision_count") != 1:
            raise ValueError("ambiguous Drive revision history")
        filename = "PACI" + day[2:] + ".zip"
        archive_path = (root / filename).resolve()
        if not archive_path.is_relative_to(root) or not archive_path.is_file():
            raise ValueError("archive missing")
        if archive_path.stat().st_size != item.get("zip_size"):
            raise ValueError("ZIP size mismatch")
        expected = item.get("zip_sha256")
        if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise ValueError("invalid pinned SHA")
        if sha_file(archive_path) != expected:
            raise ValueError("ZIP SHA mismatch")
        try:
            with ZipFile(archive_path) as z:
                names = z.namelist()
                if len(names) != len(set(names)) or len(names) != 14:
                    raise ValueError("unexpected ZIP member collection")
                ky_name = "KYI" + day[2:] + ".txt"
                uk_name = "UKC" + day[2:] + ".txt"
                if ky_name not in names or uk_name not in names:
                    raise ValueError("missing date-matched UKC/KYI member")
                if z.testzip() is not None:
                    raise ValueError("ZIP CRC mismatch")
                uk_bytes = z.read(uk_name)
                ky_bytes = z.read(ky_name)
        except BadZipFile as exc:
            raise ValueError("invalid ZIP") from exc
        if sha_bytes(uk_bytes) != item.get("ukc_sha256") or sha_bytes(ky_bytes) != item.get("kyi_sha256"):
            raise ValueError("member SHA mismatch")
        uk_records = body_records(uk_bytes, "UKC", 290)
        ky_records = body_records(ky_bytes, "KYI", 1022)
        if not uk_records or len(uk_records) != len(ky_records):
            raise ValueError("UKC/KYI record count mismatch")
        ids = [parse_ukc_record(record) for record in uk_records]
        ky_ids = [raw_field(record, 11, 8) for record in ky_records]
        if len({record.horse_id for record in ids}) != len(ids) or len(set(ky_ids)) != len(ky_ids):
            raise ValueError("duplicate canonical horse_id within day")
        if any(not re.fullmatch(r"[0-9]{8}", record.horse_id) or
               record.data_date != day for record in ids):
            raise ValueError("UKC canonical ID or target profile data_date invalid")
        if [record.horse_id for record in ids] != ky_ids:
            raise ValueError("UKC/KYI horse_id or ordering mismatch")
        result_days.append({
            "date": day, "ukc_rows": len(ids), "kyi_rows": len(ky_ids),
            "ids_matched": len(ids), "crc": "PASS", "drive_revision_count": 1,
            "provider_metadata_before_target_day_claim": True,
        })
    total = sum(row["ukc_rows"] for row in result_days)
    return {
        "version": VERSION,
        "status": "PASS_FIXED_PRIVATE_ARCHIVE_AND_DECLARED_PROVIDER_METADATA_AUDIT_ONLY",
        "day_count": len(result_days),
        "paci_declarations": total,
        "ukc_kyi_id_matches": total,
        "ukc_kyi_id_mismatches": 0,
        "future_profile_data_dates": 0,
        "prediction_safe": False,
        "pre_race_release_time_proven": False,
        "input_provider_metadata_cryptographically_attested_by_this_script": False,
        "historical_2016_to_2025_asof_certified_entries": 0,
        "source_class": "2026_DRIVE_CREATED_AND_MODIFIED_BEFORE_TARGET_LOCAL_CALENDAR_DAY",
        "decision": "RESEARCH_EVIDENCE_FOUND_NO_PREDICTION_PROMOTION",
        "days": result_days,
        "limitations": [
            "Provider metadata was independently read through connected Drive; a caller-provided JSON timestamp alone is not independent proof.",
            "Present ZIP and member SHA hashes were computed at research audit time, not contemporaneously before each race.",
            "The Drive storage history is not independently attested JRDB provider distribution time.",
            "KYI declarations are not confirmed starters; 2026 cohort is not an independent multi-year holdout.",
            "The 2026 daily evidence cannot prove 2016-2025 annual selected pedigree as-of availability.",
        ],
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--private-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.private_manifest.read_text(encoding="utf-8"))
    result = audit(args.archive_root, source)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "paci_pre_day_audit.json").write_text(
        json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"status": result["status"], "days": result["day_count"],
                      "entries": result["paci_declarations"]}))

if __name__ == "__main__":
    main()
