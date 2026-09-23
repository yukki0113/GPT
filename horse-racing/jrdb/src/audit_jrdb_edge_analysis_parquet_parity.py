#!/usr/bin/env python3
"""Audit Edge current-fact/match parity between Analysis SQLite and Parquet.

This is a historical input-parity audit only. It consumes no SED/result data and
must never be labelled TRUE_FORWARD. The acceptance gate is byte-identical
current_facts.jsonl and edge_matches.jsonl for the same PACI and serving catalog.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import run_jrdb_edge_match_current_v0_2 as current_match


class ParityAuditError(RuntimeError):
    """Raised when SQLite and Parquet Edge inputs are not semantically identical."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _first_difference(left: Path, right: Path) -> dict[str, Any] | None:
    left_rows = _read_jsonl(left)
    right_rows = _read_jsonl(right)
    length = max(len(left_rows), len(right_rows))
    for index in range(length):
        lrow = left_rows[index] if index < len(left_rows) else None
        rrow = right_rows[index] if index < len(right_rows) else None
        if lrow != rrow:
            return {
                "row_index": index,
                "sqlite": lrow,
                "parquet": rrow,
            }
    return None


def run(
    *,
    paci_path: str | Path,
    serving_catalog_jsonl: str | Path,
    analysis_db: str | Path,
    analysis_root: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    sqlite_dir = output / "sqlite"
    parquet_dir = output / "parquet"
    sqlite_dir.mkdir(exist_ok=True)
    parquet_dir.mkdir(exist_ok=True)

    sqlite_summary = current_match.run(
        paci_path=paci_path,
        analysis_db=analysis_db,
        registry_jsonl=serving_catalog_jsonl,
        output_jsonl=sqlite_dir / "edge_matches.jsonl",
        facts_jsonl=sqlite_dir / "current_facts.jsonl",
        audit_json=sqlite_dir / "matcher_audit.json",
        serving_profile="STANDARD",
        statuses=None,
    )
    parquet_summary = current_match.run(
        paci_path=paci_path,
        analysis_root=analysis_root,
        registry_jsonl=serving_catalog_jsonl,
        output_jsonl=parquet_dir / "edge_matches.jsonl",
        facts_jsonl=parquet_dir / "current_facts.jsonl",
        audit_json=parquet_dir / "matcher_audit.json",
        serving_profile="STANDARD",
        statuses=None,
    )

    facts_sqlite = sqlite_dir / "current_facts.jsonl"
    facts_parquet = parquet_dir / "current_facts.jsonl"
    matches_sqlite = sqlite_dir / "edge_matches.jsonl"
    matches_parquet = parquet_dir / "edge_matches.jsonl"

    facts_hashes = {
        "sqlite": _sha256(facts_sqlite),
        "parquet": _sha256(facts_parquet),
    }
    match_hashes = {
        "sqlite": _sha256(matches_sqlite),
        "parquet": _sha256(matches_parquet),
    }
    facts_equal = facts_hashes["sqlite"] == facts_hashes["parquet"]
    matches_equal = match_hashes["sqlite"] == match_hashes["parquet"]

    result = {
        "status": "PASS" if facts_equal and matches_equal else "FAIL",
        "evaluation_mode": "HISTORICAL_INPUT_PARITY_AUDIT",
        "result_data_used": False,
        "serving_profile": "STANDARD",
        "facts_byte_identical": facts_equal,
        "matches_byte_identical": matches_equal,
        "facts_sha256": facts_hashes,
        "matches_sha256": match_hashes,
        "sqlite_summary": sqlite_summary,
        "parquet_summary": parquet_summary,
        "first_facts_difference": None if facts_equal else _first_difference(facts_sqlite, facts_parquet),
        "first_matches_difference": None if matches_equal else _first_difference(matches_sqlite, matches_parquet),
    }
    (output / "parity_audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if result["status"] != "PASS":
        raise ParityAuditError("Edge Analysis SQLite/Parquet parity audit failed")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paci", required=True)
    parser.add_argument("--serving-catalog-jsonl", required=True)
    parser.add_argument("--analysis-db", required=True)
    parser.add_argument("--analysis-root", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    result = run(
        paci_path=args.paci,
        serving_catalog_jsonl=args.serving_catalog_jsonl,
        analysis_db=args.analysis_db,
        analysis_root=args.analysis_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
