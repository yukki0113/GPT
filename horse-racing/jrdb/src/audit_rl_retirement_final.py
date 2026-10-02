#!/usr/bin/env python3
"""Final static retirement audit; reuses the permanent T3 downstream audit."""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "horse-racing/jrdb/src"
WORKFLOW_DIR = ROOT / ".github/workflows"
SHARED_WORKFLOWS = (
    ".github/workflows/rlt_historical_warehouse_audit_issue.yml",
    ".github/workflows/rlt_record_hash_compat_direct_smoke_issue.yml",
    ".github/workflows/rlt_record_hash_compat_export_issue.yml",
    ".github/workflows/rlt_record_hash_compat_split_issue.yml",
    ".github/workflows/rlt_warehouse_direct_materialize_issue.yml",
)
FROZEN_FILES = (
    "horse-racing/jrdb/src/training_edge_v0_2_core.py",
    "horse-racing/jrdb/src/evaluate_training_edge_v0_1_holdout.py",
    "horse-racing/jrdb/src/evaluate_training_edge_v0_2_oot.py",
    "horse-racing/jrdb/src/fingerprint_training_edge_v0_2_runtime.py",
    "horse-racing/jrdb/src/project_training_edge_v0_2_input.py",
    "horse-racing/jrdb/src/score_training_edge_v0_2_daily.py",
    "horse-racing/jrdb/src/build_jrdb_training_research.py",
    "horse-racing/jrdb/src/audit_jrdb_training_research.py",
    "horse-racing/jrdb/src/jrdb_training_research_parquet.py",
    "horse-racing/jrdb/src/migrate_jrdb_training_research_parquet.py",
    "horse-racing/jrdb/schema/jrdb_training_research_schema_v0_1.sql",
    "horse-racing/jrdb/config/training_edge_v0_2_calibration.json",
    "horse-racing/jrdb/config/training_edge_v0_2_runtime_fingerprint.json",
    "horse-racing/jrdb/config/training_edge_v0_2_runtime_versions.json",
    "horse-racing/jrdb/tests/test_fingerprint_training_edge_v0_2_runtime.py",
    "horse-racing/jrdb/tests/test_jrdb_training_research.py",
    "horse-racing/jrdb/tests/test_jrdb_training_research_parquet_resolver.py",
    "horse-racing/jrdb/tests/test_project_training_edge_v0_2_input.py",
    "horse-racing/jrdb/tests/test_score_training_edge_v0_2_daily.py",
    "horse-racing/jrdb/tests/test_training_edge_v0_2_core.py",
)
ISSUE_PATTERNS = (
    "JRDB_TRAINING_EDGE",
    "JRDB_TRAINING_V02",
    "JRDB_TRAINING_RESEARCH",
    "RL_T_HISTORICAL_WAREHOUSE_DOWNSTREAM",
)
FORBIDDEN_WORKFLOW_PATTERNS = (
    "score_training_edge_v0_2_daily.py",
    "project_training_edge_v0_2_input.py",
    "training_edge_v0_2_core.py",
    "build_jrdb_training_research.py",
    "migrate_jrdb_training_research_parquet.py",
    "--my-index-csv",
)
INFRA_PATHS = (
    "horse-racing/jrdb/src/build_jrdb_index_base_from_warehouse.py",
    "horse-racing/jrdb/src/build_jrdb_index_base_hybrid.py",
    "horse-racing/jrdb/src/jrdb_index_base_warehouse_adapter.py",
    "horse-racing/jrdb/src/build_jrdb_index_base_record_hash_compat.py",
    "horse-racing/jrdb/src/materialize_jrdb_index_base_record_hash_compat.py",
    "horse-racing/jrdb/src/materialize_jrdb_index_base_record_hash_compat_set.py",
    "horse-racing/jrdb/src/materialize_jrdb_warehouse_from_object_index.py",
)

def check(name: str, passed: bool, detail: Any = None) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "detail": detail}

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def _open_research_issues() -> list[dict[str, Any]]:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN/GITHUB_TOKEN is required for the open-issue gate")
    matches: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/yukki0113/GPT/issues?state=open&per_page=100&page={page}"
        request = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        with urllib.request.urlopen(request, timeout=30) as response:
            rows = json.loads(response.read().decode("utf-8"))
        if not rows:
            break
        for issue in rows:
            if "pull_request" in issue:
                continue
            title = str(issue.get("title", ""))
            body = str(issue.get("body", ""))
            if any(term.casefold() in (title + "\n" + body).casefold() for term in ISSUE_PATTERNS):
                matches.append({"number": issue["number"], "title": title, "url": issue["html_url"]})
        if len(rows) < 100:
            break
        page += 1
    return matches

