#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Time-standard and day-adjustment primitives for Post-Race Review v0.1."""
from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Mapping

CLASS_NUMERIC = {
    "NEWCOMER": 0.0,
    "MAIDEN": 1.0,
    "CLASS_1": 2.0,
    "CLASS_2": 3.0,
    "CLASS_3": 4.0,
    "OPEN": 5.0,
    "G3": 6.0,
    "G2": 7.0,
    "G1": 8.0,
}


def _finite_positive(value: object) -> float | None:
    """Return a finite positive float or NULL-equivalent None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result) or result <= 0.0:
        return None
    return result


def _finite(value: object) -> float | None:
    """Return a finite float including zero and signed values."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def percentile(values: Iterable[object], percentile_value: float) -> float | None:
    """Return a linear-interpolated percentile for finite values."""
    if percentile_value < 0.0 or percentile_value > 100.0:
        raise ValueError("percentile must be between 0 and 100")

    cleaned: list[float] = []
    for value in values:
        parsed = _finite(value)
        if parsed is not None:
            cleaned.append(parsed)
    cleaned.sort()
    if not cleaned:
        return None
    if len(cleaned) == 1:
        return cleaned[0]

    position = (len(cleaned) - 1) * percentile_value / 100.0
    lower_index = int(math.floor(position))
    upper_index = int(math.ceil(position))
    if lower_index == upper_index:
        return cleaned[lower_index]

    weight = position - lower_index
    lower = cleaned[lower_index]
    upper = cleaned[upper_index]
    return lower + (upper - lower) * weight


def median_absolute_deviation(values: Iterable[object]) -> float | None:
    """Return median absolute deviation around the sample median."""
    cleaned: list[float] = []
    for value in values:
        parsed = _finite(value)
        if parsed is not None:
            cleaned.append(parsed)
    if not cleaned:
        return None

    center = statistics.median(cleaned)
    deviations = [abs(value - center) for value in cleaned]
    return float(statistics.median(deviations))


def trimmed_mean(
    values: Iterable[object],
    trim_fraction: float = 0.10,
) -> float | None:
    """Return a symmetric trimmed mean without hiding tiny-sample behavior."""
    if trim_fraction < 0.0 or trim_fraction >= 0.5:
        raise ValueError("trim_fraction must be in [0, 0.5)")

    cleaned: list[float] = []
    for value in values:
        parsed = _finite(value)
        if parsed is not None:
            cleaned.append(parsed)
    cleaned.sort()
    if not cleaned:
        return None

    trim_count = int(math.floor(len(cleaned) * trim_fraction))
    if trim_count == 0 or trim_count * 2 >= len(cleaned):
        return float(statistics.mean(cleaned))

    retained = cleaned[trim_count : len(cleaned) - trim_count]
    return float(statistics.mean(retained))


def standard_confidence(sample_count: int) -> str:
    """Return the v0.1 operational confidence band for a baseline sample."""
    if sample_count >= 100:
        return "HIGH"
    if sample_count >= 30:
        return "MEDIUM"
    if sample_count >= 10:
        return "LOW"
    return "FALLBACK"


def build_time_standard(values: Iterable[object]) -> dict[str, object]:
    """Summarize valid winner times for one condition bucket."""
    cleaned: list[float] = []
    for value in values:
        parsed = _finite_positive(value)
        if parsed is not None:
            cleaned.append(parsed)
    cleaned.sort()

    count = len(cleaned)
    if count == 0:
        return {
            "sample_count": 0,
            "median_winner_time_sec": None,
            "trimmed_mean_winner_time_sec": None,
            "p10_time_sec": None,
            "p25_time_sec": None,
            "p50_time_sec": None,
            "p75_time_sec": None,
            "p90_time_sec": None,
            "mad_time_sec": None,
            "stddev_time_sec": None,
            "standard_time_sec": None,
            "standard_method": "median",
            "confidence": "FALLBACK",
        }

    median_value = float(statistics.median(cleaned))
    stddev = 0.0
    if count > 1:
        stddev = float(statistics.pstdev(cleaned))

    return {
        "sample_count": count,
        "median_winner_time_sec": median_value,
        "trimmed_mean_winner_time_sec": trimmed_mean(cleaned),
        "p10_time_sec": percentile(cleaned, 10.0),
        "p25_time_sec": percentile(cleaned, 25.0),
        "p50_time_sec": percentile(cleaned, 50.0),
        "p75_time_sec": percentile(cleaned, 75.0),
        "p90_time_sec": percentile(cleaned, 90.0),
        "mad_time_sec": median_absolute_deviation(cleaned),
        "stddev_time_sec": stddev,
        "standard_time_sec": median_value,
        "standard_method": "median",
        "confidence": standard_confidence(count),
    }


