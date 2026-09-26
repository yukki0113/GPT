#!/usr/bin/env python3
"""Audit the RL-T Training Research Parquet cutover for active legacy dependencies."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OLD_DEVELOPMENT_LITE_DRIVE_ID = "1RGRVoUI3utSC3r8Zf5Gk3i9Voq7JZqmj"
LEGACY_WORKFLOW = Path(".github/workflows/jrdb_training_stage2b_issue.yml")
PARQUET_WORKFLOW = Path(".github/workflows/jrdb_training_stage2b_parquet_issue.yml")
STAGE2B_SOURCE = Path("horse-racing/jrdb/src/analyze_jrdb_training_stage2b.py")
RESOLVER = Path("horse-racing/jrdb/src/jrdb_training_research_parquet.py")

ALLOWED_HISTORICAL_REFERENCE_PREFIXES = (
    ".github/workflows/jrdb_training_stage2b_issue.yml",
    "horse-racing/jrdb/docs/RL_T_TrainingResearch_Parquet_Work_Request_20260917.md",
    "horse-racing/jrdb/src/audit_rl_t_training_research_parquet_cutover.py",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def audit(root: Path) -> dict[str, Any]:
    root = root.resolve()
    checks: list[dict[str, Any]] = []

    legacy_text = _read(root / LEGACY_WORKFLOW)
    parquet_text = _read(root / PARQUET_WORKFLOW)
    source_text = _read(root / STAGE2B_SOURCE)
    resolver_text = _read(root / RESOLVER)

    checks.append({
        "name": "legacy_workflow_retired_marker",
        "pass": "RETIRED 2026-09-26" in legacy_text,
    })
    checks.append({
        "name": "legacy_workflow_issue_trigger_removed",
        "pass": "on:\n  workflow_dispatch:" in legacy_text and "on:\n  issues:" not in legacy_text,
    })
    checks.append({
        "name": "legacy_workflow_job_disabled",
        "pass": "if: ${{ false }}" in legacy_text,
    })
    checks.append({
        "name": "parquet_workflow_has_no_deleted_drive_id",
        "pass": OLD_DEVELOPMENT_LITE_DRIVE_ID not in parquet_text,
    })
    checks.append({
        "name": "parquet_workflow_uses_training_development_parquet",
        "pass": "training_development.parquet" in parquet_text,
    })
    checks.append({
        "name": "parquet_workflow_uses_stage2b_input",
        "pass": "--input \"$DEVELOPMENT_PATH\"" in parquet_text,
    })
    checks.append({
        "name": "stage2b_parquet_normal_path_documented",
        "pass": "Parquet is the normal analytical path" in source_text,
    })
    checks.append({
        "name": "stage2b_legacy_db_marked_historical",
        "pass": "Legacy SQLite input for historical reproduction only." in source_text,
    })
    checks.append({
        "name": "training_research_current_resolver_present",
        "pass": "def resolve_current(" in resolver_text and "training_development.parquet" in resolver_text,
    })

    references: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith(".git/"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if OLD_DEVELOPMENT_LITE_DRIVE_ID in text:
            references.append(relative)

    unexpected = [
        path for path in references
        if not any(path.startswith(prefix) for prefix in ALLOWED_HISTORICAL_REFERENCE_PREFIXES)
    ]
    checks.append({
        "name": "deleted_drive_id_active_reference_count",
        "pass": not unexpected,
        "all_references": references,
        "unexpected_references": unexpected,
        "active_reference_count": len(unexpected),
    })

    failures = [check for check in checks if not check["pass"]]
    return {
        "status": "PASS" if not failures else "FAIL",
        "audit": "rl_t_training_research_parquet_cutover_v1",
        "checks": checks,
        "failure_count": len(failures),
        "failures": failures,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = audit(args.root)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    if report["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