def audit(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    checks: list[dict[str, Any]] = []
    active = sorted((root / ".github/workflows").glob("*.yml")) + sorted((root / ".github/workflows").glob("*.yaml"))
    model_hits = [p.relative_to(root).as_posix() for p in active if any(x in _read(p) for x in FORBIDDEN_WORKFLOW_PATTERNS[:5])]
    checks.append(check("active_rl_model_daily_research_workflows_zero", not model_hits, {"count": len(model_hits), "paths": model_hits}))
    active_my_index = [p.relative_to(root).as_posix() for p in active if FORBIDDEN_WORKFLOW_PATTERNS[5] in _read(p)]
    checks.append(check("active_my_index_arguments_zero", not active_my_index, {"count": len(active_my_index), "paths": active_my_index}))

    issue_hits = _open_research_issues()
    checks.append(check("open_rl_research_issues_zero", not issue_hits, {"count": len(issue_hits), "issues": issue_hits}))

    downstream_path = root / "horse-racing/jrdb/src/audit_rl_retirement_downstream_dependencies.py"
    spec = importlib.util.spec_from_file_location("rl_retirement_downstream", downstream_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load permanent T3 downstream audit")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    downstream = module.audit(root)
    checks.append(check("t3_downstream_audit_pass", downstream.get("status") == "PASS", downstream))

    inventory_path = root / "horse-racing/jrdb/docs/RL_Retired_Asset_Inventory_20261002.md"
    inv = _read(inventory_path)
    missing_frozen = [p for p in FROZEN_FILES if not (root / p).is_file()]
    frozen_markers_missing = []
    for rel in FROZEN_FILES:
        path = root / rel
        if path.suffix == ".json" or rel.endswith(".sql"):
            continue
        text = _read(path)
        marker = "FROZEN_REPRO_ONLY" if "/tests/" in rel else "RETIRED — frozen historical implementation."
        if marker not in text:
            frozen_markers_missing.append(rel)
    checks.append(check("frozen_asset_inventory_complete", not missing_frozen and not frozen_markers_missing and "T4_ASSET_FREEZE = PASS" in inv, {
        "frozen_asset_count": len(FROZEN_FILES), "missing": missing_frozen, "missing_markers": frozen_markers_missing
    }))

    config_files = (
        "horse-racing/jrdb/config/training_edge_v0_2_calibration.json",
        "horse-racing/jrdb/config/training_edge_v0_2_runtime_fingerprint.json",
        "horse-racing/jrdb/config/training_edge_v0_2_runtime_versions.json",
    )
    config_readme = _read(root / "horse-racing/jrdb/config/README_training_edge_v0_2_runtime.md")
    checks.append(check("rl_config_frozen_and_pending_marker_closed", all((root / p).is_file() for p in config_files) and "Retirement status" in config_readme and "stale historical pre-freeze evidence" in config_readme, {"config_count": len(config_files)}))

    shared_texts = {p: _read(root / p) for p in SHARED_WORKFLOWS}
    shared_missing = [p for p,t in shared_texts.items() if "ACTIVE_SHARED_INFRA" not in t]
    shared_rl_hits = [p for p,t in shared_texts.items() if any(x in t for x in FORBIDDEN_WORKFLOW_PATTERNS[:5])]
    preparer = _read(root / "horse-racing/jrdb/src/prepare_rl_t_historical_warehouse_inputs.py")
    checks.append(check("shared_infrastructure_active_and_unambiguous", not shared_missing and not shared_rl_hits and "ACTIVE_SHARED_INFRA" in preparer and all((root/p).is_file() for p in INFRA_PATHS), {
        "active_shared_workflow_count": len(shared_texts), "missing_role_markers": shared_missing, "rl_generation_hits": shared_rl_hits,
        "infrastructure_paths_present": sum((root/p).is_file() for p in INFRA_PATHS), "infrastructure_path_count": len(INFRA_PATHS)
    }))

    status_paths = (
        "horse-racing/jrdb/.gpt/HANDOFF.md",
        "horse-racing/jrdb/.gpt/MIGRATION_STATUS.md",
        "horse-racing/jrdb/.gpt/CONTEXT.md",
        "horse-racing/jrdb/.gpt/WORKFLOW.md",
    )
    status_text = {p: _read(root / p) for p in status_paths}
    missing_status = [p for p,t in status_text.items() if "RL retirement T5" not in t and "RL retirement T5 infrastructure" not in t]
    checks.append(check("status_docs_updated_through_t5", not missing_status, {"missing": missing_status}))

    failures = [c for c in checks if not c["pass"]]
    try:
        commit = subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
    except Exception:
        commit = None
    return {
        "audit": "rl_retirement_final_v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_commit": commit,
        "status": "PASS" if not failures else "FAIL",
        "active_workflow_count": len(active),
        "summary": {
            "ACTIVE_RL_MODEL_WORKFLOW_COUNT": len(model_hits),
            "ACTIVE_RL_DAILY_WORKFLOW_COUNT": len(model_hits),
            "ACTIVE_RL_RESEARCH_WORKFLOW_COUNT": len(model_hits),
            "OPEN_RL_RESEARCH_ISSUE_COUNT": len(issue_hits),
            "RACENOTE_RL_REQUIRED": False if downstream.get("status") == "PASS" else None,
            "NEWSPAPER_RL_REQUIRED": False if downstream.get("status") == "PASS" else None,
            "EDGEDB_RL_REQUIRED": False if downstream.get("status") == "PASS" else None,
            "PWA_RL_REQUIRED": False if downstream.get("status") == "PASS" else None,
            "ACTIVE_MY_INDEX_ARGUMENT_COUNT": len(active_my_index),
            "RL_ABSENCE_FAILURE_PATH_COUNT": 0 if downstream.get("status") == "PASS" else None,
            "RL_SOURCE_ROLE": "FROZEN_REPRO_ONLY",
            "RL_CONFIG_ROLE": "FROZEN_REPRO_ONLY",
            "RL_TEST_ROLE": "FROZEN_REPRO_ONLY",
            "TRAINING_RESEARCH_ROLE": "FROZEN_RESEARCH_ASSET",
            "SHARED_WAREHOUSE_INFRA_ACTIVE": not shared_missing,
            "SHARED_INDEX_BASE_ACTIVE": not shared_missing,
            "RECORD_HASH_COMPAT_ACTIVE": not shared_missing,
        },
        "checks": checks,
        "failure_count": len(failures),
        "failures": failures,
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.root)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if result["status"] != "PASS":
        raise SystemExit(2)

if __name__ == "__main__":
    main()
