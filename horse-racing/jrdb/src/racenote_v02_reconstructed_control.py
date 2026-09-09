#!/usr/bin/env python3
"""Deterministic RaceNote v0.2 reconstructed control scorer.

This implements the semantics frozen in
RaceNote_v1_0_Control_Reconstruction_Freeze_20260909.md for the control named
``v0.2-reconstructed-20260909-a``.

It is a prediction/evaluation helper. It does not mutate RaceNote data, discover
Edge conditions, acquire result data, or use target-race final odds/popularity.
"""
from __future__ import annotations

import math
import statistics
from typing import Any, Mapping, Sequence

VERSION = "v0.2-reconstructed-20260909-a"

PACE_ADJUSTMENTS = {
    "high": {"逃げ": -0.18, "先行": -0.05, "差し": 0.15, "追込": 0.10},
    "slow": {"逃げ": 0.22, "先行": 0.14, "差し": -0.08, "追込": -0.18},
    "average": {"逃げ": 0.08, "先行": 0.08, "差し": 0.02, "追込": -0.05},
}
SURFACE_MARK = {"◎": 1.00, "○": 0.75, "△": 0.35}
TRAINING_ARROW = {"デキ抜群": 0.12, "上昇": 0.07, "平行線": 0.0, "やや下降気味": -0.08}
DISTANCE_BUCKETS = ("短距離", "マイル", "中距離", "長距離")
EPS = 1e-12


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def normalized_ordinal_ranks(
    values: Sequence[Any],
    *,
    higher_is_better: bool,
) -> list[float]:
    """Return normalized ordinal ranks on the frozen race-field denominator.

    Available observations receive average tie ranks. Missing observations
    receive the median raw rank among available observations. If every value is
    missing, every row is neutral 0.5.
    """
    count = len(values)
    if count == 0:
        return []
    if count == 1:
        return [0.5]

    available = [(index, _number(value)) for index, value in enumerate(values)]
    available = [(index, value) for index, value in available if value is not None]
    if not available:
        return [0.5] * count

    ordered = sorted(available, key=lambda item: item[1], reverse=higher_is_better)
    raw_ranks: dict[int, float] = {}
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and abs(ordered[end][1] - ordered[cursor][1]) <= EPS:
            end += 1
        average_rank = ((cursor + 1) + end) / 2.0
        for slot in range(cursor, end):
            raw_ranks[ordered[slot][0]] = average_rank
        cursor = end

    missing_rank = statistics.median(raw_ranks.values())
    return [
        (raw_ranks.get(index, missing_rank) - 1.0) / (count - 1.0)
        for index in range(count)
    ]


def _recent_idm_mean(horse: Mapping[str, Any]) -> float | None:
    values: list[float] = []
    for run in list(horse.get("recent_runs") or [])[:3]:
        value = _number((run.get("performance") or {}).get("idm"))
        if value is not None:
            values.append(value)
    return sum(values) / len(values) if values else None


def _frame_fit(race: Mapping[str, Any], horse: Mapping[str, Any]) -> float:
    frame_no = str((horse.get("basic") or {}).get("frame_no"))
    frame = (((race.get("race_trends") or {}).get("frame") or {}).get(frame_no))
    if not isinstance(frame, Mapping):
        return 0.5
    starts = _number(frame.get("starts")) or 0.0
    rate = _number(frame.get("top3_rate"))
    if starts <= 0 or rate is None:
        return 0.5
    if rate > 1.0:
        rate /= 100.0
    weight = starts / (starts + 20.0)
    shrunk = weight * rate + (1.0 - weight) * 0.33
    return _clamp(shrunk / 0.45)


def _pace_group(raw: Any) -> str:
    text = str(raw or "").strip().upper()
    if text in {"ハイ", "H", "HIGH"}:
        return "high"
    if text in {"スロー", "S", "SLOW"}:
        return "slow"
    return "average"


def _pace_style_fit(race: Mapping[str, Any], horse: Mapping[str, Any]) -> float:
    field_size = int(race.get("field_size") or 0)
    style = (horse.get("ability") or {}).get("running_style")
    pace = horse.get("pace") or {}
    value = 0.5 + PACE_ADJUSTMENTS[_pace_group(pace.get("forecast_pace"))].get(style, 0.0)

    mid_order = _number(((pace.get("forecast_positions") or {}).get("mid") or {}).get("order"))
    if style in {"差し", "追込"} and mid_order is not None and field_size > 0:
        if mid_order > 0.70 * field_size:
            value -= 0.10

    position_rank = _number((pace.get("ranks") or {}).get("position"))
    if position_rank is not None:
        if position_rank <= 3:
            value += 0.08
        if position_rank >= max(8, field_size - 2):
            value -= 0.08
    return _clamp(value)


def _distance_bucket(distance_m: float | None) -> str | None:
    if distance_m is None:
        return None
    if distance_m <= 1400:
        return "短距離"
    if distance_m <= 1800:
        return "マイル"
    if distance_m <= 2200:
        return "中距離"
    return "長距離"


