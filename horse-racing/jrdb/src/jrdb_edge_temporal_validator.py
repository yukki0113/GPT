#!/usr/bin/env python3
"""Factor-specific temporal validation for JRDB Edge Registry Phase 1.

The validator consumes deterministic candidates emitted by ``jrdb_edge_discovery``
and re-queries the leakage-safe Edge Feature Mart. It evaluates sample quality,
Performance and Value signals, return concentration, and the temporal validation
shape selected by the candidate's versioned policy.

This module does not alter the independent-index Ability/Edge score. Registry
promotion is a research/shadow status until a downstream consumer explicitly opts in.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping

from jrdb_edge_validation import load_policy_catalog

VERSION = "0.1.0"
ALLOWED_FIELDS = {
    "venue_code", "surface_code", "distance_m", "turn_code", "frame_zone",
    "sire_name", "sire_line_code", "broodmare_sire_name", "broodmare_sire_line_code",
    "jockey_code", "trainer_code", "distance_change_bucket", "surface_transition",
    "frame_transition",
}


def _validate_field(field: str) -> str:
    if field not in ALLOWED_FIELDS:
        raise ValueError(f"unsupported Edge condition field: {field}")
    return field


def _where(values: Mapping[str, Any], *, require_prev1: bool) -> tuple[str, list[Any]]:
    parts = ["calculation_status='ELIGIBLE'"]
    params: list[Any] = []
    if require_prev1:
        parts.append("prev1_race_date IS NOT NULL")
    for field, value in values.items():
        _validate_field(field)
        parts.append(f"{field}=?")
        params.append(value)
    return " AND ".join(parts), params


def _ratio(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline in (None, 0):
        return None
    return float(value) / float(baseline)


def _metrics(
    connection: sqlite3.Connection,
    values: Mapping[str, Any],
    baseline_values: Mapping[str, Any],
    baseline_mode: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    require_prev1 = baseline_mode == "same_anchor_with_prev1"
    where, params = _where(values, require_prev1=require_prev1)
    baseline_where, baseline_params = _where(baseline_values, require_prev1=require_prev1)
    if start_date is not None:
        where += " AND race_date>=?"
        baseline_where += " AND race_date>=?"
        params.append(start_date)
        baseline_params.append(start_date)
    if end_date is not None:
        where += " AND race_date<=?"
        baseline_where += " AND race_date<=?"
        params.append(end_date)
        baseline_params.append(end_date)

    aggregate_sql = """
      SELECT
        COUNT(*) AS sample_n,
        COUNT(DISTINCT horse_id) AS unique_horses,
        COUNT(DISTINCT race_key) AS unique_races,
        MIN(race_date) AS first_date,
        MAX(race_date) AS last_date,
        AVG(CASE WHEN label_win_hit IS NOT NULL THEN label_win_hit END) AS win_rate,
        AVG(CASE WHEN label_place_hit IS NOT NULL THEN label_place_hit END) AS place_rate,
        SUM(COALESCE(label_win_payout,0)) / (100.0 * COUNT(*)) AS win_roi,
        SUM(COALESCE(label_place_payout,0)) / (100.0 * COUNT(*)) AS place_roi,
        SUM(COALESCE(label_win_payout,0) + COALESCE(label_place_payout,0)) AS total_return
      FROM edge_runner_fact
      WHERE
    """
    row = connection.execute(aggregate_sql + where, params).fetchone()
    baseline = connection.execute(aggregate_sql + baseline_where, baseline_params).fetchone()
    if row is None or int(row["sample_n"] or 0) == 0:
        return {
            "sample_n": 0,
            "unique_horses": 0,
            "unique_races": 0,
            "baseline_first_date": baseline["first_date"] if baseline is not None else None,
            "baseline_last_date": baseline["last_date"] if baseline is not None else None,
            "performance_lift": None,
            "place_roi_vs_baseline": None,
        }

    largest_horse_n = connection.execute(
        "SELECT MAX(n) FROM (SELECT COUNT(*) AS n FROM edge_runner_fact WHERE "
        + where
        + " GROUP BY horse_id)",
        params,
    ).fetchone()[0] or 0
    top_returns = [
        result[0]
        for result in connection.execute(
            "SELECT COALESCE(label_win_payout,0)+COALESCE(label_place_payout,0) AS payout "
            "FROM edge_runner_fact WHERE " + where + " ORDER BY payout DESC LIMIT 3",
            params,
        )
    ]
    total_return = float(row["total_return"] or 0)
    return {
        "sample_n": int(row["sample_n"]),
        "unique_horses": int(row["unique_horses"]),
        "unique_races": int(row["unique_races"]),
        "first_date": row["first_date"],
        "last_date": row["last_date"],
        "win_rate": row["win_rate"],
        "place_rate": row["place_rate"],
        "win_roi": row["win_roi"],
        "place_roi": row["place_roi"],
        "baseline_sample_n": int(baseline["sample_n"] or 0),
        "baseline_first_date": baseline["first_date"],
        "baseline_last_date": baseline["last_date"],
        "baseline_place_rate": baseline["place_rate"],
        "baseline_place_roi": baseline["place_roi"],
        "performance_lift": _ratio(row["place_rate"], baseline["place_rate"]),
        "place_roi_vs_baseline": _ratio(row["place_roi"], baseline["place_roi"]),
        "largest_horse_sample_share": float(largest_horse_n) / float(row["sample_n"]),
        "largest_return_share": (
            float(top_returns[0]) / total_return if top_returns and total_return > 0 else None
        ),
        "top3_return_share": (
            sum(float(value) for value in top_returns) / total_return if total_return > 0 else None
        ),
    }


def classify_signals(metrics: Mapping[str, Any], policy: Mapping[str, Any]) -> tuple[str, str]:
    """Classify Performance and Value independently from versioned thresholds."""
    lift = metrics.get("performance_lift")
    roi_ratio = metrics.get("place_roi_vs_baseline")
    place_roi = metrics.get("place_roi")

    performance = "NEUTRAL"
    if lift is not None:
        if float(lift) >= float(policy["performance_positive_lift"]):
            performance = "POSITIVE"
        elif float(lift) <= float(policy["performance_negative_lift"]):
            performance = "NEGATIVE"

    value = "NEUTRAL"
    if roi_ratio is not None:
        if (
            float(roi_ratio) >= float(policy["value_positive_roi_ratio"])
            and place_roi is not None
            and float(place_roi) >= float(policy["value_positive_place_roi"])
        ):
            value = "POSITIVE"
        elif float(roi_ratio) <= float(policy["value_negative_roi_ratio"]):
            value = "NEGATIVE"
    return performance, value


def _supports(value: float | None, signal: str) -> bool:
    if value is None or signal == "NEUTRAL":
        return False
    return float(value) > 1.0 if signal == "POSITIVE" else float(value) < 1.0


def _calendar_segments(first_date: str, last_date: str, years: int) -> list[tuple[str, str, str]]:
    first_year = date.fromisoformat(first_date).year
    last_year = date.fromisoformat(last_date).year
    output: list[tuple[str, str, str]] = []
    for start_year in range(first_year, last_year + 1, years):
        end_year = min(last_year, start_year + years - 1)
        output.append(
            (
                f"{start_year}-{end_year}",
                f"{start_year}-01-01",
                f"{end_year}-12-31",
            )
        )
    return output


def _relative_segments(first_date: str, last_date: str, count: int) -> list[tuple[str, str, str]]:
    start = date.fromisoformat(first_date)
    end = date.fromisoformat(last_date)
    total_days = max(1, (end - start).days + 1)
    output: list[tuple[str, str, str]] = []
    for index in range(count):
        segment_start = start + timedelta(days=(total_days * index) // count)
        if index == count - 1:
            segment_end = end
        else:
            segment_end = start + timedelta(days=(total_days * (index + 1)) // count - 1)
        output.append(
            (f"life_{index + 1}", segment_start.isoformat(), segment_end.isoformat())
        )
    return output


def _rolling_windows(as_of_date: str, windows_days: list[int]) -> list[tuple[str, str, str]]:
    end = date.fromisoformat(as_of_date)
    return [
        (
            f"{days}d",
            (end - timedelta(days=int(days) - 1)).isoformat(),
            end.isoformat(),
        )
        for days in windows_days
    ]


def _polarity(performance_signal: str, value_signal: str) -> str:
    signals = {performance_signal, value_signal} - {"NEUTRAL"}
    if signals == {"POSITIVE"}:
        return "POSITIVE"
    if signals == {"NEGATIVE"}:
        return "NEGATIVE"
    return "MIXED"


def validate_candidate(
    mart_path: str | Path,
    candidate: Mapping[str, Any],
    policy_catalog: Mapping[str, Any],
) -> dict[str, Any]:
    policy = policy_catalog["policies"][candidate["policy_id"]]
    values = {**candidate["anchor"], **candidate["modifiers"]}
    baseline_values = dict(candidate["anchor"])
    baseline_mode = candidate["baseline"]
    connection = sqlite3.connect(mart_path)
    connection.row_factory = sqlite3.Row
    try:
        overall = _metrics(connection, values, baseline_values, baseline_mode)
        performance_signal, value_signal = classify_signals(overall, policy)
        failures: list[str] = []
        validation_class = policy["validation_class"]

        minimum_n = (
            int(policy["watch_min_n"])
            if validation_class == "EMERGING"
            else int(policy["min_total_n"])
        )
        if overall["sample_n"] < minimum_n:
            failures.append("MIN_SAMPLE")
        if overall["unique_horses"] < int(policy.get("min_unique_horses", 0)):
            failures.append("MIN_UNIQUE_HORSES")
        if overall["unique_races"] < int(policy.get("min_unique_races", 0)):
            failures.append("MIN_UNIQUE_RACES")
        if (
            overall.get("largest_horse_sample_share") is not None
            and float(overall["largest_horse_sample_share"])
            > float(policy.get("max_single_horse_sample_share", 1.0))
        ):
            failures.append("HORSE_CONCENTRATION")
        if (
            overall.get("largest_return_share") is not None
            and float(overall["largest_return_share"])
            > float(policy.get("max_single_return_share", 1.0))
        ):
            failures.append("RETURN_CONCENTRATION")
        if performance_signal == "NEUTRAL" and value_signal == "NEUTRAL":
            failures.append("NO_SIGNAL")

        anchor_first = (
            overall.get("baseline_first_date")
            or candidate.get("anchor_first_observed_date")
            or candidate["first_observed_date"]
        )
        as_of_date = candidate["as_of_date"]
        if validation_class == "STRUCTURAL":
            periods = _calendar_segments(anchor_first, as_of_date, int(policy["segment_years"]))
        elif validation_class == "LIFECYCLE":
            periods = _relative_segments(anchor_first, as_of_date, int(policy["relative_segments"]))
        else:
            periods = _rolling_windows(as_of_date, [int(v) for v in policy["windows_days"]])

        minimum_slice_n = int(policy.get("min_segment_n", policy.get("min_window_n", 1)))
        slices: list[dict[str, Any]] = []
        for label, start_date, end_date in periods:
            metrics = _metrics(
                connection,
                values,
                baseline_values,
                baseline_mode,
                start_date=start_date,
                end_date=end_date,
            )
            metrics.update(
                {
                    "slice_label": label,
                    "period_start": start_date,
                    "period_end": end_date,
                }
            )
            if metrics["sample_n"] >= minimum_slice_n:
                slices.append(metrics)

        performance_consistency_ratio = None
        value_consistency_ratio = None
        required_slices = int(policy.get("min_segments", policy.get("min_windows", 1)))
        if len(slices) < required_slices:
            failures.append(
                "MIN_TEMPORAL_SLICES"
                if validation_class in {"STRUCTURAL", "LIFECYCLE"}
                else "MIN_ROLLING_WINDOWS"
            )

        if slices and performance_signal != "NEUTRAL":
            performance_consistency_ratio = sum(
                _supports(item.get("performance_lift"), performance_signal) for item in slices
            ) / len(slices)
            if performance_consistency_ratio + 1e-9 < float(policy.get("min_same_direction_ratio", 0.0)):
                failures.append("PERFORMANCE_TIME_INSTABILITY")
        if slices and value_signal != "NEUTRAL":
            value_consistency_ratio = sum(
                _supports(item.get("place_roi_vs_baseline"), value_signal) for item in slices
            ) / len(slices)
            if value_consistency_ratio + 1e-9 < float(policy.get("min_same_direction_ratio", 0.0)):
                failures.append("VALUE_TIME_INSTABILITY")

        if validation_class == "DYNAMIC":
            primary_label = f"{int(policy['primary_window_days'])}d"
            primary = next((item for item in slices if item["slice_label"] == primary_label), None)
            if primary is None:
                failures.append("PRIMARY_WINDOW_MISSING")
            else:
                primary_performance, primary_value = classify_signals(primary, policy)
                if performance_signal != "NEUTRAL" and primary_performance != performance_signal:
                    failures.append("PERFORMANCE_PRIMARY_WINDOW_LOST")
                if value_signal != "NEUTRAL" and primary_value != value_signal:
                    failures.append("VALUE_PRIMARY_WINDOW_LOST")

        soft_sample_failures = {
            "MIN_SAMPLE",
            "MIN_UNIQUE_HORSES",
            "MIN_UNIQUE_RACES",
            "MIN_TEMPORAL_SLICES",
            "MIN_ROLLING_WINDOWS",
            "PRIMARY_WINDOW_MISSING",
        }
        dynamic_decay_failures = {
            "PERFORMANCE_PRIMARY_WINDOW_LOST",
            "VALUE_PRIMARY_WINDOW_LOST",
        }
        failure_set = set(failures)
        if not failures:
            if validation_class == "EMERGING":
                decision = (
                    "PROVISIONAL"
                    if overall["sample_n"] >= int(policy["provisional_min_n"])
                    else "WATCH"
                )
            else:
                decision = "ACTIVATE"
        elif failure_set <= soft_sample_failures:
            decision = "WATCH"
        elif validation_class == "DYNAMIC" and failure_set <= dynamic_decay_failures:
            decision = "DECAY"
        else:
            decision = "REJECT"

        status = {
            "ACTIVATE": "ACTIVE",
            "PROVISIONAL": "PROVISIONAL",
            "WATCH": "WATCH",
            "DECAY": "DECAYING",
            "REJECT": "REJECTED",
        }[decision]
        return {
            "candidate_id": candidate["candidate_id"],
            "decision": decision,
            "status": status,
            "performance_signal": performance_signal,
            "value_signal": value_signal,
            "polarity": _polarity(performance_signal, value_signal),
            "failure_reasons": failures,
            "overall": overall,
            "slices": slices,
            "performance_consistency_ratio": performance_consistency_ratio,
            "value_consistency_ratio": value_consistency_ratio,
            "policy_id": candidate["policy_id"],
            "validation_class": validation_class,
        }
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mart", required=True)
    parser.add_argument("--candidates", required=True, help="Discovery JSONL")
    parser.add_argument("--policies")
    parser.add_argument("--output", required=True, help="Validation JSONL")
    args = parser.parse_args()
    policies = load_policy_catalog(args.policies) if args.policies else load_policy_catalog()
    candidates = [
        json.loads(line)
        for line in Path(args.candidates).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    results = [validate_candidate(args.mart, candidate, policies) for candidate in candidates]
    with Path(args.output).open("w", encoding="utf-8", newline="\n") as handle:
        for result in results:
            handle.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
    summary: dict[str, int] = {}
    for result in results:
        summary[result["status"]] = summary.get(result["status"], 0) + 1
    print(json.dumps({"status": "PASS", "validated": len(results), "by_status": summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
