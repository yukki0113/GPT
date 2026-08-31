#!/usr/bin/env python3
"""Fit one fitted RunPerf coefficient snapshot through a completed source year.

The tool reads only the RunPerf candidate database through ``asof_through_year`` and
creates coefficients for ``target_year = asof_through_year + 1``. It does not read or
evaluate target-year outcomes and therefore can freeze a locked-holdout scoring
snapshot before the holdout is opened.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from compare_jrdb_runperf_candidates import (
    TIME_VARIANTS,
    WARMUP_START_YEAR,
    _load_year_data,
    _solve_ols,
    _year_normal_equations,
)

VERSION = "0.1.0"
FITTED_FAMILY_FEATURES: dict[str, tuple[str, ...]] = {
    "T1": ("TIME", "prev_margin_score"),
    "T2": ("TIME", "prev_weight_relative_kg"),
    "T3": ("TIME", "prev_margin_score", "prev_weight_relative_kg"),
}


def fit_snapshot(
    database_path: Path,
    family: str,
    baseline_method: str,
    time_variant: str,
    asof_through_year: int,
    target_year: int,
) -> dict[str, Any]:
    """Fit a single coefficient snapshot using only target pairs through the as-of year."""
    normalized_family = family.upper()
    normalized_method = baseline_method.upper()
    normalized_variant = time_variant.upper()
    if normalized_family not in FITTED_FAMILY_FEATURES:
        raise ValueError("family must be one of T1, T2, T3")
    if normalized_variant not in TIME_VARIANTS:
        raise ValueError(f"unknown time variant: {normalized_variant}")
    if target_year != asof_through_year + 1:
        raise ValueError("target_year must equal asof_through_year + 1")
    if asof_through_year < WARMUP_START_YEAR:
        raise ValueError("asof_through_year is earlier than the supported history")

    time_feature = TIME_VARIANTS[normalized_variant]
    feature_tokens = FITTED_FAMILY_FEATURES[normalized_family]
    feature_names = [time_feature if token == "TIME" else token for token in feature_tokens]

    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        year_data = _load_year_data(connection, normalized_method, asof_through_year)
    finally:
        connection.close()

    width = len(feature_names) + 1
    cumulative_xtx: NDArray[np.float64] = np.zeros((width, width), dtype=np.float64)
    cumulative_xty: NDArray[np.float64] = np.zeros(width, dtype=np.float64)
    training_pair_count = 0
    pair_count_by_target_year: dict[str, int] = {}
    for year in range(WARMUP_START_YEAR, asof_through_year + 1):
        data = year_data.get(year)
        if data is None:
            pair_count_by_target_year[str(year)] = 0
            continue
        xtx, xty, row_count = _year_normal_equations(data, feature_names)
        cumulative_xtx += xtx
        cumulative_xty += xty
        training_pair_count += row_count
        pair_count_by_target_year[str(year)] = row_count

    if training_pair_count < width:
        raise ValueError("insufficient training pairs for coefficient snapshot")
    beta = _solve_ols(cumulative_xtx, cumulative_xty)
    coefficients = {
        feature_names[index]: float(beta[index + 1])
        for index in range(len(feature_names))
    }
    return {
        "status": "PASS",
        "snapshot_fitter_version": VERSION,
        "candidate": f"{normalized_family}|{normalized_method}|{normalized_variant}",
        "family": normalized_family,
        "baseline_method": normalized_method,
        "time_variant": normalized_variant,
        "target_year": target_year,
        "coefficient_asof_through_year": asof_through_year,
        "holdout_outcomes_read": False,
        "training_target": "next-start finish percentile",
        "training_pair_count": training_pair_count,
        "pair_count_by_target_year": pair_count_by_target_year,
        "intercept": float(beta[0]),
        "coefficients": coefficients,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--family", required=True, choices=sorted(FITTED_FAMILY_FEATURES))
    parser.add_argument("--baseline-method", required=True)
    parser.add_argument("--time-variant", required=True, choices=sorted(TIME_VARIANTS))
    parser.add_argument("--asof-through-year", type=int, required=True)
    parser.add_argument("--target-year", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = fit_snapshot(
        args.db,
        args.family,
        args.baseline_method,
        args.time_variant,
        args.asof_through_year,
        args.target_year,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
