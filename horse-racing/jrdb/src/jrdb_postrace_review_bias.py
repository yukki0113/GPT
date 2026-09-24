#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Track-bias primitives for JRDB Post-Race Review v0.1.

All residuals in this module follow one sign convention:
positive = better than expected, negative = worse than expected.

The module does not choose an ability model, running-style threshold, or
same-day prior strength. Those require empirical calibration and are supplied
by the caller.
"""
from __future__ import annotations

import math
import statistics
from collections.abc import Iterable

from jrdb_postrace_review_standard import median_absolute_deviation


def _finite(value: object) -> float | None:
    """Return a finite float while preserving missing values as None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def performance_residual(
    actual_performance: object,
    expected_performance: object,
) -> float | None:
    """Return actual-minus-expected under the high-is-better score convention."""
    actual = _finite(actual_performance)
    expected = _finite(expected_performance)
    if actual is None or expected is None:
        return None
    return actual - expected


def summarize_residuals(values: Iterable[object]) -> dict[str, object]:
    """Summarize one lane/style/frame residual bucket without shrinkage."""
    cleaned: list[float] = []
    for value in values:
        parsed = _finite(value)
        if parsed is not None:
            cleaned.append(parsed)

    if not cleaned:
        return {
            "sample_count": 0,
            "mean_residual": None,
            "median_residual": None,
            "mad_residual": None,
        }

    return {
        "sample_count": len(cleaned),
        "mean_residual": float(statistics.mean(cleaned)),
        "median_residual": float(statistics.median(cleaned)),
        "mad_residual": median_absolute_deviation(cleaned),
    }


def shrink_estimate(
    same_day_estimate: object,
    same_day_sample_count: int,
    prior_estimate: object,
    prior_strength: object,
) -> dict[str, object]:
    """Shrink a same-day estimate toward an externally chosen prior.

    prior_strength is an effective pseudo-sample count and has deliberately no
    default. A production value must be selected from validation evidence.
    """
    day = _finite(same_day_estimate)
    prior = _finite(prior_estimate)
    strength = _finite(prior_strength)

    if same_day_sample_count < 0:
        raise ValueError("same_day_sample_count must be non-negative")
    if strength is None or strength < 0.0:
        raise ValueError("prior_strength must be finite and non-negative")

    if day is None and prior is None:
        return {
            "shrunk_estimate": None,
            "same_day_weight": None,
            "prior_weight": None,
        }
    if day is None:
        return {
            "shrunk_estimate": prior,
            "same_day_weight": 0.0,
            "prior_weight": 1.0,
        }
    if prior is None or strength == 0.0:
        return {
            "shrunk_estimate": day,
            "same_day_weight": 1.0,
            "prior_weight": 0.0,
        }

    denominator = float(same_day_sample_count) + strength
    if denominator <= 0.0:
        return {
            "shrunk_estimate": None,
            "same_day_weight": None,
            "prior_weight": None,
        }

    day_weight = float(same_day_sample_count) / denominator
    prior_weight = strength / denominator
    estimate = day * day_weight + prior * prior_weight

    return {
        "shrunk_estimate": estimate,
        "same_day_weight": day_weight,
        "prior_weight": prior_weight,
    }


def bias_direction(
    bias_score: object,
    neutral_band: object,
) -> str | None:
    """Classify one bucket effect under the high-is-better residual convention."""
    score = _finite(bias_score)
    band = _finite(neutral_band)
    if score is None:
        return None
    if band is None or band < 0.0:
        raise ValueError("neutral_band must be finite and non-negative")

    if score > band:
        return "ASSISTED"
    if score < -band:
        return "AGAINST"
    return "NEUTRAL"


def bias_corrected_performance(
    actual_performance: object,
    bias_score: object,
) -> float | None:
    """Remove the estimated bucket effect from a high-is-better performance."""
    actual = _finite(actual_performance)
    bias = _finite(bias_score)
    if actual is None or bias is None:
        return None
    return actual - bias


def frame_bucket(frame_no: object) -> str | None:
    """Keep JRA frame number as an exact categorical bucket; do not over-group."""
    value = _finite(frame_no)
    if value is None or not value.is_integer():
        return None

    frame = int(value)
    if frame < 1 or frame > 8:
        return None
    return f"FRAME_{frame}"


def style_bucket(race_running_style_code: object) -> str | None:
    """Keep JRDB observed race-running-style code as an exact category."""
    value = _finite(race_running_style_code)
    if value is None or not value.is_integer():
        return None
    code = int(value)
    if code < 1 or code > 6:
        return None
    return f"STYLE_{code}"


def time_performance_signal(
    horse_adjusted_delta_per_1000m: object,
) -> float | None:
    """Convert time residual into a high-is-better performance signal."""
    value = _finite(horse_adjusted_delta_per_1000m)
    if value is None:
        return None
    return -value


def _last3f_relative_by_horse(
    rows: Iterable[dict[str, object]],
) -> dict[str, float]:
    """Return high-is-better last3F signal relative to each race median."""
    materialized = list(rows)
    by_race: dict[str, list[dict[str, object]]] = {}
    for row in materialized:
        race_key = str(row.get("race_key") or "").strip()
        if not race_key:
            continue
        by_race.setdefault(race_key, []).append(row)

    result: dict[str, float] = {}
    for race_rows in by_race.values():
        values: list[float] = []
        for row in race_rows:
            value = _finite(row.get("last3f_sec"))
            if value is not None and value > 0.0:
                values.append(value)
        if not values:
            continue
        center = float(statistics.median(values))
        for row in race_rows:
            key = str(row.get("race_horse_key") or "").strip()
            value = _finite(row.get("last3f_sec"))
            if key and value is not None and value > 0.0:
                result[key] = center - value
    return result