def normalized_time_delta_per_1000m(
    actual_time_sec: object,
    standard_time_sec: object,
    distance_m: object,
) -> float | None:
    """Normalize actual-minus-standard time residual to 1000 metres."""
    actual = _finite_positive(actual_time_sec)
    standard = _finite_positive(standard_time_sec)
    distance = _finite_positive(distance_m)
    if actual is None or standard is None or distance is None:
        return None

    return (actual - standard) / (distance / 1000.0)


def estimate_day_track_adjustment(
    races: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Estimate one date/venue/surface adjustment from race residual medians.

    Each race mapping must provide actual_time_sec, standard_time_sec and
    distance_m. Invalid races are excluded rather than treated as neutral.
    """
    residuals: list[float] = []
    distances: set[int] = set()

    for race in races:
        residual = normalized_time_delta_per_1000m(
            race.get("actual_time_sec"),
            race.get("standard_time_sec"),
            race.get("distance_m"),
        )
        if residual is None:
            continue
        residuals.append(residual)

        distance = _finite_positive(race.get("distance_m"))
        if distance is not None:
            distances.add(int(distance))

    if not residuals:
        return {
            "race_count": 0,
            "distance_count": 0,
            "adjustment_per_1000m_sec": None,
            "residual_mad_sec": None,
        }

    return {
        "race_count": len(residuals),
        "distance_count": len(distances),
        "adjustment_per_1000m_sec": float(statistics.median(residuals)),
        "residual_mad_sec": median_absolute_deviation(residuals),
    }


def day_track_adjustment_seconds(
    adjustment_per_1000m_sec: object,
    distance_m: object,
) -> float | None:
    """Scale a normalized day adjustment back to one race distance."""
    adjustment = _finite(adjustment_per_1000m_sec)
    distance = _finite_positive(distance_m)
    if adjustment is None or distance is None:
        return None
    return adjustment * distance / 1000.0


def adjusted_standard_time_seconds(
    historical_standard_time_sec: object,
    day_adjustment_sec: object,
) -> float | None:
    """Apply a signed day-track adjustment to the historical standard."""
    standard = _finite_positive(historical_standard_time_sec)
    adjustment = _finite(day_adjustment_sec)
    if standard is None or adjustment is None:
        return None

    result = standard + adjustment
    if result <= 0.0:
        return None
    return result


def class_equivalent(
    actual_time_sec: object,
    adjusted_class_standards: Mapping[str, object],
) -> dict[str, object]:
    """Return nearest class and a monotonic-curve continuous class position.

    Continuous interpolation is emitted only when available class standards are
    strictly faster as class rank rises. If the empirical curve is non-monotonic,
    the discrete nearest class remains available while the continuous value is
    NULL so the caller cannot silently trust a broken class curve.
    """
    actual = _finite_positive(actual_time_sec)
    if actual is None:
        return {
            "equivalent_class_group": None,
            "class_equivalent_numeric": None,
            "curve_monotonic": None,
        }

    points: list[tuple[float, str, float]] = []
    for class_group, value in adjusted_class_standards.items():
        rank = CLASS_NUMERIC.get(str(class_group))
        standard = _finite_positive(value)
        if rank is None or standard is None:
            continue
        points.append((rank, str(class_group), standard))

    points.sort(key=lambda item: item[0])
    if not points:
        return {
            "equivalent_class_group": None,
            "class_equivalent_numeric": None,
            "curve_monotonic": None,
        }

    nearest = min(points, key=lambda item: (abs(actual - item[2]), item[0]))
    monotonic = True
    for index in range(1, len(points)):
        if points[index][2] >= points[index - 1][2]:
            monotonic = False
            break

    if len(points) == 1 or not monotonic:
        numeric = None
        if len(points) == 1:
            numeric = nearest[0]
        return {
            "equivalent_class_group": nearest[1],
            "class_equivalent_numeric": numeric,
            "curve_monotonic": monotonic,
        }

    if actual >= points[0][2]:
        numeric = points[0][0]
    elif actual <= points[-1][2]:
        numeric = points[-1][0]
    else:
        numeric = None
        for index in range(1, len(points)):
            lower_rank, _lower_name, lower_time = points[index - 1]
            upper_rank, _upper_name, upper_time = points[index]
            if lower_time >= actual >= upper_time:
                time_span = lower_time - upper_time
                fraction = (lower_time - actual) / time_span
                numeric = lower_rank + fraction * (upper_rank - lower_rank)
                break

    return {
        "equivalent_class_group": nearest[1],
        "class_equivalent_numeric": numeric,
        "curve_monotonic": monotonic,
    }
