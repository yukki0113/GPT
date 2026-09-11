#!/usr/bin/env python3
"""Deterministic evidence extraction for RaceNote Newspaper presentation comments.

This module does not rank horses and does not alter RaceNote marks.  It converts
an already-frozen prediction plus its authoritative pre-race RaceNote bundle
into a compact, auditable brief for natural-language presentation.

The natural-language renderer (GPT or another presentation renderer) must use
only this brief and must not feed generated prose back into prediction logic.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

VERSION = "racenote-presentation-evidence-0.1"
TOP_MARKS = ("◎", "○", "▲")

SCORE_AXES = (
    ("ability", "ability_good"),
    ("suitability", "suitability_good"),
    ("pace_fit", "pace_style_fit"),
    ("condition", "condition_good"),
    ("distance_fit", "distance_fit"),
    ("forecast", "forecast_good"),
)


def _num(value: Any) -> float | None:
    """Return a numeric value or None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _horse_no(horse: Mapping[str, Any]) -> int:
    """Return canonical horse number from one RaceNote horse object."""
    return int((horse.get("basic") or {})["horse_no"])


def _find_horse(bundle: Mapping[str, Any], horse_no: int) -> Mapping[str, Any]:
    """Find one horse in the authoritative RaceNote bundle."""
    found = [horse for horse in bundle.get("horses") or [] if _horse_no(horse) == horse_no]
    if len(found) != 1:
        raise ValueError(f"horse_no {horse_no}: expected exactly one bundle horse, found {len(found)}")
    return found[0]