def _distance_compatibility(label: Any, target_bucket: str | None) -> float:
    text = str(label or "").strip()
    if text == "万能":
        return 0.90
    if text not in DISTANCE_BUCKETS or target_bucket not in DISTANCE_BUCKETS:
        return 0.50
    gap = abs(DISTANCE_BUCKETS.index(text) - DISTANCE_BUCKETS.index(target_bucket))
    return {0: 1.00, 1: 0.55, 2: 0.20, 3: 0.05}[gap]


def _shrunk_top3(row: Mapping[str, Any] | None) -> float | None:
    if not isinstance(row, Mapping):
        return None
    starts = _number(row.get("starts")) or 0.0
    rate = _number(row.get("top3_rate"))
    if starts <= 0 or rate is None:
        return None
    if rate > 1.0:
        rate /= 100.0
    weight = starts / (starts + 5.0)
    return weight * rate + (1.0 - weight) * 0.33


def _range_gap(row: Mapping[str, Any], target_m: float) -> float:
    lower = _number(row.get("min_m"))
    upper = _number(row.get("max_m"))
    lower_bound = -math.inf if lower is None else lower
    upper_bound = math.inf if upper is None else upper
    if lower_bound <= target_m <= upper_bound:
        return 0.0
    distances = []
    if math.isfinite(lower_bound):
        distances.append(abs(target_m - lower_bound))
    if math.isfinite(upper_bound):
        distances.append(abs(target_m - upper_bound))
    return min(distances) if distances else math.inf


def _distance_fit(
    race: Mapping[str, Any],
    horse: Mapping[str, Any],
) -> tuple[float, bool, str]:
    target_m = _number(race.get("distance_m"))
    profile = horse.get("historical_profile") or {}
    same_distance = profile.get("same_distance") or {}
    compatibility = _distance_compatibility(
        (horse.get("ability") or {}).get("distance_fit"),
        _distance_bucket(target_m),
    )
    same_starts = _number(same_distance.get("starts")) or 0.0
    contradiction = compatibility <= 0.20 and same_starts == 0

    direct = _shrunk_top3(same_distance)
    if direct is not None:
        return _clamp(direct), contradiction, "same_distance"

    ranges = list(profile.get("distance_ranges") or [])
    if target_m is not None:
        for row in ranges:
            if isinstance(row, Mapping) and _range_gap(row, target_m) == 0:
                quality = _shrunk_top3(row)
                if quality is not None:
                    return _clamp(quality), contradiction, "containing_range"

        nearby: list[tuple[float, int, float]] = []
        for index, row in enumerate(ranges):
            if not isinstance(row, Mapping):
                continue
            quality = _shrunk_top3(row)
            if quality is None:
                continue
            gap = _range_gap(row, target_m)
            if gap <= 400:
                nearby.append((gap, index, quality))
        if nearby:
            _, _, quality = min(nearby, key=lambda item: (item[0], item[1]))
            return _clamp(0.85 * quality), contradiction, "nearby_range"

    return _clamp(compatibility), contradiction, "categorical"


def _surface_fit(race: Mapping[str, Any], horse: Mapping[str, Any]) -> float:
    surface = race.get("surface")
    key = "turf" if surface == "芝" else "dirt" if surface == "ダート" else None
    marks = (horse.get("ability") or {}).get("surface_fit") or {}
    return SURFACE_MARK.get(marks.get(key) if key else None, 0.5)


def comparable_time_fit(
    race: Mapping[str, Any],
    horses: Sequence[Mapping[str, Any]],
) -> list[float]:
    """Return frozen TimeFit values.

    Only exact venue+surface+distance recent-run times are comparable. At least
    three horses need a comparable observation. Comparable horses are ranked
    against each other, but the normalized-rank denominator remains the full
    race field N-1, as required by the general normalized-rank freeze. Horses
    without a comparable time stay exactly neutral 0.5.
    """
    count = len(horses)
    if count <= 1:
        return [0.5] * count

    venue = race.get("venue")
    surface = race.get("surface")
    distance_m = race.get("distance_m")
    fastest: list[float | None] = []
    for horse in horses:
        times: list[float] = []
        for run in list(horse.get("recent_runs") or []):
            run_race = run.get("race") or {}
            if (
                run_race.get("venue") == venue
                and run_race.get("surface") == surface
                and run_race.get("distance_m") == distance_m
            ):
                value = _number((run.get("result") or {}).get("time_sec"))
                if value is not None:
                    times.append(value)
        fastest.append(min(times) if times else None)

    available = [index for index, value in enumerate(fastest) if value is not None]
    if len(available) < 3:
        return [0.5] * count

    ordered = sorted(available, key=lambda index: fastest[index])
    raw_ranks: dict[int, float] = {}
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while (
            end < len(ordered)
            and abs(float(fastest[ordered[end]]) - float(fastest[ordered[cursor]])) <= EPS
        ):
            end += 1
        average_rank = ((cursor + 1) + end) / 2.0
        for slot in range(cursor, end):
            raw_ranks[ordered[slot]] = average_rank
        cursor = end

    values = [0.5] * count
    for index, raw_rank in raw_ranks.items():
        normalized_rank = (raw_rank - 1.0) / (count - 1.0)
        values[index] = 1.0 - normalized_rank
    return values


