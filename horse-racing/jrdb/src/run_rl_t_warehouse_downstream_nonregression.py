#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the RL-T Historical Warehouse downstream non-regression gate.

This runner assumes the accepted 2010-2025 Warehouse has already passed the
Index Base dual-read gate. It rebuilds the scientific downstream chain from
both the legacy Raw Index Base route and the Warehouse compatibility route,
then compares the resulting relations and the frozen RL-T v0.2 fingerprint.

The 2026 PACI/Raw route is intentionally out of scope and remains unchanged.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

YEARS = tuple(range(2010, 2026))


def _run(command: list[str], environment: dict[str, str], log_handle: Any) -> None:
    """Run one deterministic stage and fail immediately on error."""
    log_handle.write("$ " + " ".join(command) + "\n")
    log_handle.flush()
    subprocess.run(
        command,
        check=True,
        env=environment,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _asset_args(values: list[str]) -> list[str]:
    """Expand repeatable FAMILY=PATH arguments for the Warehouse builder."""
    result: list[str] = []
    for value in values:
        result.extend(["--asset-root", value])
    return result


def _pipeline(
    label: str,
    index_db: Path,
    root: Path,
    source_git_commit: str,
    environment: dict[str, str],
    log_handle: Any,
) -> dict[str, Path]:
    """Build RunPerf, Official RunPerf, Training Research, Stage1b and fingerprint."""
    runperf = root / f"{label}_runperf.sqlite"
    official = root / f"{label}_official.sqlite"
    training = root / f"{label}_training_research.sqlite"
    training_result = root / f"{label}_training_research_result.json"
    stage1b = root / f"{label}_stage1b.json"
    stage1b_md = root / f"{label}_stage1b.md"
    edge_input = root / f"{label}_training_edge_input.sqlite"
    edge_input_result = root / f"{label}_training_edge_input_result.json"
    fingerprint = root / f"{label}_fingerprint.json"

    _run(
        [
            "python",
            "horse-racing/jrdb/src/build_jrdb_runperf_features.py",
            "--index-db",
            str(index_db),
            "--out",
            str(runperf),
            "--methods",
            "EXPANDING",
        ],
        environment,
        log_handle,
    )
    _run(
        [
            "python",
            "horse-racing/jrdb/src/build_jrdb_official_runperf.py",
            "--runperf-db",
            str(runperf),
            "--out",
            str(official),
        ],
        environment,
        log_handle,
    )
    _run(
        [
            "python",
            "horse-racing/jrdb/src/build_jrdb_training_research.py",
            "--index-db",
            str(index_db),
            "--official-runperf-db",
            str(official),
            "--out",
            str(training),
            "--source-git-commit",
            source_git_commit,
            "--result-json",
            str(training_result),
        ],
        environment,
        log_handle,
    )
    _run(
        [
            "python",
            "horse-racing/jrdb/src/analyze_jrdb_training_stage1b.py",
            "--db",
            str(training),
            "--input-format",
            "sqlite",
            "--out-json",
            str(stage1b),
            "--out-md",
            str(stage1b_md),
        ],
        environment,
        log_handle,
    )
    _run(
        [
            "python",
            "horse-racing/jrdb/src/project_training_edge_v0_2_input.py",
            "--index-db",
            str(index_db),
            "--official-db",
            str(official),
            "--out",
            str(edge_input),
            "--from-year",
            "2010",
            "--to-year",
            "2025",
            "--source-git-commit",
            source_git_commit,
            "--result-json",
            str(edge_input_result),
        ],
        environment,
        log_handle,
    )
    _run(
        [
            "python",
            "horse-racing/jrdb/src/fingerprint_training_edge_v0_2_runtime.py",
            "--input-db",
            str(edge_input),
            "--out",
            str(fingerprint),
        ],
        environment,
        log_handle,
    )

    return {
        "runperf": runperf,
        "official": official,
        "training": training,
        "stage1b": stage1b,
        "edge_input": edge_input,
        "fingerprint": fingerprint,
    }


def _expected_fingerprint_compare(actual_path: Path, expected_path: Path) -> dict[str, Any]:
    """Compare one produced fingerprint with the frozen operational contract."""
    fields = (
        "core_version",
        "training_period",
        "training_eligible_n",
        "training_semantic_sha256",
        "prediction_normalization_decimals",
        "c_training_prediction_sha256",
        "cab_training_prediction_sha256",
        "runtime_packages",
    )
    actual = json.loads(actual_path.read_text(encoding="utf-8"))
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    differences = {
        field: {"actual": actual.get(field), "expected": expected.get(field)}
        for field in fields
        if actual.get(field) != expected.get(field)
    }
    return {
        "pass": not differences,
        "differences": differences,
        "actual": {field: actual.get(field) for field in fields},
    }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--warehouse-manifest", type=Path, required=True)
    parser.add_argument("--asset-root", action="append", required=True)
    parser.add_argument("--record-hash-compat-manifest", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--source-git-commit", required=True)
    parser.add_argument(
        "--expected-fingerprint",
        type=Path,
        default=Path("horse-racing/jrdb/config/training_edge_v0_2_runtime_fingerprint.json"),
    )
    parser.add_argument("--result-json", type=Path, required=True)
    args = parser.parse_args()

    args.work_root.mkdir(parents=True, exist_ok=True)
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    log_path = args.work_root / "downstream_nonregression.log"

    environment = dict(os.environ)
    existing_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        "tools/data-storage:horse-racing/jrdb/src:" + existing_pythonpath
    )

    raw_index = args.work_root / "raw_index_2010_2025.sqlite"
    warehouse_index = args.work_root / "warehouse_index_2010_2025.sqlite"
    audit_path = args.work_root / "downstream_nonregression.json"

    with log_path.open("w", encoding="utf-8") as log_handle:
        _run(
            [
                "python",
                "horse-racing/jrdb/src/build_jrdb_index_base_from_raw.py",
                "--raw-root",
                str(args.raw_root),
                "--years",
                *[str(year) for year in YEARS],
                "--db",
                str(raw_index),
                "--no-archive-hash",
            ],
            environment,
            log_handle,
        )

        warehouse_command = [
            "python",
            "horse-racing/jrdb/src/build_jrdb_index_base_from_warehouse.py",
            "--warehouse-manifest",
            str(args.warehouse_manifest),
            *_asset_args(args.asset_root),
            "--record-hash-compat-manifest",
            str(args.record_hash_compat_manifest),
            "--years",
            *[str(year) for year in YEARS],
            "--db",
            str(warehouse_index),
        ]
        _run(warehouse_command, environment, log_handle)

        raw_outputs = _pipeline(
            "raw",
            raw_index,
            args.work_root,
            args.source_git_commit,
            environment,
            log_handle,
        )
        warehouse_outputs = _pipeline(
            "warehouse",
            warehouse_index,
            args.work_root,
            args.source_git_commit,
            environment,
            log_handle,
        )

        _run(
            [
                "python",
                "horse-racing/jrdb/src/audit_rl_t_warehouse_downstream_nonregression.py",
                "--raw-runperf",
                str(raw_outputs["runperf"]),
                "--warehouse-runperf",
                str(warehouse_outputs["runperf"]),
                "--raw-official",
                str(raw_outputs["official"]),
                "--warehouse-official",
                str(warehouse_outputs["official"]),
                "--raw-training",
                str(raw_outputs["training"]),
                "--warehouse-training",
                str(warehouse_outputs["training"]),
                "--raw-edge-input",
                str(raw_outputs["edge_input"]),
                "--warehouse-edge-input",
                str(warehouse_outputs["edge_input"]),
                "--raw-stage1b",
                str(raw_outputs["stage1b"]),
                "--warehouse-stage1b",
                str(warehouse_outputs["stage1b"]),
                "--raw-fingerprint",
                str(raw_outputs["fingerprint"]),
                "--warehouse-fingerprint",
                str(warehouse_outputs["fingerprint"]),
                "--out",
                str(audit_path),
            ],
            environment,
            log_handle,
        )

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    raw_expected = _expected_fingerprint_compare(
        raw_outputs["fingerprint"],
        args.expected_fingerprint,
    )
    warehouse_expected = _expected_fingerprint_compare(
        warehouse_outputs["fingerprint"],
        args.expected_fingerprint,
    )
    overall_pass = (
        audit.get("status") == "PASS"
        and raw_expected["pass"]
        and warehouse_expected["pass"]
    )
    result = {
        "status": "PASS" if overall_pass else "FAIL",
        "years": [2010, 2025],
        "source_mode_raw": "legacy_raw_audit_only",
        "source_mode_warehouse": "accepted_historical_warehouse",
        "warehouse_generation_id": "jrdb_normalized_warehouse_v1_2010_2025_g20260921",
        "record_hash_compatibility": "legacy_body_sha256_sidecar",
        "downstream_audit": audit,
        "raw_expected_fingerprint": raw_expected,
        "warehouse_expected_fingerprint": warehouse_expected,
        "expected_fingerprint": str(args.expected_fingerprint),
        "log": str(log_path),
    }
    args.result_json.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
