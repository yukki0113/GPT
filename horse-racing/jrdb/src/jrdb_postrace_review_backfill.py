#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Streaming historical backfill for JRDB Post-Race Review v0.1.

The ordinary day builder is intentionally simple and accepts historical rows.
That is useful for daily operation and tests, but repeatedly scanning all prior
rows would be wasteful for a 2010-2025 rebuild. This module keeps compact
rolling indices for standards and pace distributions, processes each date once,
and stages the resulting relations in DuckDB before immutable publication.
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from audit_jrdb_postrace_review import audit_review_bundle
from jrdb_postrace_review import (
    REVIEW_LOGIC_VERSION,
    REVIEW_SCHEMA_VERSION,
    classify_pace_percentile,
)
from jrdb_postrace_review_bias import build_descriptive_track_bias
from jrdb_postrace_review_context import (
    build_horse_context_rows,
    build_race_context,
)
from jrdb_postrace_review_publish import publish_database_snapshot
from jrdb_postrace_review_source import HistoricalReviewWarehouseReader
from jrdb_postrace_review_standard import (
    BASELINE_VERSION,
    CLASS_NUMERIC,
    STANDARD_SCOPES,
    adjusted_standard_time_seconds,
    class_equivalent,
    day_track_adjustment_seconds,
    leave_one_out_day_track_adjustments,
    normalized_time_delta_per_1000m,
    standard_confidence,
)


class PostRaceReviewBackfillError(RuntimeError):
    """Raised when historical Review backfill cannot proceed safely."""


def _text(value: object) -> str:
    """Return stripped text."""
    if value is None:
        return ""
    return str(value).strip()


