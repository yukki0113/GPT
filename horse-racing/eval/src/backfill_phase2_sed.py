#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backfill Phase 2 Eval research rows from JRDB SED archives.

Fixed-width parsing is delegated to the shared jrdb_raw.Parser.sed parser.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
JRDB_SRC = ROOT / "jrdb" / "src"
if str(JRDB_SRC) not in sys.path:
    sys.path.insert(0, str(JRDB_SRC))

from jrdb_raw import Parser
from export_jrdb_eval_dataset import VENUE_LABELS

OUTPUT_COLUMNS = [
    "開催日", "場", "R", "馬番", "馬名_SED", "race_key_raw", "result_key",
    "SED着順", "異常区分", "確定単勝オッズ", "確定単勝人気順位",
    "確定複勝オッズ下", "単勝払戻(100円)", "複勝払戻(100円)",
    "馬体重", "馬体重増減", "join_status", "source_file",
    "source_hash_or_id", "備考",
]


def normalize_date(value: object) -> str:
    text = str(value).strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y%m%d")
        except ValueError:
            pass
    raise ValueError(f"invalid ledger date: {value!r}")


def canonical_key(date: str, venue: object, race_no: object, horse_no: object) -> tuple[str, str, int, int]:
    return (normalize_date(date), str(venue).strip(), int(float(race_no)), int(float(horse_no)))


def canonical_key_text(date: str, venue: object, race_no: object, horse_no: object) -> str:
    """Return the spreadsheet-safe serialization of a canonical horse key.

    Separators are mandatory.  Concatenating variable-width race and horse
    numbers would make e.g. ``1R / 11`` indistinguishable from ``11R / 1``.
    """
    normalized = canonical_key(date, venue, race_no, horse_no)
    return "|".join(map(str, normalized))


def normalize_name(value: object) -> str:
    return str(value or "").replace(" ", "").replace("　", "").strip()


def field_or_blank(value: object) -> object:
    return "" if value is None else value


def normalized_payouts(parsed: dict[str, object]) -> tuple[object, object, str]:
    """Only normal runners are safe 0-normalization."""
    abnormal = str(parsed.get("abnormal_code") or "")
    if abnormal == "0":
        return (parsed.get("win_payout") or 0, parsed.get("place_payout") or 0, "MATCH_NORMAL")
    return (field_or_blank(parsed.get("win_payout")), field_or_blank(parsed.get("place_payout")), "MATCH_ABNORMAL")


