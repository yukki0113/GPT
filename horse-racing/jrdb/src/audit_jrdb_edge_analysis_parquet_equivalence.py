#!/usr/bin/env python3
"""Audit Edge current matching equivalence between Analysis SQLite and Parquet.

This is a migration gate only.  It does not change Edge Registry semantics,
serving profile, thresholds, or matcher behavior.  The same PACI and serving
catalog are run twice and the pre-race facts plus matched Edge output must be
byte-identical.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import run_jrdb_edge_match_current_v0_2 as current_match

VERSION = "0.1.0"


class EdgeAnalysisEquivalenceError(RuntimeError):
    """Raised when SQLite and Parquet do not produce identical Edge inputs/results."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_once(
    *,
    paci: Path,
    serving_catalog: Path,
    output_dir: Path,
    analysis_db: Path | None = None,
    analysis_root: Path | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    matches = output_dir / "edge_matches.jsonl"
    facts = output_dir / "current_facts.jsonl"
    audit = output_dir / "matcher_audit.json"
    summary = current_match.run(
        paci_path=paci,
        registry_jsonl=serving_catalog,
        output_jsonl=matches,
        facts_jsonl=facts,
        audit_json=audit,
        analysis_db=analysis_db,
        analysis_root=analysis_root,
        serving_profile=current_match.PROFILE_STANDARD if hasattr(current_match, "PROFILE_STANDARD") else "STANDARD",
        statuses=None,
    )
    return {
        "summary": summary,
        "facts": facts,
        "matches": matches,
        "audit": json.loads(audit.read_text(encoding="utf-8")),
        "facts_sha256": _sha256(facts),
        "matches_sha256": _sha256(matches),
    }


def audit(
    *,
    paci: str | Path,
    serving_catalog: str | Path,
    analysis_db: str | Path,
    analysis_root: str | Path,
) -> dict[str, Any]:
    """Fail closed unless both Analysis backends produce identical Edge output."""
    paci_path = Path(paci)
    catalog_path = Path(serving_catalog)
    sqlite_path = Path(analysis_db)
    parquet_root = Path(analysis_root)
    for label, path in (
        ("PACI", paci_path),
        ("serving catalog", catalog_path),
        ("Analysis SQLite", sqlite_path),
    ):
        if not path.is_file():
            raise EdgeAnalysisEquivalenceError(f"{label} not found: {path}")
    if not parquet_root.is_dir():
        raise EdgeAnalysisEquivalenceError(f"Analysis Parquet root not found: {parquet_root}")

    with tempfile.TemporaryDirectory(prefix="jrdb-edge-analysis-eq-") as temp:
        root = Path(temp)
        sqlite = _run_once(
            paci=paci_path,
            serving_catalog=catalog_path,
            output_dir=root / "sqlite",
            analysis_db=sqlite_path,
        )
        parquet = _run_once(
            paci=paci_path,
            serving_catalog=catalog_path,
            output_dir=root / "parquet",
            analysis_root=parquet_root,
        )

        facts_equal = sqlite["facts"].read_bytes() == parquet["facts"].read_bytes()
        matches_equal = sqlite["matches"].read_bytes() == parquet["matches"].read_bytes()
        if not facts_equal or not matches_equal:
            raise EdgeAnalysisEquivalenceError(
                "Analysis backend equivalence failed: "
                f"facts_equal={facts_equal} matches_equal={matches_equal}"
            )

        return {
            "status": "PASS",
            "version": VERSION,
            "serving_profile": "STANDARD",
            "paci_sha256": _sha256(paci_path),
            "serving_catalog_sha256": _sha256(catalog_path),
            "sqlite": {
                "analysis_history": sqlite["audit"].get("analysis_history"),
                "runner_rows": sqlite["summary"]["runner_rows"],
                "matched_runners": sqlite["summary"]["matched_runners"],
                "matches": sqlite["summary"]["matches"],
                "facts_sha256": sqlite["facts_sha256"],
                "matches_sha256": sqlite["matches_sha256"],
            },
            "parquet": {
                "analysis_history": parquet["audit"].get("analysis_history"),
                "runner_rows": parquet["summary"]["runner_rows"],
                "matched_runners": parquet["summary"]["matched_runners"],
                "matches": parquet["summary"]["matches"],
                "facts_sha256": parquet["facts_sha256"],
                "matches_sha256": parquet["matches_sha256"],
            },
            "facts_byte_identical": facts_equal,
            "matches_byte_identical": matches_equal,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paci", required=True)
    parser.add_argument("--serving-catalog-jsonl", required=True)
    parser.add_argument("--analysis-db", required=True)
    parser.add_argument("--analysis-root", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    result = audit(
        paci=args.paci,
        serving_catalog=args.serving_catalog_jsonl,
        analysis_db=args.analysis_db,
        analysis_root=args.analysis_root,
    )
    Path(args.output_json).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