def _score_rows(prediction: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    """Return frozen scorer rows keyed by horse number."""
    control = prediction.get("v0_2_control") or {}
    rows = control.get("all_runners") or control.get("runners") or []
    mapped: dict[int, Mapping[str, Any]] = {}
    for row in rows:
        horse_no = int(row["horse_no"])
        if horse_no in mapped:
            raise ValueError(f"duplicate scorer horse_no: {horse_no}")
        mapped[horse_no] = row
    if not mapped:
        raise ValueError("prediction does not contain v0_2_control all_runners/runners")
    return mapped


def _top_three_marks(prediction: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return ◎○▲ in mark order from the frozen candidate prediction."""
    candidate = prediction.get("v1_1_P_candidate") or {}
    marks = candidate.get("marks") or []
    by_mark: dict[str, dict[str, Any]] = {}
    for row in marks:
        mark = str(row.get("mark") or "")
        if mark in TOP_MARKS:
            if mark in by_mark:
                raise ValueError(f"duplicate top mark: {mark}")
            by_mark[mark] = dict(row)
    missing = [mark for mark in TOP_MARKS if mark not in by_mark]
    if missing:
        raise ValueError(f"prediction is missing top marks: {missing}")
    return [by_mark[mark] for mark in TOP_MARKS]


def _position_order(horse: Mapping[str, Any], key: str) -> float | None:
    """Return a forecast position order if present."""
    positions = ((horse.get("pace") or {}).get("forecast_positions") or {}).get(key) or {}
    return _num(positions.get("order"))


def _observations(horse: Mapping[str, Any], score: Mapping[str, Any]) -> dict[str, Any]:
    """Extract raw pre-race observations useful for presentation."""
    ability = horse.get("ability") or {}
    pace = horse.get("pace") or {}
    training = horse.get("training") or {}
    training_analysis = training.get("analysis") or {}
    training_summary = training.get("summary") or {}
    return {
        "idm": _num(ability.get("idm")),
        "total_index": _num(ability.get("total_index")),
        "running_style": ability.get("running_style"),
        "distance_fit_label": ability.get("distance_fit"),
        "forecast_pace": pace.get("forecast_pace"),
        "forecast_mid_order": _position_order(horse, "mid"),
        "forecast_finish_order": _position_order(horse, "finish"),
        "training_index": _num(training_analysis.get("training_index")),
        "condition_index": _num(training_analysis.get("condition_index")),
        "training_arrow": training_summary.get("training_arrow"),
        "volume_grade": training_summary.get("volume_grade"),
        "good": _num(score.get("good")),
        "ability_good": _num(score.get("ability_good")),
        "suitability_good": _num(score.get("suitability_good")),
        "pace_style_fit": _num(score.get("pace_style_fit")),
        "condition_good": _num(score.get("condition_good")),
        "distance_fit": _num(score.get("distance_fit")),
        "forecast_good": _num(score.get("forecast_good")),
        "distance_contradiction": bool(score.get("distance_contradiction")),
    }


def _rank_numeric(
    values: Sequence[tuple[int, float | None]],
    horse_no: int,
    *,
    higher_better: bool,
) -> dict[str, Any] | None:
    """Rank one horse among top three for a numeric observation."""
    available = [(number, value) for number, value in values if value is not None]
    if len(available) < 2:
        return None
    ordered = sorted(
        available,
        key=lambda item: ((-item[1]) if higher_better else item[1], item[0]),
    )
    target = next((value for number, value in available if number == horse_no), None)
    if target is None:
        return None
    rank = 1 + sum(
        1
        for _, value in available
        if (value > target if higher_better else value < target)
    )
    best = ordered[0][1]
    return {
        "rank_among_top3": rank,
        "available_count": len(available),
        "best_value": best,
        "is_best": rank == 1,
    }


def _relative_context(top_payloads: Sequence[dict[str, Any]]) -> None:
    """Attach deterministic top-three relative comparisons in place."""
    fields = (
        ("idm", True),
        ("total_index", True),
        ("training_index", True),
        ("condition_index", True),
        ("forecast_finish_order", False),
        ("ability_good", True),
        ("suitability_good", True),
        ("pace_style_fit", True),
        ("condition_good", True),
        ("distance_fit", True),
        ("forecast_good", True),
    )
    for field, higher_better in fields:
        values = [
            (int(item["horse_no"]), _num(item["observations"].get(field)))
            for item in top_payloads
        ]
        for item in top_payloads:
            relative = _rank_numeric(
                values,
                int(item["horse_no"]),
                higher_better=higher_better,
            )
            if relative is not None:
                item["relative"][field] = relative


def _axis_labels(item: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Derive compact strength/risk axis labels without generating prose."""
    relative = item.get("relative") or {}
    observations = item.get("observations") or {}
    strengths: list[str] = []
    risks: list[str] = []

    if (relative.get("idm") or {}).get("is_best") or (relative.get("total_index") or {}).get("is_best"):
        strengths.append("ability")
    if (relative.get("training_index") or {}).get("is_best") or (relative.get("condition_index") or {}).get("is_best"):
        strengths.append("training_condition")
    if (relative.get("forecast_finish_order") or {}).get("is_best") or (relative.get("pace_style_fit") or {}).get("is_best"):
        strengths.append("pace_position")
    if (relative.get("distance_fit") or {}).get("is_best"):
        strengths.append("distance_fit")
    if (relative.get("suitability_good") or {}).get("is_best"):
        strengths.append("overall_suitability")

    if observations.get("distance_contradiction"):
        risks.append("distance_contradiction")
    arrow = observations.get("training_arrow")
    if arrow in {"やや下降気味", "下降"}:
        risks.append("training_down")
    if (relative.get("idm") or {}).get("rank_among_top3") == 3 and (relative.get("total_index") or {}).get("rank_among_top3") == 3:
        risks.append("ability_below_other_top3")
    if (relative.get("condition_index") or {}).get("rank_among_top3") == 3:
        risks.append("condition_below_other_top3")

    return list(dict.fromkeys(strengths)), list(dict.fromkeys(risks))


def build_horse_briefs(
    bundle: Mapping[str, Any],
    prediction: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build structured ◎○▲ briefs from frozen prediction + pre-race bundle."""
    score_rows = _score_rows(prediction)
    top_marks = _top_three_marks(prediction)
    payloads: list[dict[str, Any]] = []

    for rank, mark_row in enumerate(top_marks, 1):
        horse_no = int(mark_row["horse_no"])
        horse = _find_horse(bundle, horse_no)
        score = score_rows.get(horse_no)
        if score is None:
            raise ValueError(f"horse_no {horse_no}: scorer row missing")
        basic = horse.get("basic") or {}
        payloads.append(
            {
                "mark": TOP_MARKS[rank - 1],
                "prediction_rank": rank,
                "horse_no": horse_no,
                "horse_name": basic.get("horse_name"),
                "observations": _observations(horse, score),
                "relative": {},
            }
        )

    _relative_context(payloads)
    for item in payloads:
        strengths, risks = _axis_labels(item)
        item["strength_axes"] = strengths
        item["risk_axes"] = risks
        item["rendering_role"] = {
            "◎": "explain_why_best",
            "○": "explain_difference_from_axis_and_upside",
            "▲": "explain_why_below_top_two_and_path_to_outperform",
        }[item["mark"]]
    return payloads


def _mode(values: Sequence[str]) -> str | None:
    """Return deterministic mode; lexical tie-break."""
    if not values:
        return None
    counts = Counter(values)
    highest = max(counts.values())
    return sorted(value for value, count in counts.items() if count == highest)[0]


def _style_counts(bundle: Mapping[str, Any]) -> dict[str, int]:
    """Count common running styles in the full field."""
    counts = Counter(
        str((horse.get("ability") or {}).get("running_style") or "不明")
        for horse in bundle.get("horses") or []
    )
    return dict(sorted(counts.items()))


def _selection_priorities(
    prediction: Mapping[str, Any],
    top_horse_nos: set[int],
) -> list[dict[str, Any]]:
    """Rank axes by how strongly top three separate from the full field."""
    rows = list(_score_rows(prediction).values())
    priorities: list[dict[str, Any]] = []
    for label, field in SCORE_AXES:
        field_values = [(int(row["horse_no"]), _num(row.get(field))) for row in rows]
        top = [
            value
            for horse_no, value in field_values
            if horse_no in top_horse_nos and value is not None
        ]
        field_all = [value for _, value in field_values if value is not None]
        if not top or not field_all:
            continue
        top_mean = sum(top) / len(top)
        field_mean = sum(field_all) / len(field_all)
        priorities.append(
            {
                "axis": label,
                "top3_mean": round(top_mean, 6),
                "field_mean": round(field_mean, 6),
                "top3_minus_field": round(top_mean - field_mean, 6),
            }
        )
    priorities.sort(key=lambda row: (-row["top3_minus_field"], row["axis"]))
    return priorities[:3]


def build_race_brief(
    bundle: Mapping[str, Any],
    prediction: Mapping[str, Any],
    horse_briefs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build one structured race-level comment brief."""
    if horse_briefs is None:
        horse_briefs = build_horse_briefs(bundle, prediction)
    top_horse_nos = {int(item["horse_no"]) for item in horse_briefs}

    pace_values = [
        str((horse.get("pace") or {}).get("forecast_pace"))
        for horse in bundle.get("horses") or []
        if (horse.get("pace") or {}).get("forecast_pace")
    ]
    styles = _style_counts(bundle)
    field_size = max(1, len(bundle.get("horses") or []))
    forward_count = styles.get("逃げ", 0) + styles.get("先行", 0)
    forward_ratio = forward_count / field_size
    if forward_ratio >= 0.50:
        front_pressure = "HIGH"
    elif forward_ratio <= 0.25:
        front_pressure = "LOW"
    else:
        front_pressure = "MEDIUM"

    control = prediction.get("v0_2_control") or {}
    candidate = prediction.get("v1_1_P_candidate") or {}
    confidence = candidate.get("confidence") or control.get("confidence")
    good_gap = _num(control.get("p1_p2_good_gap"))

    risks: list[str] = []
    if confidence == "C":
        risks.append("low_prediction_confidence")
    if good_gap is not None and good_gap < 0.015:
        risks.append("axis_good_gap_small")
    top_styles = [
        item["observations"].get("running_style")
        for item in horse_briefs
        if item.get("observations")
    ]
    known_top_styles = [style for style in top_styles if style]
    if len(known_top_styles) == 3 and len(set(known_top_styles)) == 1:
        risks.append("top3_same_running_style")
    if any((item.get("observations") or {}).get("distance_contradiction") for item in horse_briefs):
        risks.append("top3_distance_contradiction")

    race = bundle.get("race") or {}
    return {
        "race": {
            "date": race.get("date"),
            "venue": race.get("venue"),
            "race_no": race.get("race_no"),
            "surface": race.get("surface"),
            "distance_m": race.get("distance_m"),
            "field_size": field_size,
        },
        "pace": {
            "forecast_mode": _mode(pace_values),
            "style_counts": styles,
            "front_pressure": front_pressure,
        },
        "selection_priorities": _selection_priorities(prediction, top_horse_nos),
        "risk_flags": list(dict.fromkeys(risks)),
        "top3_roles": [
            {
                "mark": item["mark"],
                "horse_no": item["horse_no"],
                "horse_name": item["horse_name"],
                "strength_axes": list(item.get("strength_axes") or []),
                "risk_axes": list(item.get("risk_axes") or []),
            }
            for item in horse_briefs
        ],
        "rendering_contract": {
            "required_content": ["pace_read", "selection_method"],
            "optional_content_when_material": ["race_specific_risk"],
            "forbidden": [
                "invented_evidence",
                "result_data",
                "final_odds_or_popularity",
                "generic_fixed_sentence_selected_only_by_pace_class",
            ],
        },
    }


def build_presentation_brief(
    bundle: Mapping[str, Any],
    prediction: Mapping[str, Any],
) -> dict[str, Any]:
    """Return complete deterministic evidence for race and horse comments."""
    horse_briefs = build_horse_briefs(bundle, prediction)
    return {
        "version": VERSION,
        "result_data_used": False,
        "race_comment_brief": build_race_brief(bundle, prediction, horse_briefs),
        "horse_comment_briefs": horse_briefs,
    }