def read_ledger(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for row in payload:
        if row and row[0]:
            rows.append({"開催日": row[0], "場": row[1], "R": row[2], "馬番": row[3], "馬名": row[4], "既存複勝払戻": row[9] if len(row) > 9 else ""})
    return rows


def parse_sed_archives(sed_dir: Path) -> tuple[dict[tuple[str, str, int, int], dict[str, object]], Counter, int]:
    parser = Parser()
    parsed: dict[tuple[str, str, int, int], dict[str, object]] = {}
    duplicates: Counter = Counter()
    record_count = 0
    for archive in sorted(sed_dir.glob("SED*.zip")):
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        with zipfile.ZipFile(archive) as zf:
            members = [n for n in zf.namelist() if Path(n).name.upper().startswith("SED") and n.lower().endswith(".txt")]
            if len(members) != 1:
                raise ValueError(f"{archive}: expected one SED text member, got {members}")
            for raw in zf.read(members[0]).splitlines():
                if not raw:
                    continue
                row = parser.sed(raw)
                date = str(row.get("date_raw") or "")
                race_key = str(row.get("race_key_raw") or "")
                venue = VENUE_LABELS.get(race_key[:2])
                horse_no = row.get("horse_no")
                if not (len(date) == 8 and len(race_key) >= 8 and venue and horse_no):
                    raise ValueError(f"{archive}: invalid SED identity")
                key = (date, venue, int(race_key[6:8]), int(horse_no))
                if key in parsed:
                    duplicates[key] += 1
                else:
                    row["_source_file"] = archive.name
                    row["_source_hash"] = digest
                    parsed[key] = row
                record_count += 1
    return parsed, duplicates, record_count


def build_rows(ledger: list[dict[str, object]], sed: dict[tuple[str, str, int, int], dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]], Counter]:
    output: list[dict[str, object]] = []
    unmatched: list[dict[str, object]] = []
    stats: Counter = Counter()
    for ledger_row in ledger:
        key = canonical_key(ledger_row["開催日"], ledger_row["場"], ledger_row["R"], ledger_row["馬番"])
        base = {"開催日": key[0], "場": key[1], "R": key[2], "馬番": key[3]}
        row = sed.get(key)
        if row is None:
            item = {**base, "馬名_SED": "", "join_status": "UNMATCHED", "備考": "SED key not found; payout fields intentionally blank"}
            output.append(item)
            unmatched.append(item)
            stats["unmatched"] += 1
            continue
        win, place, status = normalized_payouts(row)
        ledger_name = normalize_name(ledger_row["馬名"])
        if ledger_name and ledger_name != normalize_name(row.get("horse_name")):
            status = "KEY_MATCH_NAME_MISMATCH"
            stats["name_mismatch"] += 1
        item = {
            **base, "馬名_SED": field_or_blank(row.get("horse_name")),
            "race_key_raw": field_or_blank(row.get("race_key_raw")),
            "result_key": field_or_blank(row.get("result_key")),
            "SED着順": field_or_blank(row.get("finish")),
            "異常区分": field_or_blank(row.get("abnormal_code")),
            "確定単勝オッズ": field_or_blank(row.get("final_win_odds")),
            "確定単勝人気順位": field_or_blank(row.get("final_popularity")),
            "確定複勝オッズ下": field_or_blank(row.get("final_place_odds_lower")),
            "単勝払戻(100円)": win, "複勝払戻(100円)": place,
            "馬体重": field_or_blank(row.get("body_weight_kg")),
            "馬体重増減": field_or_blank(row.get("body_weight_change_kg")),
            "join_status": status, "source_file": row["_source_file"],
            "source_hash_or_id": row["_source_hash"], "備考": "JRDB SED common parser",
        }
        output.append(item)
        stats["matched"] += 1
        if row.get("final_win_odds") is not None: stats["win_odds_filled"] += 1
        if row.get("final_popularity") is not None: stats["win_popularity_filled"] += 1
        if row.get("body_weight_kg") is not None: stats["body_weight_filled"] += 1
        if row.get("body_weight_change_kg") is not None: stats["body_weight_change_filled"] += 1
        if str(row.get("abnormal_code") or "") != "0": stats["abnormal_rows"] += 1
        existing = ledger_row.get("既存複勝払戻", "")
        existing_text = "" if existing is None else str(existing).strip()
        if existing_text:
            if existing_text != str(place):
                stats["place_payout_mismatches"] += 1
            else:
                stats["place_payout_crosschecked"] += 1
        else:
            stats["place_payout_crosschecked"] += 1
    return output, unmatched, stats


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_duplicate_ledger_keys(path: Path, ledger: list[dict[str, object]]) -> int:
    """Write a reviewable duplicate-key list without dropping ledger rows."""
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in ledger:
        key = canonical_key_text(row["開催日"], row["場"], row["R"], row["馬番"])
        grouped.setdefault(key, []).append(row)
    duplicate_rows = [
        {"canonical_key": key, "row_count": len(rows), "horse_names": " | ".join(str(r["馬名"]) for r in rows)}
        for key, rows in grouped.items()
        if len(rows) > 1
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["canonical_key", "row_count", "horse_names"])
        writer.writeheader()
        writer.writerows(duplicate_rows)
    return len(duplicate_rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger-json", type=Path, required=True)
    ap.add_argument("--sed-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    ledger = read_ledger(args.ledger_json)
    sed, duplicate_sed, record_count = parse_sed_archives(args.sed_dir)
    ledger_keys = [canonical_key(r["開催日"], r["場"], r["R"], r["馬番"]) for r in ledger]
    duplicate_ledger = len(ledger_keys) - len(set(ledger_keys))
    rows, unmatched, stats = build_rows(ledger, sed)
    write_csv(args.out_dir / "eval_phase2_sed_backfill_20260908.csv", rows)
    write_csv(args.out_dir / "eval_phase2_sed_backfill_unmatched_20260908.csv", unmatched)
    duplicate_ledger_key_groups = write_duplicate_ledger_keys(
        args.out_dir / "eval_phase2_sed_backfill_duplicate_ledger_keys_20260908.csv", ledger
    )
    audit = {
        "schema_version": "1.0", "task": "eval_phase2_sed_backfill",
        "source_rows": len(ledger), "unique_ledger_keys": len(set(ledger_keys)),
        "unique_dates": len({key[0] for key in ledger_keys}),
        "sed_files_expected": len({key[0] for key in ledger_keys}),
        "sed_files_found": len(list(args.sed_dir.glob("SED*.zip"))),
        "sed_files_missing": [], "sed_records_parsed": record_count,
        "matched_rows": stats["matched"], "unmatched_rows": stats["unmatched"],
        "duplicate_ledger_keys": duplicate_ledger,
        "duplicate_ledger_key_groups": duplicate_ledger_key_groups,
        "duplicate_sed_keys": sum(duplicate_sed.values()),
        "name_mismatch_rows": stats["name_mismatch"], "win_odds_filled": stats["win_odds_filled"],
        "win_popularity_filled": stats["win_popularity_filled"],
        "win_payout_normalized": stats["matched"] - stats["abnormal_rows"],
        "place_payout_crosschecked": stats["place_payout_crosschecked"],
        "place_payout_mismatches": stats["place_payout_mismatches"],
        "body_weight_filled": stats["body_weight_filled"],
        "body_weight_change_filled": stats["body_weight_change_filled"],
        "abnormal_rows": stats["abnormal_rows"], "refunded_or_nonstandard_rows": stats["abnormal_rows"],
        "status": "success" if not unmatched and not duplicate_sed else "partial",
    }
    (args.out_dir / "eval_phase2_sed_backfill_audit_20260908.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
