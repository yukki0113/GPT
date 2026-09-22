#!/usr/bin/env python3
"""Fail-closed semantic audit for Raw and Warehouse RaceNote Archive months."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import racenote_archive as archive


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare full-month Raw and Warehouse Archive logical content")
    parser.add_argument("--raw-archive", type=Path, required=True)
    parser.add_argument("--warehouse-archive", type=Path, required=True)
    parser.add_argument("--warehouse-repeat", type=Path, required=True,
                        help="independent repeated Warehouse build for determinism")
    parser.add_argument("--raw-summary", type=Path, required=True)
    parser.add_argument("--warehouse-summary", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def _canonical_hash(rows: list[tuple[str, str]]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def read_archive(path: Path) -> dict[str, Any]:
    connection = archive.open_archive(path)
    try:
        validation = archive.validate_archive(connection, full_scan=True)
        meta = archive.get_meta(connection)
        schema = [tuple(row) for row in connection.execute("PRAGMA table_info(race_bundle)").fetchall()]
        rows = connection.execute(
            "SELECT race_date, venue_code, race_no, semantic_sha256 FROM race_bundle ORDER BY race_date, venue_code, race_no"
        ).fetchall()
        keys = [f"{row[0]}|{row[1]}|{int(row[2])}" for row in rows]
        semantic = [(key, str(row[3])) for key, row in zip(keys, rows)]
        source_rows = int(connection.execute("SELECT COUNT(*) FROM source_input").fetchone()[0])
    finally:
        connection.close()
    return {
        "validation": validation, "meta": meta, "schema": schema, "keys": keys,
        "semantic": semantic, "semantic_hash": _canonical_hash(semantic),
        "source_input_count": source_rows,
    }


def summary(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("status") != "PASS":
        raise ValueError(f"PASS build summary required: {path}")
    return value


def compare(args: argparse.Namespace) -> dict[str, Any]:
    raw, warehouse, repeated = (read_archive(path) for path in (args.raw_archive, args.warehouse_archive, args.warehouse_repeat))
    raw_summary, warehouse_summary = summary(args.raw_summary), summary(args.warehouse_summary)
    key_equal = raw["keys"] == warehouse["keys"]
    semantic_equal = raw["semantic"] == warehouse["semantic"]
    deterministic = warehouse["semantic"] == repeated["semantic"]
    required = (
        raw["validation"]["status"] == "PASS", warehouse["validation"]["status"] == "PASS",
        repeated["validation"]["status"] == "PASS", raw["schema"] == warehouse["schema"],
        key_equal, semantic_equal, deterministic,
        raw["meta"].get("coverage_mode") == warehouse["meta"].get("coverage_mode") == "full_month",
        raw["meta"].get("publication_status") == warehouse["meta"].get("publication_status") == "publishable",
        raw["meta"].get("provenance_status") == warehouse["meta"].get("provenance_status") == "complete",
        warehouse_summary.get("input_backend") == "jrdb_warehouse",
    )
    return {
        "audit": "racenote_archive_raw_vs_warehouse", "status": "PASS" if all(required) else "FAIL",
        "target_month": warehouse["validation"]["target_month"],
        "race_count": {"raw": raw["validation"]["race_count"], "warehouse": warehouse["validation"]["race_count"]},
        "schema_equal": raw["schema"] == warehouse["schema"],
        "race_identity_equal": key_equal,
        "bundle_semantic_hash": {"raw": raw["semantic_hash"], "warehouse": warehouse["semantic_hash"], "equal": semantic_equal},
        "full_scan": {"raw": raw["validation"], "warehouse": warehouse["validation"], "repeat": repeated["validation"]},
        "provenance": {"raw_source_input_count": raw["source_input_count"], "warehouse_source_input_count": warehouse["source_input_count"], "warehouse_generation_id": warehouse_summary.get("warehouse_generation_id"), "boundary_previous_result_key_count": warehouse_summary.get("boundary_previous_result_key_count"), "boundary_raw_source_count": warehouse_summary.get("boundary_raw_source_count")},
        "determinism": {"warehouse_first": warehouse["semantic_hash"], "warehouse_repeat": repeated["semantic_hash"], "equal": deterministic},
        "raw_source_mode": raw["meta"].get("source_mode"), "warehouse_source_mode": warehouse["meta"].get("source_mode"),
    }


def main() -> int:
    args = parse_args()
    try:
        result = compare(args)
    except (OSError, ValueError, json.JSONDecodeError, archive.RaceNoteArchiveError) as exc:
        result = {"audit": "racenote_archive_raw_vs_warehouse", "status": "ERROR", "error": str(exc)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
