#!/usr/bin/env python3
"""Fingerprint the frozen Training Edge v0.2 fit population and predictions.

This is an operational reproducibility guard, not a model-selection step.  It
uses only the preregistered 2013-2025 fit population with 2010-2012 warmup and
never consumes 2026 outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from evaluate_training_edge_v0_2_oot import (
    SOURCE_COLUMNS,
    TRAIN_FROM,
    TRAIN_TO,
    _eligible,
    _materialize_b,
    _materialize_time_aware,
)
from training_edge_v0_2_core import (
    CAB_CATEGORICAL,
    CAB_NUMERIC,
    C_CATEGORICAL,
    C_NUMERIC,
    VERSION as CORE_VERSION,
    build_c_model,
    build_cab_model,
)

VERSION = "0.1.0"
SEMANTIC_COLUMNS = (
    "race_date",
    "race_key",
    "horse_no",
    "prior_runperf_count",
    "prior_comparable_workout_count",
    *CAB_NUMERIC,
    *CAB_CATEGORICAL,
    "performance_delta",
)
PACKAGE_NAMES = (
    "numpy",
    "pandas",
    "scipy",
    "scikit-learn",
)
PREDICTION_DECIMALS = 12


def _load_history(path: Path) -> pd.DataFrame:
    """Load the complete 2010-2025 projected input in chronological order."""
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        available = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(training_edge_input)")
        }
        missing = [column for column in SOURCE_COLUMNS if column not in available]
        if missing:
            raise ValueError(f"required v0.2 input columns are missing: {missing}")
        columns = ",".join(SOURCE_COLUMNS)
        frame = pd.read_sql_query(
            f"SELECT {columns} FROM training_edge_input "
            "WHERE year BETWEEN 2010 AND 2025 "
            "ORDER BY race_date,race_key,horse_no",
            connection,
        )
    finally:
        connection.close()
    if frame.empty:
        raise ValueError("Training Edge runtime history is empty")
    years = sorted(int(value) for value in frame["year"].dropna().unique())
    if years[0] != 2010 or years[-1] != 2025:
        raise ValueError(f"runtime history must span 2010..2025, got {years[0]}..{years[-1]}")
    return frame


def _canonical_number(value: object) -> str | None:
    """Convert one numeric semantic value to a platform-stable hexadecimal float."""
    if value is None or pd.isna(value):
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite runtime semantic number: {value!r}")
    return number.hex()


def _semantic_hash(training: pd.DataFrame) -> str:
    """Hash fit keys, eligibility state, model inputs and target deterministically."""
    digest = hashlib.sha256()
    numeric_columns = set(CAB_NUMERIC)
    numeric_columns.update(
        {
            "horse_no",
            "prior_runperf_count",
            "prior_comparable_workout_count",
            "performance_delta",
        }
    )
    for row in training.loc[:, list(SEMANTIC_COLUMNS)].itertuples(index=False, name=None):
        normalized: list[Any] = []
        for column, value in zip(SEMANTIC_COLUMNS, row, strict=True):
            if column in numeric_columns:
                normalized.append(_canonical_number(value))
            else:
                normalized.append(None if value is None or pd.isna(value) else str(value))
        payload = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
        digest.update(payload.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _prediction_hash(values: np.ndarray) -> str:
    """Hash predictions after stable 12-decimal normalization."""
    normalized = np.round(np.asarray(values, dtype=np.float64), PREDICTION_DECIMALS)
    lines = "\n".join(f"{float(value):.{PREDICTION_DECIMALS}f}" for value in normalized)
    return hashlib.sha256((lines + "\n").encode("ascii")).hexdigest()


def _package_versions() -> dict[str, str]:
    """Return versions of numerical packages that can affect fitted predictions."""
    return {name: importlib.metadata.version(name) for name in PACKAGE_NAMES}


def fingerprint(input_db: Path) -> dict[str, Any]:
    """Build the operational v0.2 fit/runtime fingerprint from 2010-2025 only."""
    frame = _load_history(input_db)
    frame = _materialize_time_aware(frame)
    frame = _materialize_b(frame)
    training = _eligible(frame, TRAIN_FROM, TRAIN_TO)
    training = training.sort_values(
        ["race_date", "race_key", "horse_no"], kind="stable"
    ).reset_index(drop=True)
    if training.empty:
        raise ValueError("frozen 2013-2025 fit population is empty")

    c_model = build_c_model()
    cab_model = build_cab_model()
    target = training["performance_delta"]
    c_model.fit(training, target)
    cab_model.fit(training, target)
    c_prediction = np.asarray(c_model.predict(training), dtype=float)
    cab_prediction = np.asarray(cab_model.predict(training), dtype=float)

    return {
        "schema": "training-edge-v0.2-runtime-fingerprint",
        "version": VERSION,
        "core_version": CORE_VERSION,
        "history_period": "2010-2025",
        "training_period": f"{TRAIN_FROM}-{TRAIN_TO}",
        "training_eligible_n": int(len(training)),
        "training_date_min": str(training["race_date"].min()),
        "training_date_max": str(training["race_date"].max()),
        "semantic_columns": list(SEMANTIC_COLUMNS),
        "training_semantic_sha256": _semantic_hash(training),
        "prediction_normalization_decimals": PREDICTION_DECIMALS,
        "c_training_prediction_sha256": _prediction_hash(c_prediction),
        "cab_training_prediction_sha256": _prediction_hash(cab_prediction),
        "runtime_packages": _package_versions(),
        "guard": {
            "max_input_year": int(frame["year"].max()),
            "max_fit_year": int(training["year"].max()),
            "contains_2026_rows": bool((frame["year"] >= 2026).any()),
        },
    }


def validate_fingerprint(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    """Fail closed when an operational fit/runtime fingerprint drifts."""
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
    mismatches: list[str] = []
    for field in fields:
        if actual.get(field) != expected.get(field):
            mismatches.append(field)
    if mismatches:
        raise ValueError("Training Edge v0.2 runtime fingerprint mismatch: " + ",".join(mismatches))


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected", type=Path)
    args = parser.parse_args()

    result = fingerprint(args.input_db)
    if args.expected is not None:
        expected = json.loads(args.expected.read_text(encoding="utf-8"))
        validate_fingerprint(result, expected)
        result["expected_validation"] = "PASS"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
