#!/usr/bin/env python3
"""Reconstruct and settle one historical JRDB Edge day without mixing it into true-forward KPI."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import build_jrdb_edge_forward_ledger as forward_ledger
import evaluate_jrdb_edge_forward as forward_eval
import run_jrdb_edge_match_current as current_match

VERSION = "0.1.0"
EVALUATION_MODE = "RECONSTRUCTED_BACKFILL"


class BackfillError(RuntimeError):
    """Raised when a reconstructed backfill cannot be audited safely."""


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _verify_sha(path: str | Path, expected: str | None, label: str) -> str:
    actual = _sha256(path)
    if expected and actual != expected.lower():
        raise BackfillError(f"{label} SHA-256 mismatch: expected={expected.lower()} actual={actual}")
    return actual


def _analysis_coverage(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {"source": None, "min_race_date": None, "max_race_date": None}
    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            "SELECT MIN(race_date),MAX(race_date),COUNT(*) FROM fact_entry_result_lite"
        ).fetchone()
    finally:
        connection.close()
    return {
        "source": str(Path(path).name),
        "min_race_date": row[0],
        "max_race_date": row[1],
        "rows": int(row[2]),
    }


def _single_race_date(matches_jsonl: Path) -> str:
    dates: set[str] = set()
    rows = 0
    for line in matches_jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows += 1
        value = str((row.get("key") or {}).get("race_date") or "").strip()
        if value:
            dates.add(value)
    if not rows:
        raise BackfillError("matcher output has no runner rows")
    if len(dates) != 1:
        raise BackfillError(f"matcher output must contain exactly one race_date: {sorted(dates)}")
    return next(iter(dates))


def _write_manifest(output_dir: Path, provenance: dict[str, Any]) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(output_dir.iterdir()):
        if not path.is_file() or path.name == "manifest.json":
            continue
        files[path.name] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    manifest = {
        "status": "PASS",
        "driver_version": VERSION,
        "evaluation_mode": EVALUATION_MODE,
        "provenance": provenance,
        "files": files,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def run(
    *,
    paci_path: str | Path,
    sed_path: str | Path,
    registry_jsonl: str | Path,
    ledger_path: str | Path,
    output_dir: str | Path,
    analysis_db: str | Path | None = None,
    expected_paci_sha256: str | None = None,
    expected_sed_sha256: str | None = None,
    expected_registry_sha256: str | None = None,
    expected_analysis_sha256: str | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paci = Path(paci_path)
    sed = Path(sed_path)
    registry = Path(registry_jsonl)
    analysis = Path(analysis_db) if analysis_db is not None else None
    for label, path in (("PACI", paci), ("SED", sed), ("Registry", registry)):
        if not path.is_file():
            raise BackfillError(f"{label} input not found: {path}")
    if analysis is not None and not analysis.is_file():
        raise BackfillError(f"Analysis input not found: {analysis}")

    input_sha = {
        "paci_sha256": _verify_sha(paci, expected_paci_sha256, "PACI"),
        "sed_sha256": _verify_sha(sed, expected_sed_sha256, "SED"),
        "registry_sha256": _verify_sha(registry, expected_registry_sha256, "Registry"),
        "analysis_sha256": (
            _verify_sha(analysis, expected_analysis_sha256, "Analysis") if analysis is not None else None
        ),
    }

    facts_jsonl = output / "current_facts.jsonl"
    matches_jsonl = output / "edge_matches.jsonl"
    matcher_summary = current_match.run(
        paci_path=paci,
        analysis_db=analysis,
        registry_jsonl=registry,
        output_jsonl=matches_jsonl,
        facts_jsonl=facts_jsonl,
    )
    race_date = _single_race_date(matches_jsonl)

    forward_json = output / "forward_evaluation.json"
    audit_jsonl = output / "forward_audit.jsonl"
    evaluation = forward_eval.run(
        matches_jsonl=matches_jsonl,
        sed_path=sed,
        output_json=forward_json,
        audit_jsonl=audit_jsonl,
        evaluation_mode=EVALUATION_MODE,
    )
    runner_audit = evaluation.get("runner_audit") or {}
    if runner_audit.get("matcher_rows") != matcher_summary.get("runner_rows"):
        raise BackfillError(
            f"matcher/evaluator row mismatch: {matcher_summary.get('runner_rows')} != "
            f"{runner_audit.get('matcher_rows')}"
        )
    if runner_audit.get("sed_joined_rows") != matcher_summary.get("runner_rows"):
        raise BackfillError(
            f"SED exact-join incomplete: joined={runner_audit.get('sed_joined_rows')} "
            f"matcher={matcher_summary.get('runner_rows')}"
        )

    ledger_result = forward_ledger.run(
        ledger_path=ledger_path,
        audit_jsonl=audit_jsonl,
        race_date=race_date,
        evaluation_mode=EVALUATION_MODE,
        output_json=output / "ledger_result.json",
        summary_evaluation_mode=EVALUATION_MODE,
    )

    provenance = {
        "race_date": race_date,
        "evaluation_mode": EVALUATION_MODE,
        "input_sha256": input_sha,
        "analysis_coverage": _analysis_coverage(analysis),
        "registry_versions": matcher_summary.get("registry_versions"),
        "matcher": matcher_summary,
        "settlement_runner_audit": runner_audit,
        "ledger_import": ledger_result.get("import"),
        "warning": (
            "RECONSTRUCTED_BACKFILL is not pre-race frozen and must not be mixed into TRUE_FORWARD KPI"
        ),
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = _write_manifest(output, provenance)
    return {
        "status": "success",
        "driver_version": VERSION,
        "evaluation_mode": EVALUATION_MODE,
        "race_date": race_date,
        "matcher": matcher_summary,
        "evaluation_overall": evaluation.get("overall"),
        "ledger": ledger_result,
        "manifest": manifest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paci", required=True)
    parser.add_argument("--sed", required=True)
    parser.add_argument("--registry-jsonl", required=True)
    parser.add_argument("--analysis-db")
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--expected-paci-sha256")
    parser.add_argument("--expected-sed-sha256")
    parser.add_argument("--expected-registry-sha256")
    parser.add_argument("--expected-analysis-sha256")
    args = parser.parse_args()
    result = run(
        paci_path=args.paci,
        sed_path=args.sed,
        registry_jsonl=args.registry_jsonl,
        analysis_db=args.analysis_db,
        ledger_path=args.ledger,
        output_dir=args.output_dir,
        expected_paci_sha256=args.expected_paci_sha256,
        expected_sed_sha256=args.expected_sed_sha256,
        expected_registry_sha256=args.expected_registry_sha256,
        expected_analysis_sha256=args.expected_analysis_sha256,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
