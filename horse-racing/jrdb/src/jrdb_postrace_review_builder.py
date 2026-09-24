#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure in-memory builder for JRDB Post-Race Review v0.1 foundation."""
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping

from jrdb_postrace_review import (
    REVIEW_LOGIC_VERSION,
    REVIEW_SCHEMA_VERSION,
    classify_pace_percentile,
)
from jrdb_postrace_review_context import (
    build_horse_context_rows,
    build_race_context,
)
from jrdb_postrace_review_standard import (
    adjusted_standard_time_seconds,
    build_asof_class_standard_curve,
    class_equivalent,
    day_track_adjustment_seconds,
    leave_one_out_day_track_adjustments,
    normalized_time_delta_per_1000m,
    percentile_rank,
    select_asof_time_standard,
)


class PostRaceReviewBuildError(RuntimeError):
    """Raised when Review rows cannot be built deterministically."""


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _finite(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _int(value: object) -> int | None:
    number = _finite(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def _group_by_race(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, list[Mapping[str, object]]]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        race_key = _text(row.get("race_key"))
        if not race_key:
            raise PostRaceReviewBuildError("Review source row has no race_key")
        grouped[race_key].append(row)
    return dict(grouped)


def _normal_winner_sample(
    race_rows: list[Mapping[str, object]],
) -> dict[str, object] | None:
    """Create one baseline sample from one completed historical race."""
    context = build_race_context(race_rows)
    winner_time = _finite(context.get("winner_time_sec"))
    if winner_time is None:
        return None

    first = race_rows[0]
    return {
        "race_key": context["race_key"],
        "race_date": first.get("race_date"),
        "venue_code": first.get("venue_code"),
        "surface_code": first.get("surface_code"),
        "distance_m": first.get("distance_m"),
        "course_code": first.get("course_code"),
        "race_type_code": first.get("race_type_code"),
        "age_group": first.get("race_type_code"),
        "declared_class_group": first.get("declared_class_group"),
        "race_class_group": first.get("declared_class_group"),
        "winner_time_sec": winner_time,
        "pace_balance_sec": context.get("pace_balance_sec"),
    }


def build_historical_race_samples(
    rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Collapse horse-grain source history into one race-grain sample table."""
    grouped = _group_by_race(rows)
    samples: list[dict[str, object]] = []
    for race_key in sorted(grouped):
        sample = _normal_winner_sample(grouped[race_key])
        if sample is not None:
            samples.append(sample)

    samples.sort(
        key=lambda row: (
            _text(row.get("race_date")),
            _text(row.get("race_key")),
        )
    )
    return samples


def _pace_history(
    historical_samples: list[dict[str, object]],
    target: Mapping[str, object],
    minimum_sample_count: int,
) -> tuple[list[float], int]:
    """Return as-of pace-balance peers, exact venue first then cross-venue."""
    target_date = _text(target.get("race_date"))
    venue = _text(target.get("venue_code"))
    surface = _text(target.get("surface_code"))
    distance = _int(target.get("distance_m"))

    exact: list[float] = []
    broad: list[float] = []
    for sample in historical_samples:
        sample_date = _text(sample.get("race_date"))
        if not sample_date or not target_date or sample_date >= target_date:
            continue
        if _text(sample.get("surface_code")) != surface:
            continue
        if _int(sample.get("distance_m")) != distance:
            continue

        balance = _finite(sample.get("pace_balance_sec"))
        if balance is None:
            continue
        broad.append(balance)
        if _text(sample.get("venue_code")) == venue:
            exact.append(balance)

    if len(exact) >= minimum_sample_count:
        return exact, 1
    if broad:
        return broad, 2
    return exact, 1


def _effective_class_curve(
    curve: Mapping[str, Mapping[str, object]],
    adjustment_sec: float | None,
) -> dict[str, float]:
    """Apply one target-distance day adjustment to every available class standard."""
    result: dict[str, float] = {}
    for class_group, standard in curve.items():
        base = _finite(standard.get("standard_time_sec"))
        if base is None:
            continue

        effective = base
        if adjustment_sec is not None:
            adjusted = adjusted_standard_time_seconds(base, adjustment_sec)
            if adjusted is None:
                continue
            effective = adjusted
        result[str(class_group)] = effective
    return result


def build_review_day(
    target_rows: Iterable[Mapping[str, object]],
    historical_rows: Iterable[Mapping[str, object]],
    *,
    minimum_standard_sample_count: int = 10,
    minimum_pace_sample_count: int = 10,
    minimum_day_adjustment_race_count: int = 2,
) -> dict[str, object]:
    """Build one completed day's Review foundation without publication side effects."""
    target_materialized = list(target_rows)
    historical_materialized = list(historical_rows)
    if not target_materialized:
        raise PostRaceReviewBuildError("target Review day has no rows")

    target_dates = {
        _text(row.get("race_date"))
        for row in target_materialized
        if _text(row.get("race_date"))
    }
    if len(target_dates) != 1:
        raise PostRaceReviewBuildError(
            "build_review_day requires exactly one target race_date"
        )
    target_date = next(iter(target_dates))

    for row in historical_materialized:
        history_date = _text(row.get("race_date"))
        if history_date and history_date >= target_date:
            raise PostRaceReviewBuildError(
                "historical_rows must be strictly earlier than target date"
            )

    historical_samples = build_historical_race_samples(historical_materialized)
    target_grouped = _group_by_race(target_materialized)

    race_work: dict[str, dict[str, object]] = {}
    adjustment_groups: dict[
        tuple[str, str],
        list[dict[str, object]],
    ] = defaultdict(list)

    for race_key in sorted(target_grouped):
        race_rows = target_grouped[race_key]
        context = build_race_context(race_rows)
        first = race_rows[0]

        standard = select_asof_time_standard(
            historical_samples,
            first,
            minimum_sample_count=minimum_standard_sample_count,
        )
        curve = build_asof_class_standard_curve(
            historical_samples,
            first,
            minimum_sample_count=minimum_standard_sample_count,
        )
        pace_values, pace_scope_level = _pace_history(
            historical_samples,
            first,
            minimum_pace_sample_count,
        )
        pace_percentile = percentile_rank(
            pace_values,
            context.get("pace_balance_sec"),
        )
        pace_shape = None
        if (
            pace_percentile is not None
            and len(pace_values) >= minimum_pace_sample_count
        ):
            pace_shape = classify_pace_percentile(pace_percentile)

        race_work[race_key] = {
            "rows": race_rows,
            "context": context,
            "standard": standard,
            "curve": curve,
            "pace_sample_count": len(pace_values),
            "pace_scope_level": pace_scope_level,
            "pace_percentile": pace_percentile,
            "pace_shape": pace_shape,
        }

        adjustment_groups[
            (
                _text(first.get("venue_code")),
                _text(first.get("surface_code")),
            )
        ].append(
            {
                "race_key": race_key,
                "actual_time_sec": context.get("winner_time_sec"),
                "standard_time_sec": standard.get("standard_time_sec"),
                "distance_m": first.get("distance_m"),
            }
        )

    loo_by_race: dict[str, dict[str, object]] = {}
    for group_races in adjustment_groups.values():
        loo_by_race.update(
            leave_one_out_day_track_adjustments(group_races)
        )

    race_context_rows: list[dict[str, object]] = []
    race_review_rows: list[dict[str, object]] = []
    horse_review_rows: list[dict[str, object]] = []

    missing_standard_count = 0
    missing_day_adjustment_count = 0
    low_pace_sample_count = 0

    for race_key in sorted(race_work):
        work = race_work[race_key]
        race_rows = work["rows"]
        if not isinstance(race_rows, list):
            raise AssertionError("internal race rows must be a list")
        context = dict(work["context"])
        standard = work["standard"]
        curve = work["curve"]
        if not isinstance(standard, Mapping) or not isinstance(curve, Mapping):
            raise AssertionError("internal standard contract broken")

        first = race_rows[0]
        loo = loo_by_race.get(
            race_key,
            {
                "race_count": 0,
                "adjustment_per_1000m_sec": None,
                "residual_mad_sec": None,
            },
        )
        adjustment_per_1000m = _finite(
            loo.get("adjustment_per_1000m_sec")
        )
        adjustment_candidate_sec = day_track_adjustment_seconds(
            adjustment_per_1000m,
            first.get("distance_m"),
        )
        adjustment_sec = None
        loo_race_count = _int(loo.get("race_count")) or 0
        if loo_race_count >= minimum_day_adjustment_race_count:
            adjustment_sec = adjustment_candidate_sec

        historical_standard = _finite(standard.get("standard_time_sec"))
        effective_standard = historical_standard
        adjustment_applied = False
        time_delta_basis = "HISTORICAL_ONLY"

        if historical_standard is None:
            missing_standard_count += 1
            effective_standard = None
            time_delta_basis = "NO_STANDARD"
        elif adjustment_sec is not None:
            effective_standard = adjusted_standard_time_seconds(
                historical_standard,
                adjustment_sec,
            )
            adjustment_applied = effective_standard is not None
            if adjustment_applied:
                time_delta_basis = "LOO_DAY_ADJUSTED"
        else:
            missing_day_adjustment_count += 1

        winner_time = _finite(context.get("winner_time_sec"))
        time_delta = None
        time_delta_per_1000m = None
        if winner_time is not None and effective_standard is not None:
            time_delta = winner_time - effective_standard
            time_delta_per_1000m = normalized_time_delta_per_1000m(
                winner_time,
                effective_standard,
                first.get("distance_m"),
            )

        effective_curve = _effective_class_curve(
            curve,
            adjustment_sec if adjustment_applied else None,
        )
        race_class = class_equivalent(
            winner_time,
            effective_curve,
        )

        pace_sample_count = int(work["pace_sample_count"])
        if pace_sample_count < minimum_pace_sample_count:
            low_pace_sample_count += 1

        context.update(
            {
                "pace_balance_percentile": work["pace_percentile"],
                "pace_shape": work["pace_shape"],
                "pace_sample_count": pace_sample_count,
                "pace_scope_level": work["pace_scope_level"],
                "review_schema_version": REVIEW_SCHEMA_VERSION,
                "review_logic_version": REVIEW_LOGIC_VERSION,
            }
        )
        race_context_rows.append(context)

        race_review_rows.append(
            {
                "race_key": race_key,
                "race_date": first.get("race_date"),
                "venue_code": first.get("venue_code"),
                "surface_code": first.get("surface_code"),
                "distance_m": first.get("distance_m"),
                "declared_class_group": first.get("declared_class_group"),
                "winner_time_sec": winner_time,
                "historical_standard_time_sec": historical_standard,
                "standard_sample_count": standard.get("sample_count"),
                "standard_scope_level": standard.get("scope_level"),
                "standard_confidence": standard.get("confidence"),
                "standard_sample_start_date": standard.get("sample_start_date"),
                "standard_sample_end_date": standard.get("sample_end_date"),
                "day_adjustment_per_1000m_sec": adjustment_per_1000m,
                "day_adjustment_candidate_sec": adjustment_candidate_sec,
                "day_track_adjustment_sec": adjustment_sec,
                "day_adjustment_race_count": loo_race_count,
                "minimum_day_adjustment_race_count": minimum_day_adjustment_race_count,
                "day_adjustment_residual_mad_sec": loo.get(
                    "residual_mad_sec"
                ),
                "day_adjustment_applied": adjustment_applied,
                "adjusted_standard_time_sec": effective_standard,
                "time_delta_sec": time_delta,
                "time_delta_per_1000m": time_delta_per_1000m,
                "time_delta_basis": time_delta_basis,
                "equivalent_class_group": race_class.get(
                    "equivalent_class_group"
                ),
                "class_equivalent_numeric": race_class.get(
                    "class_equivalent_numeric"
                ),
                "class_curve_monotonic": race_class.get("curve_monotonic"),
                "pace_shape": work["pace_shape"],
                "review_schema_version": REVIEW_SCHEMA_VERSION,
                "review_logic_version": REVIEW_LOGIC_VERSION,
            }
        )

        source_by_key = {
            _text(row.get("race_horse_key")): row
            for row in race_rows
            if _text(row.get("race_horse_key"))
        }
        horse_context = build_horse_context_rows(race_rows)
        for horse in horse_context:
            key = _text(horse.get("race_horse_key"))
            source = source_by_key.get(key, {})
            own_time = _finite(horse.get("time_sec"))
            horse_delta = None
            horse_delta_per_1000m = None
            if own_time is not None and effective_standard is not None:
                horse_delta = own_time - effective_standard
                horse_delta_per_1000m = normalized_time_delta_per_1000m(
                    own_time,
                    effective_standard,
                    first.get("distance_m"),
                )
            horse_class = class_equivalent(
                own_time,
                effective_curve,
            )

            output = dict(horse)
            output.update(
                {
                    "horse_id": source.get("horse_id"),
                    "horse_name": source.get("horse_name"),
                    "frame_no": source.get("frame_no"),
                    "carried_weight_kg": source.get("carried_weight_kg"),
                    "declared_running_style_code": source.get(
                        "declared_running_style_code"
                    ),
                    "race_running_style_code": source.get(
                        "race_running_style_code"
                    ),
                    "course_lane_code": source.get("course_lane_code"),
                    "course_lane_bucket": source.get("course_lane_bucket"),
                    "fourth_corner_lane_code": source.get(
                        "fourth_corner_lane_code"
                    ),
                    "fourth_corner_lane_bucket": source.get(
                        "fourth_corner_lane_bucket"
                    ),
                    "historical_standard_time_sec": historical_standard,
                    "adjusted_standard_time_sec": effective_standard,
                    "day_adjustment_candidate_sec": adjustment_candidate_sec,
                    "day_track_adjustment_sec": adjustment_sec,
                    "day_adjustment_applied": adjustment_applied,
                    "horse_adjusted_delta_sec": horse_delta,
                    "horse_adjusted_delta_per_1000m": horse_delta_per_1000m,
                    "time_class_equivalent": horse_class.get(
                        "equivalent_class_group"
                    ),
                    "time_class_equivalent_numeric": horse_class.get(
                        "class_equivalent_numeric"
                    ),
                    "class_curve_monotonic": horse_class.get(
                        "curve_monotonic"
                    ),
                    "pace_shape": work["pace_shape"],
                    "start_delay_confidence": "UNKNOWN",
                    "jrdb_track_diff": source.get("jrdb_track_diff"),
                    "jrdb_pace_score": source.get("jrdb_pace_score"),
                    "jrdb_late_break_score": source.get(
                        "jrdb_late_break_score"
                    ),
                    "jrdb_position_score": source.get("jrdb_position_score"),
                    "jrdb_trouble_score": source.get("jrdb_trouble_score"),
                    "jrdb_prev_trouble_score": source.get(
                        "jrdb_prev_trouble_score"
                    ),
                    "jrdb_mid_trouble_score": source.get(
                        "jrdb_mid_trouble_score"
                    ),
                    "jrdb_late_trouble_score": source.get(
                        "jrdb_late_trouble_score"
                    ),
                    "performance_label": "UNKNOWN",
                    "reason_codes_json": "[]",
                    "review_schema_version": REVIEW_SCHEMA_VERSION,
                    "review_logic_version": REVIEW_LOGIC_VERSION,
                }
            )
            horse_review_rows.append(output)

    race_context_rows.sort(key=lambda row: _text(row.get("race_key")))
    race_review_rows.sort(key=lambda row: _text(row.get("race_key")))
    horse_review_rows.sort(
        key=lambda row: (
            _text(row.get("race_key")),
            _int(row.get("horse_no")) or 0,
        )
    )

    return {
        "fact_race_context": race_context_rows,
        "fact_race_review": race_review_rows,
        "fact_horse_performance": horse_review_rows,
        "audit": {
            "target_race_date": target_date,
            "historical_race_sample_count": len(historical_samples),
            "race_count": len(race_review_rows),
            "horse_count": len(horse_review_rows),
            "missing_standard_race_count": missing_standard_count,
            "missing_day_adjustment_race_count": missing_day_adjustment_count,
            "low_pace_sample_race_count": low_pace_sample_count,
            "review_schema_version": REVIEW_SCHEMA_VERSION,
            "review_logic_version": REVIEW_LOGIC_VERSION,
        },
    }