def _bias_bucket(
    row: dict[str, object],
    dimension: str,
) -> str | None:
    """Return one exact Review bias bucket."""
    if dimension == "lane":
        return preferred_lane_bucket(
            row.get("fourth_corner_lane_bucket"),
            row.get("course_lane_bucket"),
        )
    if dimension == "style":
        return style_bucket(row.get("race_running_style_code"))
    if dimension == "frame":
        return frame_bucket(row.get("frame_no"))
    raise ValueError(f"unsupported bias dimension: {dimension}")


def build_descriptive_track_bias(
    horse_rows: Iterable[dict[str, object]],
    expected_performance_by_horse: dict[str, float] | None = None,
) -> list[dict[str, object]]:
    """Build same-day descriptive/adjusted bias summaries.

    The input should already be one date x venue x surface. Raw summaries are
    always available when observations exist. Adjusted residual summaries are
    emitted only for horses with a supplied pre-day expected performance.
    """
    materialized = list(horse_rows)
    if not materialized:
        return []

    identities = {
        (
            str(row.get("race_date") or "").strip(),
            str(row.get("venue_code") or "").strip(),
            str(row.get("surface_code") or "").strip(),
        )
        for row in materialized
    }
    if len(identities) != 1:
        raise ValueError(
            "track bias input must be one race_date x venue x surface"
        )
    race_date, venue_code, surface_code = next(iter(identities))

    last3f_relative = _last3f_relative_by_horse(materialized)
    dimensions = ("lane", "style", "frame")
    grouped: dict[
        tuple[str, str],
        dict[str, list[float]],
    ] = {}

    for row in materialized:
        horse_key = str(row.get("race_horse_key") or "").strip()
        raw_signal = time_performance_signal(
            row.get("horse_adjusted_delta_per_1000m")
        )
        expected = None
        if expected_performance_by_horse is not None and horse_key:
            expected = expected_performance_by_horse.get(horse_key)
        adjusted = performance_residual(raw_signal, expected)

        for dimension in dimensions:
            bucket = _bias_bucket(row, dimension)
            if bucket is None:
                continue
            values = grouped.setdefault(
                (dimension, bucket),
                {
                    "raw_time": [],
                    "last3f_relative": [],
                    "adjusted": [],
                },
            )
            if raw_signal is not None:
                values["raw_time"].append(raw_signal)
            relative = last3f_relative.get(horse_key)
            if relative is not None:
                values["last3f_relative"].append(relative)
            if adjusted is not None:
                values["adjusted"].append(adjusted)

    output: list[dict[str, object]] = []
    for dimension, bucket in sorted(grouped):
        values = grouped[(dimension, bucket)]
        raw_summary = summarize_residuals(values["raw_time"])
        last3f_summary = summarize_residuals(values["last3f_relative"])
        adjusted_summary = summarize_residuals(values["adjusted"])

        output.append(
            {
                "race_date": race_date,
                "venue_code": venue_code,
                "surface_code": surface_code,
                "bias_dimension": dimension,
                "bias_bucket": bucket,
                "same_day_sample_count": raw_summary["sample_count"],
                "raw_time_performance_median": raw_summary["median_residual"],
                "raw_time_performance_mean": raw_summary["mean_residual"],
                "raw_last3f_relative_median": last3f_summary[
                    "median_residual"
                ],
                "raw_last3f_sample_count": last3f_summary["sample_count"],
                "adjusted_performance_residual": adjusted_summary[
                    "median_residual"
                ],
                "adjusted_sample_count": adjusted_summary["sample_count"],
            }
        )
    return output


def leave_one_race_out_bias_estimate(
    horse_rows: Iterable[dict[str, object]],
    *,
    target_race_key: str,
    dimension: str,
    bucket: str,
    expected_performance_by_horse: dict[str, float],
    prior_estimate: object = None,
    prior_strength: object = 0.0,
) -> dict[str, object]:
    """Estimate adjusted bucket bias excluding every horse in the target race."""
    residuals: list[float] = []
    for row in horse_rows:
        if str(row.get("race_key") or "").strip() == target_race_key:
            continue
        if _bias_bucket(row, dimension) != bucket:
            continue

        horse_key = str(row.get("race_horse_key") or "").strip()
        expected = expected_performance_by_horse.get(horse_key)
        actual = time_performance_signal(
            row.get("horse_adjusted_delta_per_1000m")
        )
        residual = performance_residual(actual, expected)
        if residual is not None:
            residuals.append(residual)

    summary = summarize_residuals(residuals)
    shrunk = shrink_estimate(
        summary["median_residual"],
        int(summary["sample_count"]),
        prior_estimate,
        prior_strength,
    )
    return {
        "loo_sample_count": summary["sample_count"],
        "loo_adjusted_residual": summary["median_residual"],
        "loo_adjusted_mad": summary["mad_residual"],
        "shrunk_bias_score": shrunk["shrunk_estimate"],
        "same_day_weight": shrunk["same_day_weight"],
        "prior_weight": shrunk["prior_weight"],
    }


def preferred_lane_bucket(
    fourth_corner_lane_bucket: object,
    course_lane_bucket: object,
) -> str | None:
    """Prefer observed fourth-corner lane and fall back to overall course lane."""
    fourth = str(fourth_corner_lane_bucket or "").strip().upper()
    overall = str(course_lane_bucket or "").strip().upper()
    valid = {"INNER", "MIDDLE", "OUTER"}

    if fourth in valid:
        return fourth
    if overall in valid:
        return overall
    return None
