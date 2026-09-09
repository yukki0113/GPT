#!/usr/bin/env python3
"""Deterministic RaceNote v0.2 reconstructed control frozen on 2026-09-09."""
from __future__ import annotations
from typing import Any, Mapping, Sequence

VERSION = "v0.2-reconstructed-20260909-a"
EPS = 1e-12


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


def _num(v: Any):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def normalized_ordinal(values: Sequence[Any], *, higher_better: bool) -> list[float]:
    """Normalized average-tie ordinal rank; missing gets median available rank.

    Denominator is race field size N-1, matching the frozen control definition.
    """
    n = len(values)
    if n <= 1:
        return [0.5] * n
    avail = [(i, _num(v)) for i, v in enumerate(values) if _num(v) is not None]
    if not avail:
        return [0.5] * n
    sorted_vals = sorted(avail, key=lambda t: t[1], reverse=higher_better)
    ranks = {}
    pos = 1
    j = 0
    while j < len(sorted_vals):
        k = j + 1
        while k < len(sorted_vals) and abs(sorted_vals[k][1] - sorted_vals[j][1]) <= EPS:
            k += 1
        avg = (pos + (pos + (k - j) - 1)) / 2.0
        for ii in range(j, k):
            ranks[sorted_vals[ii][0]] = avg
        pos += k - j
        j = k
    ordered = sorted(ranks.values())
    m = len(ordered)
    median = (ordered[(m - 1) // 2] + ordered[m // 2]) / 2.0
    return [(ranks.get(i, median) - 1.0) / (n - 1.0) for i in range(n)]


def _rate_fraction(v: Any):
    x = _num(v)
    if x is None:
        return None
    return x / 100.0 if x > 1.0 + EPS else x


def _shrunk_top3(row: Mapping[str, Any] | None, prior_n: float) -> float | None:
    if not isinstance(row, Mapping):
        return None
    starts = _num(row.get("starts"))
    rate = _rate_fraction(row.get("top3_rate"))
    if starts is None or starts <= 0 or rate is None:
        return None
    weight = starts / (starts + prior_n)
    return weight * rate + (1 - weight) * 0.33


def frame_fit(bundle: Mapping[str, Any], horse: Mapping[str, Any]) -> float:
    frame_no = horse.get("basic", {}).get("frame_no")
    frame = (bundle.get("race", {}).get("race_trends") or {}).get("frame") or {}
    row = frame.get(str(frame_no)) if frame_no is not None else None
    shrunk = _shrunk_top3(row, 20.0)
    return 0.5 if shrunk is None else clamp(shrunk / 0.45)


def pace_style_fit(horse: Mapping[str, Any], field_size: int) -> float:
    pace = horse.get("pace") or {}
    ability = horse.get("ability") or {}
    forecast = pace.get("forecast_pace")
    style = ability.get("running_style")
    score = 0.5
    if forecast == "ハイ":
        adjustment = {"逃げ": -0.18, "先行": -0.05, "差し": 0.15, "追込": 0.10}
    elif forecast == "スロー":
        adjustment = {"逃げ": 0.22, "先行": 0.14, "差し": -0.08, "追込": -0.18}
    else:
        adjustment = {"逃げ": 0.08, "先行": 0.08, "差し": 0.02, "追込": -0.05}
    score += adjustment.get(style, 0.0)
    mid = ((pace.get("forecast_positions") or {}).get("mid") or {}).get("order")
    mid = _num(mid)
    if style in {"差し", "追込"} and mid is not None and mid > 0.70 * field_size:
        score -= 0.10
    position_rank = _num((pace.get("ranks") or {}).get("position"))
    if position_rank is not None and position_rank <= 3:
        score += 0.08
    if position_rank is not None and position_rank >= max(8, field_size - 2):
        score -= 0.08
    return clamp(score)


_BUCKETS = ["短距離", "マイル", "中距離", "長距離"]


def target_bucket(distance_m: int) -> str:
    if distance_m <= 1400:
        return "短距離"
    if distance_m <= 1800:
        return "マイル"
    if distance_m <= 2200:
        return "中距離"
    return "長距離"


def categorical_distance_compat(horse_fit: Any, distance_m: int) -> float:
    if horse_fit == "万能":
        return 0.90
    if horse_fit not in _BUCKETS:
        return 0.50
    delta = abs(_BUCKETS.index(horse_fit) - _BUCKETS.index(target_bucket(distance_m)))
    return [1.00, 0.55, 0.20, 0.05][min(delta, 3)]


def distance_fit(horse: Mapping[str, Any], distance_m: int) -> tuple[float, bool, str]:
    history = horse.get("historical_profile") or {}
    ability = horse.get("ability") or {}
    same = history.get("same_distance")
    same_starts = _num((same or {}).get("starts")) or 0.0
    categorical = categorical_distance_compat(ability.get("distance_fit"), distance_m)
    contradiction = categorical <= 0.20 + EPS and same_starts <= 0
    shrunk = _shrunk_top3(same, 5.0)
    if shrunk is not None:
        return clamp(shrunk), contradiction, "same_distance"

    ranges = history.get("distance_ranges") or []
    for idx, row in enumerate(ranges):
        starts = _num((row or {}).get("starts")) or 0
        low = _num((row or {}).get("min_m"))
        high = _num((row or {}).get("max_m"))
        if starts > 0 and low is not None and high is not None and low <= distance_m <= high:
            quality = _shrunk_top3(row, 5.0)
            if quality is not None:
                return clamp(quality), contradiction, f"containing_range:{idx}"

    nearest = []
    for idx, row in enumerate(ranges):
        starts = _num((row or {}).get("starts")) or 0
        low = _num((row or {}).get("min_m"))
        high = _num((row or {}).get("max_m"))
        if starts <= 0 or low is None or high is None:
            continue
        gap = low - distance_m if distance_m < low else distance_m - high if distance_m > high else 0
        if 0 < gap <= 400:
            nearest.append((gap, idx, row))
    if nearest:
        nearest.sort(key=lambda x: (x[0], x[1]))
        _, idx, row = nearest[0]
        quality = _shrunk_top3(row, 5.0)
        if quality is not None:
            return clamp(0.85 * quality), contradiction, f"nearby_range:{idx}"

    if ability.get("distance_fit") is not None:
        return categorical, contradiction, "categorical"
    return 0.5, contradiction, "insufficient"


def surface_fit(bundle: Mapping[str, Any], horse: Mapping[str, Any]) -> float:
    surface = bundle.get("race", {}).get("surface")
    key = {"芝": "turf", "ダート": "dirt"}.get(surface)
    mark = ((horse.get("ability") or {}).get("surface_fit") or {}).get(key) if key else None
    return {"◎": 1.0, "○": 0.75, "△": 0.35}.get(mark, 0.5)


def comparable_time(bundle: Mapping[str, Any], horse: Mapping[str, Any]):
    race = bundle.get("race") or {}
    best = None
    for run in horse.get("recent_runs") or []:
        run_race = run.get("race") or {}
        result = run.get("result") or {}
        if (
            run_race.get("venue") == race.get("venue")
            and run_race.get("surface") == race.get("surface")
            and run_race.get("distance_m") == race.get("distance_m")
        ):
            time_sec = _num(result.get("time_sec"))
            if time_sec is not None:
                best = time_sec if best is None else min(best, time_sec)
    return best


def condition_good(horse: Mapping[str, Any]) -> float:
    analysis = ((horse.get("training") or {}).get("analysis") or {})
    values = []
    for key in ("training_index", "condition_index"):
        value = _num(analysis.get(key))
        if value is not None:
            values.append(clamp(value / 100.0))
    base = sum(values) / len(values) if values else 0.5
    arrow = ((horse.get("training") or {}).get("summary") or {}).get("training_arrow")
    base += {"デキ抜群": 0.12, "上昇": 0.07, "平行線": 0.0, "やや下降気味": -0.08}.get(arrow, 0.0)
    return clamp(base)


def score_race_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    horses = list(bundle.get("horses") or [])
    field_size = len(horses)
    if field_size == 0:
        raise ValueError("race bundle has no horses")

    idm_rank = normalized_ordinal([(h.get("ability") or {}).get("idm") for h in horses], higher_better=True)
    total_rank = normalized_ordinal(
        [(h.get("ability") or {}).get("total_index") for h in horses], higher_better=True
    )
    recent_average = []
    for horse in horses:
        values = []
        for run in (horse.get("recent_runs") or [])[:3]:
            value = _num((run.get("performance") or {}).get("idm"))
            if value is not None:
                values.append(value)
        recent_average.append(sum(values) / len(values) if values else None)
    recent_rank = normalized_ordinal(recent_average, higher_better=True)

    forecast_orders = [
        ((h.get("pace") or {}).get("forecast_positions") or {}).get("finish", {}).get("order") for h in horses
    ]
    forecast_rank = normalized_ordinal(forecast_orders, higher_better=False)

    raw_times = [comparable_time(bundle, horse) for horse in horses]
    comparable = sum(time is not None for time in raw_times)
    if comparable >= 3:
        time_rank = normalized_ordinal(raw_times, higher_better=False)
        time_goods = [0.5 if time is None else 1 - rank for time, rank in zip(raw_times, time_rank)]
    else:
        time_goods = [0.5] * field_size

    rows = []
    distance_m = int(bundle["race"]["distance_m"])
    for idx, horse in enumerate(horses):
        ability_rank = (idm_rank[idx] + total_rank[idx] + recent_rank[idx]) / 3
        ability_good = 1 - ability_rank
        frame = frame_fit(bundle, horse)
        pace = pace_style_fit(horse, field_size)
        distance, contradiction, distance_source = distance_fit(horse, distance_m)
        surface = surface_fit(bundle, horse)
        time = time_goods[idx]
        suitability = 0.18 * frame + 0.25 * pace + 0.30 * distance + 0.12 * surface + 0.15 * time
        condition = condition_good(horse)
        forecast_good = 1 - forecast_rank[idx]
        good = 0.42 * ability_good + 0.38 * suitability + 0.10 * condition + 0.10 * forecast_good
        if contradiction:
            good -= 0.08
        weak_ability = ability_rank > 0.60 + EPS
        if weak_ability:
            good -= 0.05
        basic = horse.get("basic") or {}
        rows.append(
            {
                "horse_no": int(basic["horse_no"]),
                "horse_name": basic.get("horse_name"),
                "frame_no": basic.get("frame_no"),
                "good": good,
                "ability_good": ability_good,
                "ability_rank": ability_rank,
                "suitability_good": suitability,
                "condition_good": condition,
                "forecast_good": forecast_good,
                "frame_fit": frame,
                "pace_style_fit": pace,
                "distance_fit": distance,
                "distance_fit_source": distance_source,
                "surface_fit": surface,
                "time_fit": time,
                "comparable_time_sec": raw_times[idx],
                "distance_contradiction": contradiction,
                "weak_ability_penalty": weak_ability,
            }
        )

    rows.sort(key=lambda row: (-row["good"], row["horse_no"]))
    marks = ["◎", "○", "▲", "△1", "△2"]
    top_five = []
    for idx, row in enumerate(rows[:5]):
        selected = dict(row)
        selected["base_rank"] = idx + 1
        selected["mark"] = marks[idx]
        top_five.append(selected)

    gap = top_five[0]["good"] - top_five[1]["good"] if len(top_five) > 1 else 1.0
    p1 = top_five[0]
    if gap < 0.015 - EPS or p1["distance_contradiction"]:
        confidence = "C"
    elif (
        gap >= 0.040 - EPS
        and p1["ability_good"] >= 0.60 - EPS
        and p1["suitability_good"] >= 0.55 - EPS
    ):
        confidence = "A"
    else:
        confidence = "B"

    return {
        "control_version": VERSION,
        "result_data_used": False,
        "race": {
            "date": bundle["race"]["date"],
            "venue": bundle["race"]["venue"],
            "race_no": bundle["race"]["race_no"],
            "surface": bundle["race"]["surface"],
            "distance_m": distance_m,
            "field_size": field_size,
        },
        "confidence": confidence,
        "p1_p2_good_gap": gap,
        "top5": top_five,
        "runners": rows,
    }
