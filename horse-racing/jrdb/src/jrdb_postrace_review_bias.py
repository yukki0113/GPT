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
