#!/usr/bin/env python3
"""Build, but never promote, an Analysis Parquet post-race candidate.

The post-race SQLite database is a disposable transformation workspace.  This
entry point turns the fully-audited workspace into a new immutable Parquet
generation.  It deliberately has no promotion option: Drive round-trip
validation and the separate current-pointer step follow in later stages.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jrdb_analysis_parquet_current import resolve_current, validate_generation
from migrate_jrdb_analysis_parquet import migrate


class AnalysisCandidateError(RuntimeError):
    """Raised when a candidate fails a gate before pointer promotion."""


def _require(value: object, label: str, expected: object) -> None:
    if value != expected:
        raise AnalysisCandidateError(f"Candidate {label} must be {expected!r}: {value!r}")


def _audit_gate(audit: object) -> dict[str, Any]:
    if not isinstance(audit, dict):
        raise AnalysisCandidateError("Candidate audit is missing")
    for key, expected in (
        ("status", "PASS"),
        ("row_count_equal", True),
        ("canonical_key_equal", True),
        ("schema_contract_equal", True),
        ("row_level_equivalence", True),
        ("metadata_preserved", True),
        ("duplicate_key_rows", 0),
    ):
        _require(audit.get(key), f"audit.{key}", expected)
    return audit


def build_candidate(
    source_sqlite: Path,
    analysis_root: Path,
    generation_id: str,
    affected_years: set[int],
) -> dict[str, Any]:
    """Create and locally validate a shadow candidate without touching current.

    ``affected_years`` is explicit so unchanged year objects can be reused from
    the currently validated generation.  The resulting ``shadow_current.json``
    is only a candidate marker and is never a canonical pointer.
    """
    root = analysis_root.resolve()
    source_sqlite = source_sqlite.resolve()
    if not generation_id:
        raise ValueError("generation_id is required")
    if not affected_years:
        raise ValueError("affected_years is required")
    if (root / "generations" / generation_id).exists():
        raise FileExistsError(root / "generations" / generation_id)

    current_path = root / "current.json"
    current_before = current_path.read_bytes()
    base = resolve_current(root)
    result = migrate(
        source_sqlite,
        root,
        generation_id,
        affected_years=set(affected_years),
        reuse_manifest=base["manifest"],
        promote=False,
    )
    if current_path.read_bytes() != current_before:
        raise AnalysisCandidateError("Candidate build changed current.json")

    pointer = result.get("pointer") if isinstance(result, dict) else None
    if not isinstance(pointer, dict):
        raise AnalysisCandidateError("Candidate pointer is missing")
    _require(pointer.get("status"), "pointer.status", "SHADOW_PASS")
    _require(pointer.get("generation_id"), "pointer.generation_id", generation_id)
    expected_manifest = f"generations/{generation_id}/manifest.json"
    _require(pointer.get("manifest"), "pointer.manifest", expected_manifest)
    audit = _audit_gate(result.get("audit"))

    candidate = validate_generation(root, root / expected_manifest)
    _require(candidate.get("generation_id"), "manifest.generation_id", generation_id)
    return {
        "status": "CANDIDATE_PASS",
        "candidate_generation_id": generation_id,
        "previous_generation_id": base["generation_id"],
        "manifest": expected_manifest,
        "rows": candidate["rows"],
        "affected_years": sorted(affected_years),
        "audit": audit,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sqlite", type=Path, required=True)
    parser.add_argument("--analysis-root", type=Path, required=True)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--affected-year", type=int, action="append", required=True)
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()
    result = build_candidate(
        args.source_sqlite,
        args.analysis_root,
        args.generation_id,
        set(args.affected_year),
    )
    if args.result_json:
        args.result_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