def _finite(value: object) -> float | None:
    """Return one finite float while preserving missing values."""
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
    """Return one integer-like value."""
    number = _finite(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def _race_month(value: object) -> int | None:
    """Return month from a normalized Review date."""
    text = _text(value)
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        try:
            month = int(text[5:7])
        except ValueError:
            return None
        if 1 <= month <= 12:
            return month
    return None


def _standard_value(
    row: Mapping[str, object],
    field_name: str,
) -> object:
    """Mirror the v0.1 standard-key semantics without scanning history."""
    if field_name == "age_group":
        value = row.get("age_group")
        if value is not None and _text(value):
            return value
        return row.get("race_type_code")

    if field_name == "race_month":
        value = row.get("race_month")
        if value is not None:
            return value
        return _race_month(row.get("race_date"))

    if field_name == "race_class_group":
        value = row.get("race_class_group")
        if value is not None and _text(value):
            return value
        return row.get("declared_class_group")

    return row.get(field_name)


def _median_sorted(values: Sequence[float]) -> float | None:
    """Return the median of an already-sorted finite sequence."""
    count = len(values)
    if count == 0:
        return None
    middle = count // 2
    if count % 2:
        return float(values[middle])
    return float(values[middle - 1] + values[middle]) / 2.0


@dataclass
class _TimeBucket:
    """One rolling time-standard bucket."""

    values: list[float] = field(default_factory=list)
    sample_start_date: str | None = None
    sample_end_date: str | None = None

    def add(self, race_date: str, winner_time_sec: float) -> None:
        bisect.insort(self.values, winner_time_sec)
        if self.sample_start_date is None:
            self.sample_start_date = race_date
        self.sample_end_date = race_date

    def summary(
        self,
        scope_level: int,
        scope_fields: Sequence[str],
    ) -> dict[str, object]:
        count = len(self.values)
        return {
            "sample_count": count,
            "standard_time_sec": _median_sorted(self.values),
            "standard_method": "median",
            "confidence": standard_confidence(count),
            "scope_level": scope_level,
            "scope_fields": list(scope_fields),
            "sample_start_date": self.sample_start_date,
            "sample_end_date": self.sample_end_date,
        }


class RollingReviewHistory:
    """Compact prior-date index for time standards and pace distributions."""

    def __init__(self) -> None:
        self._standards: list[dict[tuple[str, ...], _TimeBucket]] = [
            {} for _ in STANDARD_SCOPES
        ]
        self._pace_exact: dict[tuple[str, str, int], list[float]] = {}
        self._pace_broad: dict[tuple[str, int], list[float]] = {}
        self.race_sample_count = 0

    @staticmethod
    def _scope_key(
        target: Mapping[str, object],
        fields: Sequence[str],
    ) -> tuple[str, ...] | None:
        values: list[str] = []
        for field_name in fields:
            value = _standard_value(target, field_name)
            text = _text(value)
            if not text:
                return None
            values.append(text)
        return tuple(values)

    def lookup_standard(
        self,
        target: Mapping[str, object],
        *,
        minimum_sample_count: int,
        class_group: str | None = None,
    ) -> dict[str, object]:
        """Resolve one v0.1 standard with the same documented fallback order."""
        if minimum_sample_count < 1:
            raise ValueError("minimum_sample_count must be at least 1")

        lookup_target = dict(target)
        if class_group is not None:
            lookup_target["race_class_group"] = class_group

        broadest_nonempty: tuple[int, Sequence[str], _TimeBucket] | None = None

        for index, fields in enumerate(STANDARD_SCOPES):
            scope_level = index + 1
            key = self._scope_key(lookup_target, fields)
            if key is None:
                continue
            bucket = self._standards[index].get(key)
            if bucket is None or not bucket.values:
                continue

            broadest_nonempty = (scope_level, fields, bucket)
            if len(bucket.values) >= minimum_sample_count:
                return bucket.summary(scope_level, fields)

        if broadest_nonempty is not None:
            scope_level, fields, bucket = broadest_nonempty
            return bucket.summary(scope_level, fields)

        return {
            "sample_count": 0,
            "standard_time_sec": None,
            "standard_method": "median",
            "confidence": "FALLBACK",
            "scope_level": None,
            "scope_fields": None,
            "sample_start_date": None,
            "sample_end_date": None,
        }

    def lookup_class_curve(
        self,
        target: Mapping[str, object],
        *,
        minimum_sample_count: int,
    ) -> dict[str, dict[str, object]]:
        """Resolve every known class independently; never substitute classes."""
        result: dict[str, dict[str, object]] = {}
        for class_group in CLASS_NUMERIC:
            result[class_group] = self.lookup_standard(
                target,
                minimum_sample_count=minimum_sample_count,
                class_group=class_group,
            )
        return result

    @staticmethod
    def _percentile_rank_sorted(
        values: Sequence[float],
        target_value: object,
    ) -> float | None:
        target = _finite(target_value)
        if target is None or not values:
            return None

        left = bisect.bisect_left(values, target)
        right = bisect.bisect_right(values, target)
        equal = right - left
        return 100.0 * (
            float(left) + 0.5 * float(equal)
        ) / float(len(values))

    def lookup_pace(
        self,
        target: Mapping[str, object],
        pace_balance_sec: object,
        *,
        minimum_sample_count: int,
    ) -> dict[str, object]:
        """Resolve an as-of pace percentile, preferring exact venue peers."""
        venue = _text(target.get("venue_code"))
        surface = _text(target.get("surface_code"))
        distance = _int(target.get("distance_m"))
        if not surface or distance is None:
            return {
                "pace_balance_percentile": None,
                "pace_sample_count": 0,
                "pace_scope_level": None,
                "pace_shape": None,
            }

        exact = self._pace_exact.get(
            (venue, surface, distance),
            [],
        )
        broad = self._pace_broad.get(
            (surface, distance),
            [],
        )

        values: Sequence[float]
        scope_level: int
        if len(exact) >= minimum_sample_count:
            values = exact
            scope_level = 1
        elif broad:
            values = broad
            scope_level = 2
        else:
            values = exact
            scope_level = 1

        percentile = self._percentile_rank_sorted(
            values,
            pace_balance_sec,
        )
        pace_shape = None
        if (
            percentile is not None
            and len(values) >= minimum_sample_count
        ):
            pace_shape = classify_pace_percentile(percentile)

        return {
            "pace_balance_percentile": percentile,
            "pace_sample_count": len(values),
            "pace_scope_level": scope_level,
            "pace_shape": pace_shape,
        }

    def add_race_sample(
        self,
        sample: Mapping[str, object],
    ) -> None:
        """Add one completed race only after its whole date has been reviewed."""
        race_date = _text(sample.get("race_date"))
        winner_time = _finite(sample.get("winner_time_sec"))
        if not race_date or winner_time is None or winner_time <= 0.0:
            return

        for index, fields in enumerate(STANDARD_SCOPES):
            key = self._scope_key(sample, fields)
            if key is None:
                continue
            bucket = self._standards[index].setdefault(
                key,
                _TimeBucket(),
            )
            bucket.add(race_date, winner_time)

        pace_balance = _finite(sample.get("pace_balance_sec"))
        venue = _text(sample.get("venue_code"))
        surface = _text(sample.get("surface_code"))
        distance = _int(sample.get("distance_m"))
        if (
            pace_balance is not None
            and surface
            and distance is not None
        ):
            exact = self._pace_exact.setdefault(
                (venue, surface, distance),
                [],
            )
            broad = self._pace_broad.setdefault(
                (surface, distance),
                [],
            )
            bisect.insort(exact, pace_balance)
            bisect.insort(broad, pace_balance)

        self.race_sample_count += 1

    def add_race_samples(
        self,
        samples: Iterable[Mapping[str, object]],
    ) -> None:
        for sample in samples:
            self.add_race_sample(sample)


def _group_by_race(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, list[Mapping[str, object]]]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        race_key = _text(row.get("race_key"))
        if not race_key:
            raise PostRaceReviewBackfillError(
                "Review source row has no race_key"
            )
        grouped[race_key].append(row)
    return dict(grouped)


def _effective_class_curve(
    curve: Mapping[str, Mapping[str, object]],
    adjustment_sec: float | None,
) -> dict[str, float]:
    result: dict[str, float] = {}
    for class_group, standard in curve.items():
        base = _finite(standard.get("standard_time_sec"))
        if base is None:
            continue

        effective = base
        if adjustment_sec is not None:
            adjusted = adjusted_standard_time_seconds(
                base,
                adjustment_sec,
            )
            if adjusted is None:
                continue
            effective = adjusted
        result[str(class_group)] = effective
    return result


def _history_sample(
    first: Mapping[str, object],
    context: Mapping[str, object],
) -> dict[str, object] | None:
    winner_time = _finite(context.get("winner_time_sec"))
    if winner_time is None or winner_time <= 0.0:
        return None

    return {
        "race_key": context.get("race_key"),
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


def build_review_day_indexed(
    target_rows: Iterable[Mapping[str, object]],
    history: RollingReviewHistory,
    *,
    minimum_standard_sample_count: int = 10,
    minimum_pace_sample_count: int = 10,
    minimum_day_adjustment_race_count: int = 2,
) -> dict[str, object]:
    """Build one Review day from compact prior-date rolling indices."""
    target_materialized = list(target_rows)
    if not target_materialized:
        raise PostRaceReviewBackfillError(
            "target Review day has no rows"
        )

    target_dates = {
        _text(row.get("race_date"))
        for row in target_materialized
        if _text(row.get("race_date"))
    }
    if len(target_dates) != 1:
        raise PostRaceReviewBackfillError(
            "indexed Review day requires exactly one race_date"
        )
    target_date = next(iter(target_dates))
    target_grouped = _group_by_race(target_materialized)

    race_work: dict[str, dict[str, object]] = {}
    adjustment_groups: dict[
        tuple[str, str],
        list[dict[str, object]],
    ] = defaultdict(list)
    history_samples: list[dict[str, object]] = []

    for race_key in sorted(target_grouped):
        race_rows = target_grouped[race_key]
        context = build_race_context(race_rows)
        first = race_rows[0]

        standard = history.lookup_standard(
            first,
            minimum_sample_count=minimum_standard_sample_count,
        )
        curve = history.lookup_class_curve(
            first,
            minimum_sample_count=minimum_standard_sample_count,
        )
        pace = history.lookup_pace(
            first,
            context.get("pace_balance_sec"),
            minimum_sample_count=minimum_pace_sample_count,
        )

        race_work[race_key] = {
            "rows": race_rows,
            "context": context,
            "standard": standard,
            "curve": curve,
            "pace": pace,
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

        sample = _history_sample(first, context)
        if sample is not None:
            history_samples.append(sample)

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
        context_value = work["context"]
        standard = work["standard"]
        curve = work["curve"]
        pace = work["pace"]

        if not isinstance(race_rows, list):
            raise AssertionError("internal race rows must be a list")
        if not isinstance(context_value, Mapping):
            raise AssertionError("internal context contract broken")
        if not isinstance(standard, Mapping):
            raise AssertionError("internal standard contract broken")
        if not isinstance(curve, Mapping):
            raise AssertionError("internal curve contract broken")
        if not isinstance(pace, Mapping):
            raise AssertionError("internal pace contract broken")

        context = dict(context_value)
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

        historical_standard = _finite(
            standard.get("standard_time_sec")
        )
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

        pace_sample_count = _int(
            pace.get("pace_sample_count")
        ) or 0
        if pace_sample_count < minimum_pace_sample_count:
            low_pace_sample_count += 1

        context.update(
            {
                "pace_balance_percentile": pace.get(
                    "pace_balance_percentile"
                ),
                "pace_shape": pace.get("pace_shape"),
                "pace_sample_count": pace_sample_count,
                "pace_scope_level": pace.get("pace_scope_level"),
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
                "declared_class_group": first.get(
                    "declared_class_group"
                ),
                "winner_time_sec": winner_time,
                "historical_standard_time_sec": historical_standard,
                "standard_sample_count": standard.get("sample_count"),
                "standard_scope_level": standard.get("scope_level"),
                "standard_confidence": standard.get("confidence"),
                "standard_sample_start_date": standard.get(
                    "sample_start_date"
                ),
                "standard_sample_end_date": standard.get(
                    "sample_end_date"
                ),
                "day_adjustment_per_1000m_sec": adjustment_per_1000m,
                "day_adjustment_candidate_sec": adjustment_candidate_sec,
                "day_track_adjustment_sec": adjustment_sec,
                "day_adjustment_race_count": loo_race_count,
                "minimum_day_adjustment_race_count": (
                    minimum_day_adjustment_race_count
                ),
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
                "class_curve_monotonic": race_class.get(
                    "curve_monotonic"
                ),
                "pace_shape": pace.get("pace_shape"),
                "baseline_version": BASELINE_VERSION,
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
            race_horse_key = _text(horse.get("race_horse_key"))
            source = source_by_key.get(race_horse_key, {})
            own_time = _finite(horse.get("time_sec"))
            horse_delta = None
            horse_delta_per_1000m = None

            if own_time is not None and effective_standard is not None:
                horse_delta = own_time - effective_standard
                horse_delta_per_1000m = (
                    normalized_time_delta_per_1000m(
                        own_time,
                        effective_standard,
                        first.get("distance_m"),
                    )
                )

            horse_class = class_equivalent(
                own_time,
                effective_curve,
            )

            output = dict(horse)
            output.update(
                {
                    "race_date": first.get("race_date"),
                    "venue_code": first.get("venue_code"),
                    "surface_code": first.get("surface_code"),
                    "distance_m": first.get("distance_m"),
                    "field_size": first.get("field_size"),
                    "declared_class_group": first.get(
                        "declared_class_group"
                    ),
                    "horse_id": source.get("horse_id"),
                    "horse_name": source.get("horse_name"),
                    "frame_no": source.get("frame_no"),
                    "carried_weight_kg": source.get(
                        "carried_weight_kg"
                    ),
                    "declared_running_style_code": source.get(
                        "declared_running_style_code"
                    ),
                    "race_running_style_code": source.get(
                        "race_running_style_code"
                    ),
                    "course_lane_code": source.get(
                        "course_lane_code"
                    ),
                    "course_lane_bucket": source.get(
                        "course_lane_bucket"
                    ),
                    "fourth_corner_lane_code": source.get(
                        "fourth_corner_lane_code"
                    ),
                    "fourth_corner_lane_bucket": source.get(
                        "fourth_corner_lane_bucket"
                    ),
                    "historical_standard_time_sec": (
                        historical_standard
                    ),
                    "adjusted_standard_time_sec": effective_standard,
                    "day_adjustment_candidate_sec": (
                        adjustment_candidate_sec
                    ),
                    "day_track_adjustment_sec": adjustment_sec,
                    "day_adjustment_applied": adjustment_applied,
                    "horse_adjusted_delta_sec": horse_delta,
                    "horse_adjusted_delta_per_1000m": (
                        horse_delta_per_1000m
                    ),
                    "time_class_equivalent": horse_class.get(
                        "equivalent_class_group"
                    ),
                    "time_class_equivalent_numeric": horse_class.get(
                        "class_equivalent_numeric"
                    ),
                    "class_curve_monotonic": horse_class.get(
                        "curve_monotonic"
                    ),
                    "pace_shape": pace.get("pace_shape"),
                    "start_delay_confidence": "UNKNOWN",
                    "jrdb_track_diff": source.get(
                        "jrdb_track_diff"
                    ),
                    "jrdb_pace_score": source.get(
                        "jrdb_pace_score"
                    ),
                    "jrdb_late_break_score": source.get(
                        "jrdb_late_break_score"
                    ),
                    "jrdb_position_score": source.get(
                        "jrdb_position_score"
                    ),
                    "jrdb_trouble_score": source.get(
                        "jrdb_trouble_score"
                    ),
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
                    "baseline_version": BASELINE_VERSION,
                    "review_schema_version": REVIEW_SCHEMA_VERSION,
                    "review_logic_version": REVIEW_LOGIC_VERSION,
                }
            )
            horse_review_rows.append(output)

    race_context_rows.sort(
        key=lambda row: _text(row.get("race_key"))
    )
    race_review_rows.sort(
        key=lambda row: _text(row.get("race_key"))
    )
    horse_review_rows.sort(
        key=lambda row: (
            _text(row.get("race_key")),
            _int(row.get("horse_no")) or 0,
        )
    )
    history_samples.sort(
        key=lambda row: _text(row.get("race_key"))
    )

    return {
        "fact_race_context": race_context_rows,
        "fact_race_review": race_review_rows,
        "fact_horse_performance": horse_review_rows,
        "history_samples": history_samples,
        "audit": {
            "target_race_date": target_date,
            "prior_race_sample_count": history.race_sample_count,
            "race_count": len(race_review_rows),
            "horse_count": len(horse_review_rows),
            "missing_standard_race_count": missing_standard_count,
            "missing_day_adjustment_race_count": (
                missing_day_adjustment_count
            ),
            "low_pace_sample_race_count": low_pace_sample_count,
            "baseline_version": BASELINE_VERSION,
            "review_schema_version": REVIEW_SCHEMA_VERSION,
            "review_logic_version": REVIEW_LOGIC_VERSION,
        },
    }


def build_descriptive_bias_rows(
    horse_rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Create v0.1 descriptive bias rows without uncalibrated causal scores."""
    grouped: dict[
        tuple[str, str],
        list[dict[str, object]],
    ] = defaultdict(list)

    for source in horse_rows:
        row = dict(source)
        venue = _text(row.get("venue_code"))
        surface = _text(row.get("surface_code"))
        if not venue or not surface:
            continue
        grouped[(venue, surface)].append(row)

    result: list[dict[str, object]] = []
    for key in sorted(grouped):
        summaries = build_descriptive_track_bias(
            grouped[key],
            expected_performance_by_horse=None,
        )
        for summary in summaries:
            raw_count = _int(
                summary.get("same_day_sample_count")
            ) or 0
            last3f_count = _int(
                summary.get("raw_last3f_sample_count")
            ) or 0
            if raw_count == 0 and last3f_count == 0:
                continue

            output = dict(summary)
            output.update(
                {
                    "prior_sample_count": None,
                    "raw_same_day_estimate": summary.get(
                        "raw_time_performance_median"
                    ),
                    "prior_estimate": None,
                    "prior_strength": None,
                    "shrunk_bias_score": None,
                    "bias_direction": None,
                    "confidence": (
                        "DESCRIPTIVE_ONLY"
                        if max(raw_count, last3f_count) >= 3
                        else "LOW_SAMPLE"
                    ),
                    "baseline_version": BASELINE_VERSION,
                    "review_schema_version": REVIEW_SCHEMA_VERSION,
                    "review_logic_version": REVIEW_LOGIC_VERSION,
                }
            )
            result.append(output)

    result.sort(
        key=lambda row: (
            _text(row.get("venue_code")),
            _text(row.get("surface_code")),
            _text(row.get("bias_dimension")),
            _text(row.get("bias_bucket")),
        )
    )
    return result


def _schema_sql() -> str:
    """Read the frozen Review schema used by the streaming stage database."""
    path = (
        Path(__file__).resolve().parents[1]
        / "schema"
        / "jrdb_postrace_review_schema_v0_1.sql"
    )
    return path.read_text(encoding="utf-8")


def _relation_columns(
    connection: Any,
    relation: str,
) -> list[str]:
    rows = connection.execute(
        "SELECT column_name "
        "FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ? "
        "ORDER BY ordinal_position",
        [relation],
    ).fetchall()
    return [str(row[0]) for row in rows]


def _insert_relation_rows(
    connection: Any,
    relation: str,
    rows: Sequence[Mapping[str, object]],
) -> None:
    """Insert one small daily batch against the frozen physical schema."""
    if not rows:
        return

    columns = _relation_columns(connection, relation)
    allowed = set(columns)
    for row in rows:
        unknown = {
            str(key)
            for key in row
            if str(key) not in allowed
        }
        if unknown:
            raise PostRaceReviewBackfillError(
                f"{relation}: unknown columns {sorted(unknown)}"
            )

    quoted = ", ".join(
        '"' + column.replace('"', '""') + '"'
        for column in columns
    )
    marks = ", ".join("?" for _ in columns)
    values = [
        tuple(row.get(column) for column in columns)
        for row in rows
    ]
    connection.executemany(
        f'INSERT INTO "{relation}" ({quoted}) VALUES ({marks})',
        values,
    )


def _group_by_date(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, list[Mapping[str, object]]]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        race_date = _text(row.get("race_date"))
        if not race_date:
            raise PostRaceReviewBackfillError(
                "historical Review source row has no race_date"
            )
        grouped[race_date].append(row)
    return dict(grouped)


def _asset_root_args(
    values: Sequence[str],
) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(
                "asset root must use FAMILY=/path syntax"
            )
        family, raw_path = value.split("=", 1)
        family = family.strip().upper()
        path = Path(raw_path).expanduser().resolve()
        if family not in {"BAC", "KYI", "SED"}:
            raise ValueError(
                f"unsupported Review asset root: {family}"
            )
        result[family] = path

    missing = {"BAC", "KYI", "SED"} - set(result)
    if missing:
        raise ValueError(
            f"missing Review asset roots: {sorted(missing)}"
        )
    return result


def backfill_historical_warehouse(
    *,
    warehouse_current: Path,
    asset_roots: Mapping[str, Path],
    years: Sequence[int],
    staging_database: Path,
    output_root: Path,
    generation_id: str,
    minimum_standard_sample_count: int = 10,
    minimum_pace_sample_count: int = 10,
    minimum_day_adjustment_race_count: int = 2,
    promote: bool = True,
    complete_snapshot: bool = True,
) -> dict[str, object]:
    """Build and publish one historical Review snapshot from accepted Warehouse."""
    try:
        import duckdb
    except ImportError as exc:
        raise PostRaceReviewBackfillError(
            "historical Review backfill requires duckdb"
        ) from exc

    normalized_years = sorted(set(int(year) for year in years))
    if not normalized_years:
        raise ValueError("at least one backfill year is required")
    if complete_snapshot and normalized_years != list(range(2010, 2026)):
        raise ValueError(
            "v0.1 complete historical snapshot requires exactly 2010-2025"
        )

    staging_database = Path(staging_database).resolve()
    if staging_database.exists():
        raise FileExistsError(staging_database)
    staging_database.parent.mkdir(parents=True, exist_ok=True)

    reader = HistoricalReviewWarehouseReader(
        Path(warehouse_current),
        asset_roots=asset_roots,
    )
    source_generation_id = _text(
        reader.current.get("generation_id")
    )
    if not source_generation_id:
        raise PostRaceReviewBackfillError(
            "accepted Warehouse generation id is missing"
        )

    history = RollingReviewHistory()
    yearly_stats: list[dict[str, object]] = []
    total_days = 0
    total_warnings = 0

    connection = duckdb.connect(str(staging_database))
    try:
        connection.execute(_schema_sql())

        for year in normalized_years:
            year_rows, provenance = reader.read_year(year)
            by_date = _group_by_date(year_rows)

            year_races = 0
            year_horses = 0
            year_bias_rows = 0
            year_warnings = 0

            for race_date in sorted(by_date):
                day_rows = by_date[race_date]
                day_bundle = build_review_day_indexed(
                    day_rows,
                    history,
                    minimum_standard_sample_count=(
                        minimum_standard_sample_count
                    ),
                    minimum_pace_sample_count=(
                        minimum_pace_sample_count
                    ),
                    minimum_day_adjustment_race_count=(
                        minimum_day_adjustment_race_count
                    ),
                )

                horse_rows = day_bundle[
                    "fact_horse_performance"
                ]
                if not isinstance(horse_rows, list):
                    raise AssertionError(
                        "horse Review relation must be a list"
                    )
                bias_rows = build_descriptive_bias_rows(
                    horse_rows
                )
                day_bundle["fact_track_bias"] = bias_rows

                day_audit = audit_review_bundle(
                    day_bundle,
                    expected_target_date=race_date,
                )
                if day_audit["status"] != "PASS":
                    raise PostRaceReviewBackfillError(
                        f"{race_date}: daily Review audit failed: "
                        f"{day_audit['hard_errors']}"
                    )

                for relation in (
                    "fact_race_context",
                    "fact_race_review",
                    "fact_horse_performance",
                    "fact_track_bias",
                ):
                    relation_rows = day_bundle.get(relation)
                    if not isinstance(relation_rows, list):
                        raise AssertionError(
                            f"{relation} must be a list"
                        )
                    _insert_relation_rows(
                        connection,
                        relation,
                        relation_rows,
                    )

                history_samples = day_bundle.get(
                    "history_samples"
                )
                if not isinstance(history_samples, list):
                    raise AssertionError(
                        "history_samples must be a list"
                    )
                history.add_race_samples(history_samples)

                race_rows = day_bundle["fact_race_review"]
                year_races += len(race_rows)
                year_horses += len(horse_rows)
                year_bias_rows += len(bias_rows)
                warning_count = _int(
                    day_audit.get("warning_count")
                ) or 0
                year_warnings += warning_count
                total_warnings += warning_count
                total_days += 1

                if total_days % 100 == 0:
                    print(
                        json.dumps(
                            {
                                "event": "review_backfill_progress",
                                "race_date": race_date,
                                "days": total_days,
                                "prior_race_samples": (
                                    history.race_sample_count
                                ),
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )

            connection.commit()
            yearly_stats.append(
                {
                    "year": year,
                    "source_rows": len(year_rows),
                    "source_races": provenance.get(
                        "race_count"
                    ),
                    "review_races": year_races,
                    "review_horses": year_horses,
                    "track_bias_rows": year_bias_rows,
                    "daily_warning_count": year_warnings,
                }
            )
            print(
                json.dumps(
                    {
                        "event": "review_backfill_year_complete",
                        **yearly_stats[-1],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    finally:
        connection.close()

    source_provenance = {
        "source_mode": "historical_warehouse",
        "warehouse_generation_id": source_generation_id,
        "warehouse_schema_version": reader.current.get(
            "warehouse_schema_version"
        ),
        "years": normalized_years,
        "minimum_standard_sample_count": (
            minimum_standard_sample_count
        ),
        "minimum_pace_sample_count": minimum_pace_sample_count,
        "minimum_day_adjustment_race_count": (
            minimum_day_adjustment_race_count
        ),
    }

    publication = publish_database_snapshot(
        staging_database,
        Path(output_root),
        generation_id,
        source_provenance=source_provenance,
        promote=promote,
        complete_snapshot=complete_snapshot,
    )

    manifest = publication["manifest"]
    audit = publication["audit"]
    return {
        "status": "PASS",
        "generation_id": generation_id,
        "warehouse_generation_id": source_generation_id,
        "years": normalized_years,
        "days_processed": total_days,
        "prior_race_samples": history.race_sample_count,
        "daily_warning_count": total_warnings,
        "yearly_stats": yearly_stats,
        "manifest": manifest,
        "audit": audit,
        "pointer": publication["pointer"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill JRDB Post-Race Review v0.1 from the accepted "
            "Historical Warehouse."
        )
    )
    parser.add_argument(
        "--warehouse-current",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--asset-root",
        action="append",
        default=[],
        metavar="FAMILY=/path",
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        required=True,
    )
    parser.add_argument(
        "--staging-database",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--generation-id",
        required=True,
    )
    parser.add_argument(
        "--minimum-standard-sample-count",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--minimum-pace-sample-count",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--minimum-day-adjustment-race-count",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--promote",
        action="store_true",
    )
    parser.add_argument(
        "--complete-snapshot",
        action="store_true",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
    )
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    asset_roots = _asset_root_args(args.asset_root)

    result = backfill_historical_warehouse(
        warehouse_current=args.warehouse_current,
        asset_roots=asset_roots,
        years=args.years,
        staging_database=args.staging_database,
        output_root=args.output_root,
        generation_id=args.generation_id,
        minimum_standard_sample_count=(
            args.minimum_standard_sample_count
        ),
        minimum_pace_sample_count=(
            args.minimum_pace_sample_count
        ),
        minimum_day_adjustment_race_count=(
            args.minimum_day_adjustment_race_count
        ),
        promote=bool(args.promote),
        complete_snapshot=bool(args.complete_snapshot),
    )

    if args.summary_json is not None:
        args.summary_json.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.summary_json.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "status": result["status"],
                "generation_id": result["generation_id"],
                "warehouse_generation_id": result[
                    "warehouse_generation_id"
                ],
                "days_processed": result["days_processed"],
                "prior_race_samples": result[
                    "prior_race_samples"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
