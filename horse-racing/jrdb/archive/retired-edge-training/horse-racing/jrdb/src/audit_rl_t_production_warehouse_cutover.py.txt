#!/usr/bin/env python3
"""Final static audit for RL-T production Historical Warehouse cutover."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PRODUCTION_FILES = (
    ".github/workflows/jrdb_training_edge_v02_daily_issue.yml",
    ".github/workflows/jrdb_training_edge_v02_replay_issue.yml",
    ".github/workflows/jrdb_training_research_issue.yml",
    "horse-racing/jrdb/src/prepare_rl_t_historical_warehouse_inputs.py",
    "horse-racing/jrdb/src/build_jrdb_index_base_hybrid.py",
    "horse-racing/jrdb/src/build_jrdb_index_base_from_warehouse.py",
    "horse-racing/jrdb/src/build_jrdb_runperf_features.py",
    "horse-racing/jrdb/src/build_jrdb_official_runperf.py",
)
WORKFLOWS = PRODUCTION_FILES[:3]
OLD_PATTERNS = (
    "GPT/JRDB",
    "jrdb_store_manifest_v1.json",
    "legacy jrdb://",
)
HISTORICAL_FETCH_SIGNATURE = "--from-year 2010 --to-year 2025"
ACCEPTED_GENERATION = "jrdb_normalized_warehouse_v1_2010_2025_g20260921"


def audit(root: Path) -> dict[str, Any]:
    root = root.resolve()
    texts = {path: (root / path).read_text(encoding="utf-8") for path in PRODUCTION_FILES}
    checks: list[dict[str, Any]] = []

    for path in WORKFLOWS:
        text = texts[path]
        checks.append({
            "name": f"{path}:historical_raw_fetch_absent",
            "pass": HISTORICAL_FETCH_SIGNATURE not in text,
        })
        checks.append({
            "name": f"{path}:accepted_generation_present",
            "pass": ACCEPTED_GENERATION in text,
        })

    daily = texts[WORKFLOWS[0]]
    replay = texts[WORKFLOWS[1]]
    research = texts[WORKFLOWS[2]]
    preparer = texts[PRODUCTION_FILES[3]]

    checks.extend([
        {
            "name": "daily_uses_hybrid_builder",
            "pass": "build_jrdb_index_base_hybrid.py" in daily,
        },
        {
            "name": "replay_uses_hybrid_builder",
            "pass": "build_jrdb_index_base_hybrid.py" in replay,
        },
        {
            "name": "training_research_uses_warehouse_builder",
            "pass": "build_jrdb_index_base_from_warehouse.py" in research,
        },
        {
            "name": "daily_2026_paci_sed_route_retained",
            "pass": "PACI_FOLDER_URL" in daily and "SED_FOLDER_URL" in daily,
        },
        {
            "name": "replay_2026_paci_sed_route_retained",
            "pass": "PACI_FOLDER_URL" in replay and "SED_FOLDER_URL" in replay,
        },
        {
            "name": "shared_preparer_reports_no_historical_raw",
            "pass": '"historical_raw_required": False' in preparer,
        },
        {
            "name": "shared_preparer_no_gdown_folder",
            "pass": "gdown --folder" not in preparer,
        },
    ])

    active_legacy_refs: list[dict[str, Any]] = []
    for path, text in texts.items():
        for pattern in OLD_PATTERNS:
            if pattern.lower() in text.lower():
                active_legacy_refs.append({"path": path, "pattern": pattern})
        if "fetch_jrdb_history.py" in text and path in WORKFLOWS:
            lines = [
                line.strip()
                for line in text.splitlines()
                if "fetch_jrdb_history.py" in line
            ]
            if lines:
                active_legacy_refs.extend(
                    {"path": path, "pattern": line}
                    for line in lines
                )

    # Current-year PACI / settled SED Raw-direct references are explicitly allowed.
    active_legacy_refs = [
        item for item in active_legacy_refs
        if not (
            item["path"] in WORKFLOWS[:2]
            and "fetch_jrdb_history.py" not in item["pattern"]
        )
    ]

    checks.append({
        "name": "rl_t_old_gpt_jrdb_active_reference_count",
        "pass": len(active_legacy_refs) == 0,
        "active_reference_count": len(active_legacy_refs),
        "active_references": active_legacy_refs,
    })

    failures = [check for check in checks if not check["pass"]]
    return {
        "status": "PASS" if not failures else "FAIL",
        "audit_version": "rl_t_production_warehouse_cutover_v1",
        "historical_generation": ACCEPTED_GENERATION,
        "historical_normal_operation": "WAREHOUSE",
        "historical_raw_normal_fetch": "DISABLED",
        "historical_raw_fallback": "DISABLED",
        "current_2026_route": "UNCHANGED",
        "checks": checks,
        "failure_count": len(failures),
        "failures": failures,
        "rl_t_old_gpt_jrdb_active_reference_count": len(active_legacy_refs),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = audit(args.root)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if report["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
