#!/usr/bin/env python3
"""Audit Stage 2b Parquet results against the frozen 2026-09-11 historical evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

MODELS = ("M0", "M1", "M2", "M3", "M4")
TEST_YEARS = tuple(str(year) for year in range(2018, 2024))

TOLERANCE = {
    "pooled_spearman": 5e-5,
    "pooled_rmse": 5e-7,
    "top_bottom_mean_spread": 1e-4,
    "yearly_spearman": 5e-5,
}

BASELINE = {
    "source": {
        "date": "2026-09-11",
        "issue": 846,
        "run_id": 34507502943,
        "artifact_id": 10165030176,
        "artifact_digest": "sha256:3e1bd66f1b12d873ba61d7a363d7682f2958b68163de82c10d6a1eccc19b61cc",
        "frozen_analyzer_source_sha": "58797eddbe5d04d55a7de83d8f8473a4fd7c06cb",
    },
    "source_rows": 686096,
    "source_min_year": 2010,
    "source_max_year": 2023,
    "source_duplicate_keys": 0,
    "population": {
        "eligible_2013_2023": 214833,
        "oot_test_2018_2023": 112766,
        "test_year_counts": {
            "2018": 19012,
            "2019": 17322,
            "2020": 19045,
            "2021": 18975,
            "2022": 18108,
            "2023": 20304,
        },
    },
    "holdout_guard": {
        "max_selected_year": 2023,
        "selected_2024_2025_rows": 0,
    },
    "pooled": {
        "M0": {"spearman": 0.19902771693410864, "rmse": 0.08692224108108608, "top_bottom_mean_spread": 0.05431136349147435},
        "M1": {"spearman": 0.21654642478725783, "rmse": 0.08666240371995754, "top_bottom_mean_spread": 0.05895927207839491},
        "M2": {"spearman": 0.19912953448890194, "rmse": 0.0869204533066393, "top_bottom_mean_spread": 0.05455107815065491},
        "M3": {"spearman": 0.21680320187285398, "rmse": 0.08665762619253241, "top_bottom_mean_spread": 0.05959080425693002},
        "M4": {"spearman": 0.21682023064734518, "rmse": 0.08665781290748024, "top_bottom_mean_spread": 0.05880572644432597},
    },
    "yearly_spearman": {
        "M0": {"2018": 0.20978846968815254, "2019": 0.1853303674105251, "2020": 0.2032802113527943, "2021": 0.18369556490030128, "2022": 0.2091246919062997, "2023": 0.20245611439356684},
        "M1": {"2018": 0.22247405872590484, "2019": 0.20150271466451294, "2020": 0.22604312102954036, "2021": 0.20353838596768126, "2022": 0.23161231750739233, "2023": 0.21411344873595162},
        "M2": {"2018": 0.209447631607633, "2019": 0.1851675122468908, "2020": 0.20344676865472808, "2021": 0.18391360488717648, "2022": 0.20922836005116657, "2023": 0.20299795428241152},
        "M3": {"2018": 0.22246406060947568, "2019": 0.20137574802848998, "2020": 0.22636797415642207, "2021": 0.20388327289360011, "2022": 0.2320725038348364, "2023": 0.21467999798635076},
        "M4": {"2018": 0.22258086487381123, "2019": 0.2012877229333735, "2020": 0.2262459552064811, "2021": 0.20376235171335083, "2022": 0.23268834232060384, "2023": 0.21433442502081693},
    },
    "classification": {
        "M1": "B_CORE_CANDIDATE",
        "M2": "B_AUXILIARY_ONLY",
        "M3": "B_CORE_CANDIDATE",
        "M4": "B_CORE_CANDIDATE",
    },
    "named_pattern_identity_count_sha256": "58e2c7b90bbda5f837d64aeaa2c9762fa3adf579a3168c89029e8cf812b535e0",
}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def _named_pattern_digest(report: dict[str, Any]) -> str:
    diagnostics = report.get("named_pattern_diagnostics")
    if not isinstance(diagnostics, dict):
        raise RuntimeError("named_pattern_diagnostics missing")
    ignored = {
        "discovery_relative_effect",
        "discovery_positive_year_share",
        "validation_relative_effect",
        "validation_positive_year_share",
    }
    compact: dict[str, list[dict[str, Any]]] = {}
    for family, rows in diagnostics.items():
        if not isinstance(rows, list):
            raise RuntimeError(f"named pattern family is not a list: {family}")
        compact[family] = [
            {key: value for key, value in row.items() if key not in ignored}
            for row in rows
        ]
    payload = json.dumps(
        compact, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _numeric_check(
    checks: list[dict[str, Any]],
    label: str,
    actual: float,
    expected: float,
    tolerance: float,
) -> None:
    delta = abs(float(actual) - float(expected))
    checks.append({
        "name": label,
        "pass": delta <= tolerance,
        "actual": actual,
        "expected": expected,
        "absolute_delta": delta,
        "tolerance": tolerance,
    })


def audit(result: dict[str, Any], resolver: dict[str, Any] | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    source = result.get("source_audit") or {}
    population = result.get("population") or {}
    holdout = result.get("holdout_guard") or {}
    metrics = result.get("metrics") or {}
    pooled = metrics.get("pooled") or {}
    yearly = metrics.get("yearly") or {}
    decisions = result.get("incremental_decision") or {}

    source_rows = resolver.get("rows") if resolver else source.get("source_table_rows")
    source_min_year = resolver.get("min_year") if resolver else source.get("selected_min_year")
    source_max_year = resolver.get("max_year") if resolver else source.get("selected_max_year")
    duplicate_keys = resolver.get("duplicate_keys") if resolver else None

    for label, actual, expected in (
        ("source_rows", source_rows, BASELINE["source_rows"]),
        ("source_min_year", source_min_year, BASELINE["source_min_year"]),
        ("source_max_year", source_max_year, BASELINE["source_max_year"]),
        ("holdout_max_selected_year", holdout.get("max_selected_year"), BASELINE["holdout_guard"]["max_selected_year"]),
        ("holdout_selected_2024_2025_rows", holdout.get("selected_2024_2025_rows"), BASELINE["holdout_guard"]["selected_2024_2025_rows"]),
    ):
        checks.append({"name": label, "pass": actual == expected, "actual": actual, "expected": expected})

    if resolver is not None:
        checks.append({
            "name": "source_duplicate_keys",
            "pass": duplicate_keys == BASELINE["source_duplicate_keys"],
            "actual": duplicate_keys,
            "expected": BASELINE["source_duplicate_keys"],
        })

    checks.append({
        "name": "population",
        "pass": population == BASELINE["population"],
        "actual": population,
        "expected": BASELINE["population"],
    })

    for model in MODELS:
        current = pooled.get(model) or {}
        baseline = BASELINE["pooled"][model]
        _numeric_check(checks, f"{model}.pooled.spearman", current.get("spearman"), baseline["spearman"], TOLERANCE["pooled_spearman"])
        _numeric_check(checks, f"{model}.pooled.rmse", current.get("rmse"), baseline["rmse"], TOLERANCE["pooled_rmse"])
        spread = (current.get("top_minus_bottom") or {}).get("mean_delta")
        _numeric_check(checks, f"{model}.pooled.top_bottom_mean_spread", spread, baseline["top_bottom_mean_spread"], TOLERANCE["top_bottom_mean_spread"])

        for year in TEST_YEARS:
            actual = ((yearly.get(model) or {}).get(year) or {}).get("spearman")
            expected = BASELINE["yearly_spearman"][model][year]
            _numeric_check(checks, f"{model}.{year}.spearman", actual, expected, TOLERANCE["yearly_spearman"])

    for model, expected in BASELINE["classification"].items():
        actual = (decisions.get(model) or {}).get("classification")
        checks.append({
            "name": f"{model}.classification",
            "pass": actual == expected,
            "actual": actual,
            "expected": expected,
        })

    named_digest = _named_pattern_digest(result)
    checks.append({
        "name": "named_pattern_identity_count_sha256",
        "pass": named_digest == BASELINE["named_pattern_identity_count_sha256"],
        "actual": named_digest,
        "expected": BASELINE["named_pattern_identity_count_sha256"],
    })

    failures = [item for item in checks if not item["pass"]]
    return {
        "status": "PASS" if not failures else "FAIL",
        "audit_contract": "stage2b_historical_nonregression_v1",
        "baseline": BASELINE["source"],
        "tolerance": TOLERANCE,
        "checks": checks,
        "failure_count": len(failures),
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--resolver", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = audit(
        _read_json(args.result),
        None if args.resolver is None else _read_json(args.resolver),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["status"],
        "failure_count": report["failure_count"],
        "tolerance": report["tolerance"],
    }, ensure_ascii=False))
    if report["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
