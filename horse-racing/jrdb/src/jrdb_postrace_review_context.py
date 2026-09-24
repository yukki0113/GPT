#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Race-context builders for JRDB Post-Race Review v0.1."""
from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Mapping

from jrdb_postrace_review import (
    closing_gain_seconds,
    closing_reference_candidate_seconds,
    corner_frontness,
    finish_gap_seconds,
    opening_reference_candidate_seconds,
    pace_balance_seconds,
    position_dynamics,
)
from jrdb_postrace_review_standard import median_absolute_deviation


class PostRaceReviewContextError(RuntimeError):
    """Raised when one race cannot satisfy a deterministic context contract."""


def _finite(value: object) -> float | None:
    """Return a finite float or None."""
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


def _text(value: object) -> str:
    """Return stripped text."""
    if value is None:
        return ""
    return str(value).strip()


def _normal_result(row: Mapping[str, object]) -> bool:
    """Return true when SED abnormal code is normal or blank."""
    code = _text(row.get("abnormal_code"))
    return code in {"", "0"}


def winner_time_seconds(
    rows: Iterable[Mapping[str, object]],
) -> float | None:
    """Return the valid common winning time, including dead-heat handling."""
    winners: list[float] = []
    for row in rows:
        if _int(row.get("finish")) != 1 or not _normal_result(row):
            continue
        time_sec = _finite(row.get("time_sec"))
        if time_sec is None or time_sec <= 0.0:
            continue
        winners.append(time_sec)

    if not winners:
        return None

    minimum = min(winners)
    maximum = max(winners)
    if maximum - minimum > 0.051:
        raise PostRaceReviewContextError(
            "rank-1 SED rows disagree on winning time"
        )
    return float(statistics.median(winners))


def _candidate_summary(values: Iterable[object]) -> dict[str, object]:
    """Return robust reference and dispersion for reconstructed sectionals."""
    cleaned: list[float] = []
    for value in values:
        parsed = _finite(value)
        if parsed is not None and parsed > 0.0:
            cleaned.append(parsed)

    if not cleaned:
        return {
            "reference_sec": None,
            "candidate_count": 0,
            "candidate_mad_sec": None,
        }

    return {
        "reference_sec": float(statistics.median(cleaned)),
        "candidate_count": len(cleaned),
        "candidate_mad_sec": median_absolute_deviation(cleaned),
    }