def _condition_score(horse: Mapping[str, Any]) -> float:
    analysis = (horse.get("training") or {}).get("analysis") or {}
    components: list[float] = []
    for key in ("training_index", "condition_index"):
        value = _number(analysis.get(key))
        if value is not None:
            components.append(_clamp(value / 100.0))
    score = sum(components) / len(components) if components else 0.5
    arrow = ((horse.get("training") or {}).get("summary") or {}).get("training_arrow")
    return _clamp(score + TRAINING_ARROW.get(arrow, 0.0))


def score_race_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Score one RaceNote v1.0 race bundle under the frozen reconstructed control."""
    race = bundle.get("race")
    horses = bundle.get("horses")
    if not isinstance(race, Mapping) or not isinstance(horses, list) or not horses:
        raise ValueError("RaceNote bundle requires race object and non-empty horses list")
    if any(not isinstance(horse, Mapping) for horse in horses):
        raise ValueError("RaceNote horses entries must be objects")

    field_size = int(race.get("field_size") or len(horses))
    if field_size != len(horses):
        raise ValueError(f"field_size mismatch: race={field_size} horses={len(horses)}")

    horse_numbers = [int((horse.get("basic") or {}).get("horse_no")) for horse in horses]
    if len(set(horse_numbers)) != len(horse_numbers) or any(number <= 0 for number in horse_numbers):
        raise ValueError("horse_no must be unique positive integers")

    idm_rank = normalized_ordinal_ranks(
        [(horse.get("ability") or {}).get("idm") for horse in horses],
        higher_is_better=True,
    )
    total_rank = normalized_ordinal_ranks(
        [(horse.get("ability") or {}).get("total_index") for horse in horses],
        higher_is_better=True,
    )
    recent_rank = normalized_ordinal_ranks(
        [_recent_idm_mean(horse) for horse in horses],
        higher_is_better=True,
    )
    ability_rank = [
        (idm_rank[index] + total_rank[index] + recent_rank[index]) / 3.0
        for index in range(len(horses))
    ]
    ability_good = [1.0 - value for value in ability_rank]

    forecast_rank = normalized_ordinal_ranks(
        [
            (((horse.get("pace") or {}).get("forecast_positions") or {}).get("finish") or {}).get("order")
            for horse in horses
        ],
        higher_is_better=False,
    )
    forecast_good = [1.0 - value for value in forecast_rank]
    time_fit = comparable_time_fit(race, horses)

    rows: list[dict[str, Any]] = []
    for index, horse in enumerate(horses):
        frame_fit = _frame_fit(race, horse)
        pace_style_fit = _pace_style_fit(race, horse)
        distance_fit, contradiction, distance_evidence = _distance_fit(race, horse)
        surface_fit = _surface_fit(race, horse)
        suitability_good = (
            0.18 * frame_fit
            + 0.25 * pace_style_fit
            + 0.30 * distance_fit
            + 0.12 * surface_fit
            + 0.15 * time_fit[index]
        )
        condition = _condition_score(horse)
        good = (
            0.42 * ability_good[index]
            + 0.38 * suitability_good
            + 0.10 * condition
            + 0.10 * forecast_good[index]
        )
        if contradiction:
            good -= 0.08
        weak_ability = ability_rank[index] > 0.60
        if weak_ability:
            good -= 0.05

        basic = horse.get("basic") or {}
        rows.append(
            {
                "horse_no": int(basic["horse_no"]),
                "horse_name": basic.get("horse_name"),
                "good": _clamp(good),
                "ability_good": ability_good[index],
                "ability_rank": ability_rank[index],
                "suitability_good": suitability_good,
                "condition": condition,
                "forecast_good": forecast_good[index],
                "frame_fit": frame_fit,
                "pace_style_fit": pace_style_fit,
                "distance_fit": distance_fit,
                "distance_evidence": distance_evidence,
                "surface_fit": surface_fit,
                "time_fit": time_fit[index],
                "distance_contradiction": contradiction,
                "weak_ability_penalty": weak_ability,
            }
        )

    rows.sort(key=lambda row: (-row["good"], row["horse_no"]))
    gap = rows[0]["good"] - rows[1]["good"] if len(rows) >= 2 else math.inf
    p1 = rows[0]
    if gap < 0.015 or p1["distance_contradiction"]:
        confidence = "C"
    elif (
        gap >= 0.040
        and p1["ability_good"] >= 0.60
        and p1["suitability_good"] >= 0.55
        and not p1["distance_contradiction"]
    ):
        confidence = "A"
    else:
        confidence = "B"

    return {
        "control_version": VERSION,
        "result_data_used": False,
        "race": {
            "date": race.get("date"),
            "venue": race.get("venue"),
            "race_no": race.get("race_no"),
            "field_size": field_size,
        },
        "confidence": confidence,
        "rows": rows,
        "top_five": rows[:5],
    }
