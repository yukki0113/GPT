#!/usr/bin/env python3
"""Score frozen Training Edge v0.2 for one pre-race JRDB day.

The input projection may contain historical settled rows plus the target day's
pre-race rows. Target-day result values are never required and are ignored for
eligibility. The scientific model definition and calibration are imported from
the frozen v0.2 assets; this module only adds an operational daily projection.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from evaluate_training_edge_v0_2_oot import (
    MIN_PRIOR_COMPARABLE_WORKOUT,
    MIN_PRIOR_RUNPERF,
    SOURCE_COLUMNS,
    TRAIN_FROM,
    TRAIN_TO,
    _eligible,
    _materialize_b,
    _materialize_time_aware,
)
from fingerprint_training_edge_v0_2_runtime import (
    fingerprint as build_runtime_fingerprint,
    validate_fingerprint,
)
from training_edge_v0_2_core import (
    VERSION as CORE_VERSION,
    build_c_model,
    build_cab_model,
    load_calibration,
    training_edge_direction,
    training_edge_percentile,
)

VERSION = "0.2.0"
CSV_COLUMNS = (
    "date",
    "venue_code",
    "race_no",
    "horse_no",
    "training_edge_index",
)
DEFAULT_RUNTIME_FINGERPRINT = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "training_edge_v0_2_runtime_fingerprint.json"
)


def _sha256(path: Path) -> str:
    """Return a streaming SHA-256 digest for an input or output file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalize_target_date(value: str) -> str:
    """Normalize YYYYMMDD or YYYY-MM-DD to ISO YYYY-MM-DD."""
    text = value.strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    try:
        parsed = pd.Timestamp(text).date()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid target date: {value!r}") from exc
    normalized = parsed.isoformat()
    if normalized != text:
        raise ValueError("target date must be YYYYMMDD or YYYY-MM-DD")
    return normalized


def _load_projection(path: Path, target_date: str) -> pd.DataFrame:
    """Load historical rows through the target date from the v0.2 projection."""
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
            "WHERE race_date<=? ORDER BY race_date,race_key,horse_no",
            connection,
            params=(target_date,),
        )
    finally:
        connection.close()
    if frame.empty:
        raise ValueError("Training Edge daily input is empty")
    if not bool((frame["race_date"] == target_date).any()):
        raise ValueError(f"target date is absent from projection: {target_date}")
    return frame


def _load_race_identity(index_db: Path, target_date: str) -> dict[str, dict[str, Any]]:
    """Load race_key -> venue/race identity for the target date."""
    if not index_db.is_file():
        raise FileNotFoundError(index_db)
    connection = sqlite3.connect(f"file:{index_db}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT race_key,venue_code,race_no FROM race_context "
            "WHERE race_date=? ORDER BY race_key",
            (target_date,),
        ).fetchall()
    finally:
        connection.close()
    if not rows:
        raise ValueError(f"target date is absent from Index Base: {target_date}")
    identity: dict[str, dict[str, Any]] = {}
    for race_key, venue_code, race_no in rows:
        key = str(race_key)
        if key in identity:
            raise ValueError(f"duplicate target race_key in Index Base: {key}")
        identity[key] = {
            "venue_code": str(venue_code or "").zfill(2),
            "race_no": int(race_no),
        }
    return identity


def _pre_race_reason(row: pd.Series) -> str | None:
    """Return the first frozen-history eligibility failure, else None."""
    if int(row["prior_runperf_count"]) < MIN_PRIOR_RUNPERF:
        return "PRIOR_RUNPERF_LT3"
    if int(row["prior_comparable_workout_count"]) < MIN_PRIOR_COMPARABLE_WORKOUT:
        return "PRIOR_COMPARABLE_WORKOUT_LT3"
    if pd.isna(row["final_self_pct"]):
        return "FINAL_SELF_PCT_MISSING"
    return None


