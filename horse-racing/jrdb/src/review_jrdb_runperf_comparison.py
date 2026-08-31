#!/usr/bin/env python3
"""Review one completed RunPerf development comparison without opening holdout data.

This script deliberately limits promotion candidates to the predeclared independent
families B0/B1/T0/T1. T2/T3 are diagnostic until a separate carried-weight effect
study is completed, while J0/J1 remain JRDB benchmarks.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any, Iterable

VERSION = "0.1.0"
INDEPENDENT_ELIGIBLE = {"B0", "B1", "T0", "T1"}
CONDITIONAL_DIAGNOSTIC = {"T2", "T3"}
JRDB_BENCHMARK = {"J0", "J1"}


def _finite(value: Any) -> float | None:
    """Return one finite float or None."""
    if value is None:
        return None
    result = float(value)
    if not math.isfinite(result):
        return None
    return result


def _mean(values: Iterable[float]) -> float | None:
    """Return arithmetic mean or None."""
    materialized = list(values)
    if not materialized:
        return None
    return float(statistics.fmean(materialized))


def _std(values: Iterable[float]) -> float | None:
    """Return population standard deviation or None."""
    materialized = list(values)
    if not materialized:
        return None
    return float(statistics.pstdev(materialized))


def _compact(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return stable fields used in the human adoption review."""
    keys = (
        "candidate",
        "family",
        "baseline_method",
        "time_variant",
        "development_year_count",
        "positive_primary_year_count",
        "mean_primary_rank_score",
        "std_primary_rank_score",
        "mean_same_condition_rank_score",
        "mean_top_pick_win_rate",
        "mean_top_pick_top3_rate",
        "mean_coverage",
    )
    return {key: candidate.get(key) for key in keys}


def _candidate_key(candidate: dict[str, Any]) -> tuple[float, float, float]:
    """Use the same declared ordering as the comparator."""
    primary = _finite(candidate.get("mean_primary_rank_score"))
    same = _finite(candidate.get("mean_same_condition_rank_score"))
    std = _finite(candidate.get("std_primary_rank_score"))
    return (
        primary if primary is not None else -math.inf,
        same if same is not None else -math.inf,
        -std if std is not None else -math.inf,
    )


def _year_map(candidate: dict[str, Any]) -> dict[int, float]:
    """Map test year to primary rank score when finite."""
    result: dict[int, float] = {}
    for row in candidate.get("yearly") or []:
        value = _finite(row.get("primary_rank_score"))
        if value is not None:
            result[int(row["year"])] = value
    return result