def reconstruct_race_sectionals(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Reconstruct race-level opening and closing 3F references."""
    materialized = list(rows)
    winner_time = winner_time_seconds(materialized)

    opening_candidates: list[float] = []
    closing_candidates: list[float] = []

    for row in materialized:
        opening = opening_reference_candidate_seconds(
            row.get("first3f_sec"),
            row.get("first3f_leader_diff_sec"),
        )
        if opening is not None:
            opening_candidates.append(opening)

        if winner_time is None:
            continue
        gap = finish_gap_seconds(row.get("time_sec"), winner_time)
        closing = closing_reference_candidate_seconds(
            row.get("last3f_sec"),
            row.get("last3f_leader_diff_sec"),
            gap,
        )
        if closing is not None:
            closing_candidates.append(closing)

    opening_summary = _candidate_summary(opening_candidates)
    closing_summary = _candidate_summary(closing_candidates)
    balance = pace_balance_seconds(
        opening_summary["reference_sec"],
        closing_summary["reference_sec"],
    )

    return {
        "winner_time_sec": winner_time,
        "first3f_reference_sec": opening_summary["reference_sec"],
        "first3f_candidate_count": opening_summary["candidate_count"],
        "first3f_candidate_mad_sec": opening_summary["candidate_mad_sec"],
        "last3f_reference_sec": closing_summary["reference_sec"],
        "last3f_candidate_count": closing_summary["candidate_count"],
        "last3f_candidate_mad_sec": closing_summary["candidate_mad_sec"],
        "pace_balance_sec": balance,
    }


def _last3f_rank_map(
    rows: Iterable[Mapping[str, object]],
) -> tuple[dict[str, int], int]:
    """Return competition ranks for valid last-3F values; smaller is faster."""
    values: list[tuple[str, float]] = []
    for row in rows:
        key = _text(row.get("race_horse_key"))
        last3f = _finite(row.get("last3f_sec"))
        if not key or last3f is None or last3f <= 0.0:
            continue
        values.append((key, last3f))

    values.sort(key=lambda item: (item[1], item[0]))
    ranks: dict[str, int] = {}
    previous_value: float | None = None
    previous_rank = 0

    for index, (key, value) in enumerate(values, start=1):
        rank = index
        if previous_value is not None and math.isclose(
            value,
            previous_value,
            abs_tol=1e-9,
        ):
            rank = previous_rank
        ranks[key] = rank
        previous_value = value
        previous_rank = rank

    return ranks, len(values)


def _speed_percentile(rank: int | None, sample_count: int) -> float | None:
    """Map smaller last3f rank to a high-is-better 0-100 percentile."""
    if rank is None or sample_count <= 0:
        return None
    if sample_count == 1:
        return 100.0
    return 100.0 * float(sample_count - rank) / float(sample_count - 1)


def build_horse_context_rows(
    rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Build threshold-free horse context rows for one race."""
    materialized = list(rows)
    winner_time = winner_time_seconds(materialized)
    ranks, valid_last3f_count = _last3f_rank_map(materialized)

    results: list[dict[str, object]] = []
    for row in materialized:
        field_size = row.get("field_size")
        corners = [
            row.get("corner1_position"),
            row.get("corner2_position"),
            row.get("corner3_position"),
            row.get("corner4_position"),
        ]
        normalized = corner_frontness(corners, field_size)
        dynamics = position_dynamics(
            corners,
            row.get("finish"),
            field_size,
        )

        gap = None
        if winner_time is not None:
            gap = finish_gap_seconds(row.get("time_sec"), winner_time)

        closing_gain = closing_gain_seconds(
            row.get("last3f_leader_diff_sec"),
            gap,
        )
        key = _text(row.get("race_horse_key"))
        last3f_rank = ranks.get(key)

        output = {
            "race_key": row.get("race_key"),
            "race_horse_key": row.get("race_horse_key"),
            "horse_no": row.get("horse_no"),
            "finish": row.get("finish"),
            "time_sec": row.get("time_sec"),
            "winner_gap_sec": gap,
            "first3f_sec": row.get("first3f_sec"),
            "last3f_sec": row.get("last3f_sec"),
            "last3f_rank": last3f_rank,
            "last3f_speed_percentile": _speed_percentile(
                last3f_rank,
                valid_last3f_count,
            ),
            "first3f_leader_diff_sec": row.get("first3f_leader_diff_sec"),
            "last3f_leader_diff_sec": row.get("last3f_leader_diff_sec"),
            "closing_gain_sec": closing_gain,
            "corner1_position": corners[0],
            "corner2_position": corners[1],
            "corner3_position": corners[2],
            "corner4_position": corners[3],
            "corner1_frontness": normalized[0],
            "corner2_frontness": normalized[1],
            "corner3_frontness": normalized[2],
            "corner4_frontness": normalized[3],
        }
        output.update(dynamics)
        results.append(output)

    results.sort(
        key=lambda row: (
            _int(row.get("horse_no")) or 0,
        )
    )
    return results


def build_race_context(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Build one race-level context row from unified Review source rows."""
    materialized = list(rows)
    if not materialized:
        raise PostRaceReviewContextError("race context requires SED rows")

    race_keys = {
        _text(row.get("race_key"))
        for row in materialized
        if _text(row.get("race_key"))
    }
    if len(race_keys) != 1:
        raise PostRaceReviewContextError(
            "race context requires exactly one race_key"
        )

    sectionals = reconstruct_race_sectionals(materialized)
    pace_codes = {
        _text(row.get("race_pace_code"))
        for row in materialized
        if _text(row.get("race_pace_code"))
    }
    pace_code = None
    pace_code_conflict = False
    if len(pace_codes) == 1:
        pace_code = next(iter(pace_codes))
    elif len(pace_codes) > 1:
        pace_code_conflict = True

    first = materialized[0]
    return {
        "race_key": next(iter(race_keys)),
        "race_date": first.get("race_date"),
        "venue_code": first.get("venue_code"),
        "surface_code": first.get("surface_code"),
        "distance_m": first.get("distance_m"),
        "field_size": first.get("field_size"),
        "race_pace_code": pace_code,
        "race_pace_code_conflict": pace_code_conflict,
        **sectionals,
    }
