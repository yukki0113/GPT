#!/usr/bin/env python3
"""Finalize existing-horse Ability comparison output without changing model metrics.

The model comparator intentionally produces the full frozen development evidence.
This post-processing step only makes candidate selection fail closed when an annual
primary metric is missing or non-finite, then rebuilds the compact selection views.
It does not refit a model, alter the candidate grid, or inspect 2024-2025 labels.
"""
from __future__ import annotations

import argparse
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np

FAMILIES = ("a0", "ridge", "elastic_net")


def _is_finite_number(value: Any) -> bool:
    """Return True only for finite int/float metric values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def _selection_sort_key(candidate: dict[str, Any]) -> float:
    """Return a fail-closed sorting key for candidate selection."""
    value = candidate.get("mean_primary")
    if not _is_finite_number(value):
        return -math.inf
    return float(value)


def _sanitize_candidate(candidate: dict[str, Any], development_years: list[int]) -> dict[str, Any]:
    """Mark a candidate invalid if any required annual primary is non-finite."""
    result = deepcopy(candidate)
    annual = result.get("annual", [])
    primary_by_year = {int(row["year"]): row.get("primary") for row in annual if "year" in row}
    invalid_years = [year for year in development_years if not _is_finite_number(primary_by_year.get(year))]

    if invalid_years:
        result["selection_status"] = "INVALID_NONFINITE_ANNUAL_PRIMARY"
        result["invalid_primary_years"] = invalid_years
        result["mean_primary"] = None
        result["primary_sd"] = None
        return result

    primary = [float(primary_by_year[year]) for year in development_years]
    result["selection_status"] = "VALID"
    result["invalid_primary_years"] = []
    result["mean_primary"] = float(np.mean(primary))
    result["primary_sd"] = float(np.std(primary))
    return result


def _paired_delta(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Build annual primary deltas against the frozen best A0 baseline."""
    baseline_by_year = {int(row["year"]): row.get("primary") for row in baseline["annual"]}
    deltas: list[dict[str, Any]] = []
    for row in candidate["annual"]:
        year = int(row["year"])
        candidate_primary = row.get("primary")
        baseline_primary = baseline_by_year.get(year)
        if not _is_finite_number(candidate_primary) or not _is_finite_number(baseline_primary):
            delta = None
        else:
            delta = float(candidate_primary) - float(baseline_primary)
        deltas.append({"year": year, "delta_primary": delta})
    return {"candidate": candidate["candidate"], "annual_delta_vs_best_a0": deltas}


def finalize(report: dict[str, Any]) -> dict[str, Any]:
    """Return a selection-safe copy of one frozen development comparison report."""
    result = deepcopy(report)
    development_years = [int(year) for year in result.get("development_years", [])]
    if development_years != list(range(2013, 2024)):
        raise ValueError("unexpected Ability development years")
    if result.get("holdout_touched") is not False:
        raise ValueError("development report indicates holdout access")
    if result.get("2024_2025_predictive_metrics_inspected") is not False:
        raise ValueError("development report indicates 2024-2025 predictive metric access")

    validity: dict[str, dict[str, int]] = {}
    for family in FAMILIES:
        candidates = [_sanitize_candidate(candidate, development_years) for candidate in result.get(family, [])]
        candidates.sort(key=_selection_sort_key, reverse=True)
        result[family] = candidates
        valid_count = sum(1 for candidate in candidates if candidate.get("selection_status") == "VALID")
        validity[family] = {
            "total": len(candidates),
            "valid": valid_count,
            "invalid": len(candidates) - valid_count,
        }

    best: dict[str, dict[str, Any] | None] = {}
    for family in FAMILIES:
        best[family] = next(
            (candidate for candidate in result[family] if candidate.get("selection_status") == "VALID"),
            None,
        )

    result["best_a0"] = best["a0"]
    result["best_ridge"] = best["ridge"]
    result["best_elastic_net"] = best["elastic_net"]
    result["candidate_validity"] = validity

    selectable = [
        candidate
        for family in FAMILIES
        for candidate in result[family]
        if candidate.get("selection_status") == "VALID"
    ]
    selectable.sort(key=_selection_sort_key, reverse=True)
    result["top_candidates"] = selectable[:20]

    if result["best_a0"] is None:
        result["paired_vs_best_a0"] = []
        result["status"] = "FAIL"
        result["selection_failure_reason"] = "NO_VALID_A0_CANDIDATE"
        return result

    paired = []
    for family_key in ("best_ridge", "best_elastic_net"):
        candidate = result[family_key]
        if candidate is not None:
            paired.append(_paired_delta(candidate, result["best_a0"]))
    result["paired_vs_best_a0"] = paired

    if result["best_ridge"] is None or result["best_elastic_net"] is None:
        result["status"] = "FAIL"
        result["selection_failure_reason"] = "NO_VALID_REGULARIZED_CANDIDATE"
    else:
        result["selection_failure_reason"] = None
    return result


def main() -> int:
    """Finalize one JSON report in place or at an explicit output path."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    finalized = finalize(report)
    destination = args.out or args.report
    destination.write_text(json.dumps(finalized, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": finalized["status"],
                "candidate_validity": finalized["candidate_validity"],
                "best_a0": finalized["best_a0"]["candidate"] if finalized["best_a0"] else None,
                "best_ridge": finalized["best_ridge"]["candidate"] if finalized["best_ridge"] else None,
                "best_elastic_net": finalized["best_elastic_net"]["candidate"] if finalized["best_elastic_net"] else None,
            },
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    return 0 if finalized["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
