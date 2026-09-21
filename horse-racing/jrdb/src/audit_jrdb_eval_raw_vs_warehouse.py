#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Full historical Raw-vs-Warehouse equivalence audit for Eval consumers.

The audit is non-mutating.  It binds frozen annual BAC/SED Raw rows to the
accepted Warehouse by source member + one-based record ordinal, verifies the
original record SHA, reconstructs the common-parser logical row from Warehouse,
and compares every logical value.  Eval-specific projections are then hashed
through the same helpers used by the Raw path.

Any mismatch is a hard FAIL and must block historical input cutover.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

from jrdb_eval_horse_result_adapter import project_eval_horse_result_from_parsed
from jrdb_eval_raw_adapter import (
    project_bac_eval_parsed,
    project_sed_race_eval_parsed,
)
from jrdb_eval_warehouse_adapter import EvalWarehouseError, WarehouseEvalReader
from jrdb_racenote_warehouse_adapter import unflatten_parser_row
from jrdb_raw import Parser


MEMBER_RE = {
    "BAC": re.compile(r"^BAC(\d{6})\.txt$", re.IGNORECASE),
    "SED": re.compile(r"^SED(\d{6})\.txt$", re.IGNORECASE),
}

VENUE_LABELS = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}
ABNORMALITY_LABELS = {
    "0": "異常なし", "1": "取消", "2": "除外", "3": "中止",
    "4": "失格", "5": "降着", "6": "再騎乗",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stream_hash(rows: list[tuple[tuple[str, int], object]]) -> str:
    digest = hashlib.sha256()
    for key, value in sorted(rows):
        digest.update(key[0].encode("utf-8"))
        digest.update(b"|")
        digest.update(str(key[1]).encode("ascii"))
        digest.update(b"|")
        digest.update(canonical_json(value).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def member_key(name: object, ordinal: object) -> tuple[str, int]:
    return Path(str(name or "")).name.upper(), int(ordinal or 0)


def member_date_from_name(family: str, member: str) -> str | None:
    match = MEMBER_RE[family].fullmatch(Path(member).name)
    if not match:
        return None
    token = match.group(1)
    return "20" + token


def read_raw_year(
    family: str,
    path: Path,
) -> dict[tuple[str, int], dict[str, object]]:
    parser = Parser()
    method = getattr(parser, family.lower())
    rows: dict[tuple[str, int], dict[str, object]] = {}
    with zipfile.ZipFile(path) as archive:
        members = sorted(
            member for member in archive.namelist()
            if MEMBER_RE[family].fullmatch(Path(member).name)
        )
        if not members:
            raise RuntimeError(f"{path}: no {family} daily members")
        for member in members:
            ordinal = 0
            for raw in archive.read(member).splitlines():
                if not raw:
                    continue
                ordinal += 1
                key = member_key(member, ordinal)
                if key in rows:
                    raise RuntimeError(f"duplicate Raw source identity: {key}")
                rows[key] = {
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "parsed": method(raw),
                    "member_date": member_date_from_name(family, member),
                }
    return rows


def read_warehouse_year(
    reader: WarehouseEvalReader,
    family: str,
    year: int,
) -> dict[tuple[str, int], dict[str, object]]:
    relation = family.lower()
    rows: dict[tuple[str, int], dict[str, object]] = {}
    for warehouse_row in reader.relation_rows(relation, year):
        key = member_key(
            warehouse_row.get("source_member"),
            warehouse_row.get("source_record_ordinal"),
        )
        if key in rows:
            raise RuntimeError(f"duplicate Warehouse source identity: {family}/{year}/{key}")
        rows[key] = {
            "sha256": str(warehouse_row.get("source_record_sha256") or ""),
            "parsed": unflatten_parser_row(family, warehouse_row),
            "member_date": str(warehouse_row.get("source_member_date") or ""),
        }
    return rows


def projection(family: str, parsed: dict[str, object]) -> object:
    if family == "BAC":
        return project_bac_eval_parsed(parsed)
    race = project_sed_race_eval_parsed(parsed)
    horse = project_eval_horse_result_from_parsed(parsed, VENUE_LABELS, ABNORMALITY_LABELS)
    phase2 = {
        "race_key_raw": parsed.get("race_key_raw"),
        "result_key": parsed.get("result_key"),
        "horse_name": parsed.get("horse_name"),
        "finish": parsed.get("finish"),
        "abnormal_code": parsed.get("abnormal_code"),
        "final_win_odds": parsed.get("final_win_odds"),
        "final_popularity": parsed.get("final_popularity"),
        "final_place_odds_lower": parsed.get("final_place_odds_lower"),
        "win_payout": parsed.get("win_payout"),
        "place_payout": parsed.get("place_payout"),
        "body_weight_kg": parsed.get("body_weight_kg"),
        "body_weight_change_kg": parsed.get("body_weight_change_kg"),
    }
    return {"race": race, "horse": horse, "phase2_sed": phase2}


def compare_year_family(
    reader: WarehouseEvalReader,
    family: str,
    year: int,
    raw_path: Path,
    mismatch_limit: int,
) -> dict[str, object]:
    raw_rows = read_raw_year(family, raw_path)
    warehouse_rows = read_warehouse_year(reader, family, year)
    raw_keys = set(raw_rows)
    warehouse_keys = set(warehouse_rows)
    missing_in_warehouse = sorted(raw_keys - warehouse_keys)
    extra_in_warehouse = sorted(warehouse_keys - raw_keys)
    mismatches: list[dict[str, object]] = []
    hash_mismatches = 0
    logical_mismatches = 0
    member_date_mismatches = 0

    raw_projection_rows: list[tuple[tuple[str, int], object]] = []
    warehouse_projection_rows: list[tuple[tuple[str, int], object]] = []
    raw_logical_rows: list[tuple[tuple[str, int], object]] = []
    warehouse_logical_rows: list[tuple[tuple[str, int], object]] = []

    for key in sorted(raw_keys & warehouse_keys):
        raw = raw_rows[key]
        warehouse = warehouse_rows[key]
        if raw["sha256"] != warehouse["sha256"]:
            hash_mismatches += 1
            if len(mismatches) < mismatch_limit:
                mismatches.append({"key": key, "kind": "source_record_sha256", "raw": raw["sha256"], "warehouse": warehouse["sha256"]})
        raw_member_date = str(raw.get("member_date") or "")
        warehouse_member_date = "".join(ch for ch in str(warehouse.get("member_date") or "") if ch.isdigit())
        if raw_member_date != warehouse_member_date:
            member_date_mismatches += 1
            if len(mismatches) < mismatch_limit:
                mismatches.append({"key": key, "kind": "source_member_date", "raw": raw_member_date, "warehouse": warehouse_member_date})
        raw_parsed = raw["parsed"]
        warehouse_parsed = warehouse["parsed"]
        raw_logical_rows.append((key, raw_parsed))
        warehouse_logical_rows.append((key, warehouse_parsed))
        if raw_parsed != warehouse_parsed:
            logical_mismatches += 1
            if len(mismatches) < mismatch_limit:
                mismatches.append({"key": key, "kind": "logical_row", "raw": raw_parsed, "warehouse": warehouse_parsed})
        raw_projection_rows.append((key, projection(family, raw_parsed)))
        warehouse_projection_rows.append((key, projection(family, warehouse_parsed)))

    raw_logical_hash = stream_hash(raw_logical_rows)
    warehouse_logical_hash = stream_hash(warehouse_logical_rows)
    raw_projection_hash = stream_hash(raw_projection_rows)
    warehouse_projection_hash = stream_hash(warehouse_projection_rows)
    status = "PASS" if not (
        missing_in_warehouse or extra_in_warehouse or hash_mismatches
        or logical_mismatches or member_date_mismatches
        or raw_logical_hash != warehouse_logical_hash
        or raw_projection_hash != warehouse_projection_hash
    ) else "FAIL"
    return {
        "status": status,
        "family": family,
        "year": year,
        "raw_archive": raw_path.name,
        "raw_archive_sha256": sha256_file(raw_path),
        "raw_rows": len(raw_rows),
        "warehouse_rows": len(warehouse_rows),
        "missing_in_warehouse": len(missing_in_warehouse),
        "extra_in_warehouse": len(extra_in_warehouse),
        "source_record_sha256_mismatches": hash_mismatches,
        "source_member_date_mismatches": member_date_mismatches,
        "logical_row_mismatches": logical_mismatches,
        "raw_logical_hash": raw_logical_hash,
        "warehouse_logical_hash": warehouse_logical_hash,
        "raw_eval_projection_hash": raw_projection_hash,
        "warehouse_eval_projection_hash": warehouse_projection_hash,
        "sample_mismatches": mismatches,
        "sample_missing_in_warehouse": missing_in_warehouse[:mismatch_limit],
        "sample_extra_in_warehouse": extra_in_warehouse[:mismatch_limit],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit Eval Historical Raw vs accepted JRDB Warehouse.")
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--warehouse-bac-root", type=Path, required=True)
    parser.add_argument("--warehouse-sed-root", type=Path, required=True)
    parser.add_argument("--raw-bac-dir", type=Path, required=True)
    parser.add_argument("--raw-sed-dir", type=Path, required=True)
    parser.add_argument("--from-year", type=int, default=2010)
    parser.add_argument("--to-year", type=int, default=2025)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mismatch-limit", type=int, default=20)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report: dict[str, object] = {
        "audit": "jrdb_eval_raw_vs_warehouse",
        "status": "FAIL",
        "from_year": args.from_year,
        "to_year": args.to_year,
        "checks": [],
    }
    try:
        reader = WarehouseEvalReader(
            args.current,
            manifest=args.manifest,
            asset_roots={"BAC": args.warehouse_bac_root, "SED": args.warehouse_sed_root},
        )
        checks: list[dict[str, object]] = []
        for year in range(args.from_year, args.to_year + 1):
            for family, raw_dir in (("BAC", args.raw_bac_dir), ("SED", args.raw_sed_dir)):
                raw_path = raw_dir / f"{family}_{year}.zip"
                if not raw_path.is_file():
                    raise RuntimeError(f"missing Raw annual archive: {raw_path}")
                checks.append(compare_year_family(reader, family, year, raw_path, args.mismatch_limit))

        guard_2026 = False
        try:
            reader.require_historical_date(dt.date(2026, 1, 1))
        except EvalWarehouseError:
            guard_2026 = True

        repeat_year = args.to_year
        first = read_warehouse_year(reader, "SED", repeat_year)
        second = read_warehouse_year(reader, "SED", repeat_year)
        first_repeat_hash = stream_hash([(key, row["parsed"]) for key, row in first.items()])
        second_repeat_hash = stream_hash([(key, row["parsed"]) for key, row in second.items()])
        idempotent = first_repeat_hash == second_repeat_hash

        all_pass = all(check["status"] == "PASS" for check in checks)
        report.update({
            "status": "PASS" if all_pass and guard_2026 and idempotent else "FAIL",
            "source_generation_id": reader.current.get("generation_id"),
            "checks": checks,
            "warehouse_2026_guard": guard_2026,
            "warehouse_repeat_read_year": repeat_year,
            "warehouse_repeat_read_hash_1": first_repeat_hash,
            "warehouse_repeat_read_hash_2": second_repeat_hash,
            "warehouse_repeat_read_idempotent": idempotent,
            "summary": {
                "checks": len(checks),
                "passed": sum(1 for check in checks if check["status"] == "PASS"),
                "failed": sum(1 for check in checks if check["status"] != "PASS"),
                "raw_rows": sum(int(check["raw_rows"]) for check in checks),
                "warehouse_rows": sum(int(check["warehouse_rows"]) for check in checks),
                "logical_mismatches": sum(int(check["logical_row_mismatches"]) for check in checks),
                "record_hash_mismatches": sum(int(check["source_record_sha256_mismatches"]) for check in checks),
            },
        })
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