def _paired_difference(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Summarize left-right development differences on exactly matched years."""
    left_years = _year_map(left)
    right_years = _year_map(right)
    years = sorted(set(left_years).intersection(right_years))
    rows: list[dict[str, Any]] = []
    differences: list[float] = []
    for year in years:
        difference = left_years[year] - right_years[year]
        differences.append(difference)
        rows.append(
            {
                "year": year,
                "left": left_years[year],
                "right": right_years[year],
                "difference": difference,
            }
        )
    positive = sum(1 for value in differences if value > 0.0)
    negative = sum(1 for value in differences if value < 0.0)
    zero = len(differences) - positive - negative
    return {
        "left": left.get("candidate"),
        "right": right.get("candidate"),
        "year_count": len(differences),
        "positive_year_count": positive,
        "negative_year_count": negative,
        "zero_year_count": zero,
        "mean_difference": _mean(differences),
        "median_difference": float(statistics.median(differences)) if differences else None,
        "std_difference": _std(differences),
        "min_difference": min(differences) if differences else None,
        "max_difference": max(differences) if differences else None,
        "yearly": rows,
    }


def _coefficient_stability(candidate: dict[str, Any]) -> dict[str, Any]:
    """Summarize sign and magnitude stability for fitted T-family coefficients."""
    history = candidate.get("coefficient_history") or []
    feature_values: dict[str, list[tuple[int, float]]] = {}
    for row in history:
        year = int(row["test_year"])
        coefficients = row.get("coefficients") or {}
        for feature, raw_value in coefficients.items():
            value = _finite(raw_value)
            if value is None:
                continue
            feature_values.setdefault(str(feature), []).append((year, value))

    summary: dict[str, Any] = {}
    for feature, pairs in sorted(feature_values.items()):
        pairs.sort()
        values = [value for _, value in pairs]
        signs: list[int] = []
        for value in values:
            sign = 0
            if value > 0.0:
                sign = 1
            elif value < 0.0:
                sign = -1
            signs.append(sign)
        sign_flips = 0
        previous_nonzero: int | None = None
        for sign in signs:
            if sign == 0:
                continue
            if previous_nonzero is not None and sign != previous_nonzero:
                sign_flips += 1
            previous_nonzero = sign
        summary[feature] = {
            "year_count": len(values),
            "positive_count": sum(1 for sign in signs if sign > 0),
            "negative_count": sum(1 for sign in signs if sign < 0),
            "zero_count": sum(1 for sign in signs if sign == 0),
            "adjacent_sign_flip_count": sign_flips,
            "mean": _mean(values),
            "std": _std(values),
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "yearly": [{"year": year, "value": value} for year, value in pairs],
        }
    return summary


def review(comparison: dict[str, Any]) -> dict[str, Any]:
    """Build the predeclared independent-core adoption review."""
    protocol = comparison.get("protocol") or {}
    if comparison.get("status") != "PASS":
        raise ValueError("comparison status must be PASS")
    if bool(protocol.get("holdout_touched")):
        raise ValueError("refusing to review a comparison that touched the locked holdout")
    locked = protocol.get("locked_holdout_years")
    if locked != [2024, 2025]:
        raise ValueError("expected locked holdout years [2024, 2025]")

    all_candidates = comparison.get("all_candidates") or []
    independent = [
        candidate for candidate in all_candidates
        if str(candidate.get("family")) in INDEPENDENT_ELIGIBLE
    ]
    conditional = [
        candidate for candidate in all_candidates
        if str(candidate.get("family")) in CONDITIONAL_DIAGNOSTIC
    ]
    benchmarks = [
        candidate for candidate in all_candidates
        if str(candidate.get("family")) in JRDB_BENCHMARK
    ]
    if not independent:
        raise ValueError("no independent eligible candidates found")

    independent.sort(key=_candidate_key, reverse=True)
    conditional.sort(key=_candidate_key, reverse=True)
    benchmarks.sort(key=_candidate_key, reverse=True)
    best = independent[0]
    runner_up = independent[1] if len(independent) > 1 else None

    family_best: dict[str, dict[str, Any]] = {}
    for candidate in independent:
        family = str(candidate["family"])
        if family not in family_best:
            family_best[family] = candidate

    pairwise: dict[str, Any] = {}
    if runner_up is not None:
        pairwise["best_vs_runner_up"] = _paired_difference(best, runner_up)
    for family in ("B1", "B0"):
        candidate = family_best.get(family)
        if candidate is not None and candidate.get("candidate") != best.get("candidate"):
            pairwise[f"best_vs_{family}"] = _paired_difference(best, candidate)
    if benchmarks:
        pairwise["best_vs_best_jrdb_benchmark"] = _paired_difference(best, benchmarks[0])

    result = {
        "status": "PASS",
        "reviewer_version": VERSION,
        "holdout_touched": False,
        "eligibility": {
            "independent_core": sorted(INDEPENDENT_ELIGIBLE),
            "conditional_diagnostic": sorted(CONDITIONAL_DIAGNOSTIC),
            "jrdb_benchmark_only": sorted(JRDB_BENCHMARK),
        },
        "best_independent_candidate": _compact(best),
        "runner_up_independent_candidate": _compact(runner_up) if runner_up is not None else None,
        "top_independent_candidates": [_compact(candidate) for candidate in independent[:10]],
        "best_by_independent_family": {
            family: _compact(candidate) for family, candidate in family_best.items()
        },
        "best_conditional_diagnostic": _compact(conditional[0]) if conditional else None,
        "best_jrdb_benchmark": _compact(benchmarks[0]) if benchmarks else None,
        "paired_primary_differences": pairwise,
        "best_candidate_coefficient_stability": _coefficient_stability(best),
        "decision_note": (
            "This report does not auto-promote the numeric winner. Review year-paired differences, "
            "coverage, comparable-condition validity, coefficient stability, and complexity before "
            "freezing the provisional RunPerf specification."
        ),
    }
    return result


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    comparison = json.loads(args.comparison.read_text(encoding="utf-8"))
    result = review(comparison)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
