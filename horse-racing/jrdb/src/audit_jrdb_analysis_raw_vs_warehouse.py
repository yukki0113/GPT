#!/usr/bin/env python3
"""Non-mutating full logical equivalence audit for Raw-direct and Warehouse Analysis input."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from jrdb_analysis_warehouse_adapter import WarehouseAnalysisReader
from update_jrdb_analysis_incremental import FACT_COLUMNS, parse_date, parse_day

KEY = ("race_key", "horse_no")


def _canon(value: object) -> str:
    if value is None: return "N:"
    if isinstance(value, float): return f"F:{value:.17g}"
    return f"S:{value}"


def _indexed(rows: Iterable[tuple]) -> dict[tuple[object, object], tuple]:
    result = {}
    for row in rows:
        key = (row[FACT_COLUMNS.index(KEY[0])], row[FACT_COLUMNS.index(KEY[1])])
        if key in result: raise RuntimeError(f"duplicate Analysis canonical key: {key!r}")
        result[key] = row
    return result


def _row_hash(indexed: Mapping[tuple[object, object], tuple]) -> str:
    digest = hashlib.sha256(("|".join(FACT_COLUMNS) + "\n").encode())
    for key in sorted(indexed, key=lambda value: tuple(_canon(v) for v in value)):
        digest.update("\x1f".join(_canon(value) for value in indexed[key]).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _null_blank(rows: Iterable[tuple]) -> dict[str, dict[str, int]]:
    data = list(rows)
    return {column: {"null": sum(row[index] is None for row in data), "blank": sum(row[index] == "" for row in data)} for index, column in enumerate(FACT_COLUMNS)}


def _representative(rows: Iterable[tuple]) -> dict[str, Any]:
    index = {name: FACT_COLUMNS.index(name) for name in ("venue_code", "track_type", "finish", "training_index")}
    rows = list(rows)
    return {"rows": len(rows), "by_venue_track": sorted(Counter((row[index["venue_code"]], row[index["track_type"]]) for row in rows).items()), "finish_non_null": sum(row[index["finish"]] is not None for row in rows), "training_non_null": sum(row[index["training_index"]] is not None for row in rows)}


def compare(raw_rows: list[tuple], warehouse_rows: list[tuple], warehouse_repeat: list[tuple]) -> dict[str, Any]:
    raw, wh, repeated = _indexed(raw_rows), _indexed(warehouse_rows), _indexed(warehouse_repeat)
    schema_equal = len(raw_rows) >= 0 and len(FACT_COLUMNS) == len(next(iter(raw.values()), ())) == len(next(iter(wh.values()), ()))
    result = {"status": "PASS", "row_count": {"raw": len(raw), "warehouse": len(wh)}, "schema": {"columns": list(FACT_COLUMNS), "equal": schema_equal}, "primary_key": {"raw_count": len(raw), "warehouse_count": len(wh), "equal": set(raw) == set(wh), "duplicates": 0}, "null_blank_semantics_equal": _null_blank(raw.values()) == _null_blank(wh.values()), "canonical_row_hash": {"raw": _row_hash(raw), "warehouse": _row_hash(wh)}, "representative_query": {"raw": _representative(raw.values()), "warehouse": _representative(wh.values())}, "idempotence": {"warehouse_first": _row_hash(wh), "warehouse_second": _row_hash(repeated)}}
    result["canonical_row_hash"]["equal"] = result["canonical_row_hash"]["raw"] == result["canonical_row_hash"]["warehouse"]
    result["idempotence"]["equal"] = result["idempotence"]["warehouse_first"] == result["idempotence"]["warehouse_second"]
    mismatches = [key for key in sorted(set(raw) | set(wh)) if raw.get(key) != wh.get(key)]
    result["all_logical_columns_equal"] = not mismatches
    result["mismatch_key_count"] = len(mismatches)
    result["mismatch_key_sample"] = [list(key) for key in mismatches[:20]]
    required = (result["schema"]["equal"], result["primary_key"]["equal"], result["null_blank_semantics_equal"], result["canonical_row_hash"]["equal"], result["all_logical_columns_equal"], result["representative_query"]["raw"] == result["representative_query"]["warehouse"], result["idempotence"]["equal"])
    if not all(required): result["status"] = "FAIL"
    return result


def _asset_roots(values: list[str]) -> dict[str, Path]:
    roots = {}
    for value in values:
        family, sep, path = value.partition("=")
        if not sep or not family or not path: raise ValueError("--asset-root requires FAMILY=/local/staging/root")
        roots[family.upper()] = Path(path)
    return roots


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--warehouse-current", type=Path, required=True)
    parser.add_argument("--asset-root", action="append", required=True)
    parser.add_argument("--source-member-date")
    parser.add_argument("--audit-json", type=Path)
    args = parser.parse_args()
    date = parse_date(args.date)
    member_date = parse_date(args.source_member_date) if args.source_member_date else None
    raw_rows, raw_meta = parse_day(args.raw_root, date)
    reader = WarehouseAnalysisReader(args.warehouse_current, asset_roots=_asset_roots(args.asset_root))
    warehouse_rows, warehouse_meta = reader.parse_day(date, source_member_date=member_date)
    warehouse_repeat, _ = reader.parse_day(date, source_member_date=member_date)
    result = compare(raw_rows, warehouse_rows, warehouse_repeat)
    result.update({"target_date": date.isoformat(), "raw_meta": raw_meta, "warehouse_meta": warehouse_meta})
    if args.audit_json: args.audit_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] != "PASS": raise SystemExit(2)


if __name__ == "__main__": main()
