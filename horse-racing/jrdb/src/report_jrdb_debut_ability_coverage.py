#!/usr/bin/env python3
"""Report structural Debut Ability evidence coverage without predictive evaluation."""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import numpy as np

BANDWIDTHS = (200, 400, 600, 800)


def _date_token(value: Any) -> str | None:
    """Normalize a date-like value to YYYYMMDD."""
    if value is None:
        return None
    text = str(value).strip().replace("-", "").replace("/", "")
    if len(text) < 8 or not text[:8].isdigit():
        return None
    return text[:8]


def _lag_days(target_value: Any, source_value: Any) -> int | None:
    """Return nonnegative target-minus-source day lag when both dates are valid."""
    target = _date_token(target_value)
    source = _date_token(source_value)
    if target is None or source is None:
        return None
    try:
        target_date = date(int(target[:4]), int(target[4:6]), int(target[6:8]))
        source_date = date(int(source[:4]), int(source[4:6]), int(source[6:8]))
    except ValueError:
        return None
    lag = (target_date - source_date).days
    return lag if lag >= 0 else None


def _finite(values: Iterable[Any]) -> list[float]:
    """Return finite numeric values only."""
    result: list[float] = []
    for value in values:
        if value is None:
            continue
        number = float(value)
        if math.isfinite(number):
            result.append(number)
    return result


def _distribution(values: Iterable[Any]) -> dict[str, float | int | None]:
    """Summarize one numeric evidence distribution without using target outcomes."""
    finite = _finite(values)
    if not finite:
        return {"count": 0, "min": None, "p25": None, "median": None, "p75": None, "p90": None, "max": None}
    array = np.asarray(finite, dtype=float)
    return {
        "count": len(finite),
        "min": float(np.min(array)),
        "p25": float(np.quantile(array, 0.25)),
        "median": float(np.quantile(array, 0.50)),
        "p75": float(np.quantile(array, 0.75)),
        "p90": float(np.quantile(array, 0.90)),
        "max": float(np.max(array)),
    }


def _coverage(count: int, total: int) -> float | None:
    """Return a structural coverage ratio."""
    return float(count) / total if total else None


def report(database: Path, from_year: int, to_year: int) -> dict[str, Any]:
    """Build annual and aggregate structural coverage diagnostics."""
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT
              t.*,
              p.*,
              tr.*,
              pe.*,
              c.score_status AS target_score_status,
              c.official_runperf_raw AS target_runperf
            FROM debut_target_runner t
            JOIN debut_pedigree_feature p USING(race_key,horse_no)
            JOIN debut_training_feature tr USING(race_key,horse_no)
            JOIN debut_people_prior_feature pe USING(race_key,horse_no)
            LEFT JOIN debut_current_result c USING(race_key,horse_no)
            WHERE t.year BETWEEN ? AND ?
            ORDER BY t.year,t.race_date,t.race_key,t.horse_no
            """,
            (from_year, to_year),
        ).fetchall()
        records = [dict(row) for row in rows]
        if not records:
            raise ValueError("no Debut Ability snapshot rows in requested coverage period")

        def summarize(subset: list[dict[str, Any]]) -> dict[str, Any]:
            total = len(subset)
            true_first = sum(int(row["is_true_first_start"]) == 1 for row in subset)
            prior_start_no_scored = total - true_first
            label_ok = sum(
                row.get("target_score_status") == "OK"
                and row.get("target_runperf") is not None
                and math.isfinite(float(row["target_runperf"]))
                for row in subset
            )
            pre_race = sum(row.get("race_context_availability") == "PRE_RACE" for row in subset)
            identity = sum(row.get("horse_id") not in (None, "") for row in subset)
            profile = sum(int(row["profile_prior_day_available"]) == 1 for row in subset)
            same_day_profile = sum(int(row["profile_same_day_observation_exists"]) == 1 for row in subset)
            weight = sum(row.get("weight_relative") is not None for row in subset)
            cha = sum(int(row["cha_missing"]) == 0 for row in subset)
            cyb = sum(int(row["cyb_missing"]) == 0 for row in subset)
            lag_values = [
                lag
                for row in subset
                for lag in [_lag_days(row.get("race_date"), row.get("profile_data_date"))]
                if lag is not None
            ]

            pedigree = {}
            for prefix in (
                "sire_debut",
                "broodmare_sire_debut",
                "sire_line_debut",
                "broodmare_sire_line_debut",
                "sire_surface_debut",
                "broodmare_sire_surface_debut",
            ):
                counts = [int(row[f"{prefix}_n"]) for row in subset]
                covered = sum(value > 0 for value in counts)
                pedigree[prefix] = {
                    "coverage": _coverage(covered, total),
                    "n": _distribution(counts),
                }

            distance = {}
            for base in ("sire_distance", "broodmare_sire_distance"):
                for bandwidth in BANDWIDTHS:
                    prefix = f"{base}_d{bandwidth}"
                    counts = [int(row[f"{prefix}_n"]) for row in subset]
                    neff = [row[f"{prefix}_neff"] for row in subset if int(row[f"{prefix}_n"]) > 0]
                    covered = sum(value > 0 for value in counts)
                    distance[prefix] = {
                        "coverage": _coverage(covered, total),
                        "n": _distribution(counts),
                        "neff_when_present": _distribution(neff),
                    }

            people = {}
            for prefix in ("jockey_debut", "trainer_debut"):
                counts = [int(row[f"{prefix}_n"]) for row in subset]
                covered = sum(value > 0 for value in counts)
                people[prefix] = {
                    "coverage": _coverage(covered, total),
                    "n": _distribution(counts),
                }

            training_numeric = {}
            for field in (
                "jrdb_workout_index_cha",
                "jrdb_first_segment_index",
                "jrdb_middle_segment_index",
                "jrdb_final_segment_index",
                "jrdb_workout_index_cyb",
                "finish_index",
                "week_ago_workout_index",
            ):
                present = sum(row.get(field) is not None for row in subset)
                training_numeric[field] = _coverage(present, total)

            return {
                "target_count": total,
                "true_first_start_count": true_first,
                "true_first_start_rate": _coverage(true_first, total),
                "prior_start_no_scored_history_count": prior_start_no_scored,
                "prior_start_no_scored_history_rate": _coverage(prior_start_no_scored, total),
                "pre_race_context_coverage": _coverage(pre_race, total),
                "horse_id_coverage": _coverage(identity, total),
                "target_label_coverage": _coverage(label_ok, total),
                "profile_prior_day_coverage": _coverage(profile, total),
                "profile_same_day_observation_rate": _coverage(same_day_profile, total),
                "profile_lag_days_when_prior_available": _distribution(lag_values),
                "weight_relative_coverage": _coverage(weight, total),
                "cha_coverage": _coverage(cha, total),
                "cyb_coverage": _coverage(cyb, total),
                "training_numeric_coverage": training_numeric,
                "pedigree": pedigree,
                "distance": distance,
                "people": people,
            }

        annual = []
        for year in range(from_year, to_year + 1):
            subset = [row for row in records if int(row["year"]) == year]
            if subset:
                annual.append({"year": year, **summarize(subset)})

        return {
            "status": "PASS",
            "period": [from_year, to_year],
            "aggregate": summarize(records),
            "annual": annual,
            "predictive_metrics_computed": False,
            "2024_2025_predictive_metrics_inspected": False,
            "model_selected": False,
        }
    finally:
        connection.close()


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--from-year", required=True, type=int)
    parser.add_argument("--to-year", required=True, type=int)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = report(args.db, args.from_year, args.to_year)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": result["status"], "period": result["period"], "predictive_metrics_computed": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