def _display_index(value: float) -> str:
    """Round the PWA-facing percentile to exactly one decimal, half-up."""
    rounded = Decimal(str(float(value))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return format(rounded, ".1f")


def verify_runtime_fingerprint(input_db: Path, expected_path: Path) -> dict[str, Any]:
    """Verify that the 2013-2025 fit population/runtime matches the frozen reference."""
    if not expected_path.is_file():
        raise FileNotFoundError(expected_path)
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    actual = build_runtime_fingerprint(input_db)
    validate_fingerprint(actual, expected)
    return {
        "status": "PASS",
        "expected_path": str(expected_path),
        "expected_sha256": _sha256(expected_path),
        "training_eligible_n": actual["training_eligible_n"],
        "training_semantic_sha256": actual["training_semantic_sha256"],
        "c_training_prediction_sha256": actual["c_training_prediction_sha256"],
        "cab_training_prediction_sha256": actual["cab_training_prediction_sha256"],
        "runtime_packages": actual["runtime_packages"],
        "guard": actual["guard"],
    }


def score_day(
    input_db: Path,
    index_db: Path,
    calibration_path: Path,
    target_date: str,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Fit frozen 2013-2025 models and score one target day pre-race."""
    normalized_date = _normalize_target_date(target_date)
    frame = _load_projection(input_db, normalized_date)
    frame = _materialize_time_aware(frame)
    frame = _materialize_b(frame)

    training = _eligible(frame, TRAIN_FROM, TRAIN_TO)
    if training.empty:
        raise ValueError("frozen 2013-2025 training population is empty")

    target = frame.loc[frame["race_date"] == normalized_date].copy()
    target = target.sort_values(["race_key", "horse_no"], kind="stable").reset_index(drop=True)
    if target.empty:
        raise ValueError("target day has no runner rows")

    c_model = build_c_model()
    cab_model = build_cab_model()
    c_model.fit(training, training["performance_delta"])
    cab_model.fit(training, training["performance_delta"])
    calibration = load_calibration(calibration_path)
    race_identity = _load_race_identity(index_db, normalized_date)

    reasons = [_pre_race_reason(row) for _, row in target.iterrows()]
    eligible_mask = np.asarray([reason is None for reason in reasons], dtype=bool)
    edge_raw = np.full(len(target), np.nan, dtype=float)
    edge_percentile = np.full(len(target), np.nan, dtype=float)

    if bool(eligible_mask.any()):
        eligible = target.loc[eligible_mask]
        c_prediction = np.asarray(c_model.predict(eligible), dtype=float)
        cab_prediction = np.asarray(cab_model.predict(eligible), dtype=float)
        eligible_raw = cab_prediction - c_prediction
        eligible_percentile = np.asarray(
            [training_edge_percentile(value, calibration) for value in eligible_raw],
            dtype=float,
        )
        edge_raw[eligible_mask] = eligible_raw
        edge_percentile[eligible_mask] = eligible_percentile

    csv_rows: list[dict[str, str]] = []
    audit_rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int, int]] = set()
    for position, (_, row) in enumerate(target.iterrows()):
        race_key = str(row["race_key"])
        identity = race_identity.get(race_key)
        if identity is None:
            raise ValueError(f"target race_key absent from Index Base race_context: {race_key}")
        horse_no = int(row["horse_no"])
        key = (identity["venue_code"], int(identity["race_no"]), horse_no)
        if key in seen_keys:
            raise ValueError(f"duplicate daily output key: {key}")
        seen_keys.add(key)

        reason = reasons[position]
        display = ""
        direction = None
        raw_value = None
        percentile_value = None
        if reason is None:
            raw_value = float(edge_raw[position])
            percentile_value = float(edge_percentile[position])
            display = _display_index(percentile_value)
            direction = training_edge_direction(raw_value)

        csv_rows.append(
            {
                "date": normalized_date,
                "venue_code": identity["venue_code"],
                "race_no": str(int(identity["race_no"])),
                "horse_no": str(horse_no),
                "training_edge_index": display,
            }
        )
        audit_rows.append(
            {
                "race_key": race_key,
                "venue_code": identity["venue_code"],
                "race_no": int(identity["race_no"]),
                "horse_no": horse_no,
                "eligible": reason is None,
                "ineligible_reason": reason,
                "prior_runperf_count": int(row["prior_runperf_count"]),
                "prior_comparable_workout_count": int(row["prior_comparable_workout_count"]),
                "final_self_pct": None if pd.isna(row["final_self_pct"]) else float(row["final_self_pct"]),
                "training_edge_raw": raw_value,
                "training_edge_percentile": percentile_value,
                "training_edge_index_display": display or None,
                "direction": direction,
            }
        )

    csv_rows.sort(key=lambda item: (item["venue_code"], int(item["race_no"]), int(item["horse_no"])))
    audit_rows.sort(key=lambda item: (item["venue_code"], item["race_no"], item["horse_no"]))
    eligible_count = sum(1 for row in audit_rows if row["eligible"])
    audit = {
        "status": "success",
        "scorer_version": VERSION,
        "core_version": CORE_VERSION,
        "target_date": normalized_date,
        "training_period": f"{TRAIN_FROM}-{TRAIN_TO}",
        "training_eligible_n": int(len(training)),
        "target_runner_n": int(len(target)),
        "target_eligible_n": int(eligible_count),
        "target_ineligible_n": int(len(target) - eligible_count),
        "display_contract": {
            "field": "training_edge_index",
            "source": "frozen development percentile",
            "range": "0.0-100.0",
            "decimal_places": 1,
            "rounding": "ROUND_HALF_UP",
            "ineligible": "blank",
        },
        "guard": {
            "fit_min_year": int(training["year"].min()),
            "fit_max_year": int(training["year"].max()),
            "target_year": int(normalized_date[:4]),
            "target_result_required": False,
            "market_fields_used": False,
        },
        "source": {
            "input_db": str(input_db),
            "input_db_sha256": _sha256(input_db),
            "index_db": str(index_db),
            "index_db_sha256": _sha256(index_db),
            "calibration": str(calibration_path),
            "calibration_sha256": _sha256(calibration_path),
        },
        "rows": audit_rows,
    }
    return csv_rows, audit


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    """Write the five-column PWA handoff CSV as UTF-8 with BOM."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-db", type=Path, required=True)
    parser.add_argument("--index-db", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--runtime-fingerprint", type=Path, default=DEFAULT_RUNTIME_FINGERPRINT)
    parser.add_argument("--date", required=True, help="YYYYMMDD or YYYY-MM-DD")
    parser.add_argument("--out-csv", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    args = parser.parse_args()

    runtime_guard = verify_runtime_fingerprint(
        input_db=args.input_db,
        expected_path=args.runtime_fingerprint,
    )
    rows, audit = score_day(
        input_db=args.input_db,
        index_db=args.index_db,
        calibration_path=args.calibration,
        target_date=args.date,
    )
    audit["runtime_fingerprint"] = runtime_guard
    write_csv(rows, args.out_csv)
    audit["output"] = {
        "csv": str(args.out_csv),
        "csv_sha256": _sha256(args.out_csv),
        "audit_json": str(args.audit_json),
    }
    args.audit_json.parent.mkdir(parents=True, exist_ok=True)
    args.audit_json.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
