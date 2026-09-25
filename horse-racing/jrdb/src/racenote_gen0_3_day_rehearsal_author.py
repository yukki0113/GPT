#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Author and validate one blind RaceNote Gen0.3 day rehearsal.

This module is deliberately rehearsal-only. It does not replace the normal
GPT-authored single-race path. It applies one deterministic qualitative author
profile across every prepared race so an entire day can be frozen before any
result is opened.
"""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from racenote_all_runner_synthesis import (
    semantic_sha256 as synthesis_sha256,
    validate_all_runner_synthesis,
)
from racenote_pairwise_comparison import (
    required_pair_keys,
    semantic_sha256 as pairwise_sha256,
    validate_pairwise_comparison_from_synthesis,
)
from racenote_scenario_robustness import (
    semantic_sha256 as scenario_sha256,
    validate_scenario_robustness,
)
from racenote_forecast_gen0_3 import (
    audit_frozen_forecast,
    freeze_forecast,
    semantic_sha256 as forecast_sha256,
    validate_forecast,
)

PROFILE_VERSION = "DayRehearsal-v0.1"

TREND_ORDER = {
    "SUPPORTIVE": 4,
    "MIXED": 3,
    "NEUTRAL_OR_UNKNOWN": 2,
    "OPPOSED": 1,
    "INSUFFICIENT": 0,
}
REVIEW_ORDER = {
    "HIDDEN_STRENGTH": 6,
    "SUPPORTIVE": 5,
    "MIXED": 4,
    "MIXED_CONTEXT_ONLY": 3,
    "INSUFFICIENT": 2,
    "CAUTION": 1,
    "FRAGILE_FORM": 0,
}


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []


def _horse_index(general: Mapping[str, object]) -> dict[int, Mapping[str, object]]:
    result: dict[int, Mapping[str, object]] = {}
    for raw in _as_list(general.get("horses")):
        horse = _as_mapping(raw)
        horse_no = int(horse["horse_no"])
        result[horse_no] = horse
    return result


def _states(horse: Mapping[str, object]) -> tuple[str, str]:
    interpretation = _as_mapping(horse.get("prediction_interpretation"))
    trend = _as_mapping(interpretation.get("data_trend"))
    review = _as_mapping(interpretation.get("racereview"))
    return (
        _text(trend.get("state")).upper(),
        _text(review.get("state")).upper(),
    )


def _ability_profile(horse: Mapping[str, object]) -> dict[str, float | None]:
    interpretation = _as_mapping(horse.get("prediction_interpretation"))
    ability = _as_mapping(interpretation.get("ability_anchor"))
    profile = _as_mapping(ability.get("profile"))

    output: dict[str, float | None] = {}
    for key in ("typical_median", "latest", "peak", "minimum", "mad"):
        raw = profile.get(key)
        if raw is None:
            output[key] = None
        else:
            output[key] = float(raw)
    return output


def _ability_key(horse: Mapping[str, object]) -> tuple[float, float, float, float]:
    profile = _ability_profile(horse)

    def value(key: str, default: float) -> float:
        raw = profile.get(key)
        if raw is None:
            return default
        return float(raw)

    return (
        value("typical_median", -9999.0),
        value("latest", -9999.0),
        value("peak", -9999.0),
        -value("mad", 9999.0),
    )


def _author_order(general: Mapping[str, object]) -> list[int]:
    """Qualitative lexicographic author order; no additive score is used."""
    index = _horse_index(general)

    def key(horse_no: int) -> tuple[object, ...]:
        horse = index[horse_no]
        trend_state, review_state = _states(horse)
        return (
            -TREND_ORDER.get(trend_state, 0),
            -REVIEW_ORDER.get(review_state, 2),
            tuple(-value for value in _ability_key(horse)),
            horse_no,
        )

    return sorted(index, key=key)


def _interpretation_components(horse: Mapping[str, object]) -> tuple[list[str], list[str]]:
    interpretation = _as_mapping(horse.get("prediction_interpretation"))
    positive = [
        _text(value)
        for value in _as_list(interpretation.get("positive_case_components"))
        if _text(value)
    ]
    concern = [
        _text(value)
        for value in _as_list(interpretation.get("concern_case_components"))
        if _text(value)
    ]
    return positive, concern


def _primary_lane(horse: Mapping[str, object]) -> str:
    trend_state, review_state = _states(horse)
    positive, concern = _interpretation_components(horse)
    trend_codes = [
        code for code in positive + concern if code.startswith("DATA_TREND_")
    ]
    review_codes = [
        code for code in positive + concern if code.startswith("RACEREVIEW_")
    ]

    if trend_state not in {"", "NEUTRAL_OR_UNKNOWN", "INSUFFICIENT"} and trend_codes:
        return "DATA_TREND"
    if review_state not in {"", "MIXED_CONTEXT_ONLY", "INSUFFICIENT"} and review_codes:
        return "RACEREVIEW"
    if trend_codes:
        return "DATA_TREND"
    if review_codes:
        return "RACEREVIEW"
    return "UNCERTAINTY"


def _confidence(horse: Mapping[str, object]) -> str:
    trend_state, review_state = _states(horse)
    interpretation = _as_mapping(horse.get("prediction_interpretation"))
    trend = _as_mapping(interpretation.get("data_trend"))
    review = _as_mapping(interpretation.get("racereview"))

    if trend_state in {"MIXED", "INSUFFICIENT"}:
        return "LOW"
    if review_state in {"MIXED", "MIXED_CONTEXT_ONLY", "INSUFFICIENT"}:
        return "LOW"
    if trend.get("small_sample_only") is True:
        return "LOW"
    if _text(review.get("contradiction_status")).upper() == "MIXED":
        return "LOW"
    if trend_state == "SUPPORTIVE" and review_state in {"HIDDEN_STRENGTH", "SUPPORTIVE"}:
        return "HIGH"
    return "MEDIUM"


def _boundary_priority(upper: Mapping[str, object], lower: Mapping[str, object]) -> str:
    reasons: list[str] = []
    if _confidence(upper) == "LOW":
        reasons.append("UPPER_LOW_CONFIDENCE")
    if _confidence(lower) == "LOW":
        reasons.append("LOWER_LOW_CONFIDENCE")

    for side, horse in (("UPPER", upper), ("LOWER", lower)):
        interpretation = _as_mapping(horse.get("prediction_interpretation"))
        trend = _as_mapping(interpretation.get("data_trend"))
        review = _as_mapping(interpretation.get("racereview"))
        if _text(trend.get("state")).upper() == "MIXED":
            reasons.append(f"{side}_TREND_MIXED")
        if trend.get("small_sample_only") is True:
            reasons.append(f"{side}_SMALL_SAMPLE_ONLY")
        review_state = _text(review.get("state")).upper()
        if review_state in {"MIXED", "MIXED_CONTEXT_ONLY"}:
            reasons.append(f"{side}_REVIEW_MIXED")
        if _text(review.get("contradiction_status")).upper() == "MIXED":
            reasons.append(f"{side}_REVIEW_CONTRADICTION")
    return "HIGH" if reasons else "STANDARD"


def build_synthesis(general: Mapping[str, object]) -> dict[str, object]:
    order = _author_order(general)
    index = _horse_index(general)
    horses: list[dict[str, object]] = []

    for rank, horse_no in enumerate(order, start=1):
        horse = index[horse_no]
        trend_state, review_state = _states(horse)
        positive, concern = _interpretation_components(horse)
        ability = _ability_profile(horse)
        lane = _primary_lane(horse)
        typical = ability.get("typical_median")
        latest = ability.get("latest")
        reason = (
            f"{PROFILE_VERSION}: Trend={trend_state}, Review={review_state}を"
            f"優先順に読み、Ability typical={typical}, latest={latest}は境界文脈として使用。"
        )
        uncertainty = (
            "日次リハーサルの定型author profileであり、Evidence状態の序列は"
            "確率的信頼度や自動スコアを意味しない。"
        )
        horses.append(
            {
                "horse_no": horse_no,
                "draft_rank": rank,
                "confidence": _confidence(horse),
                "primary_lane": lane,
                "positive_components": positive,
                "concern_components": concern,
                "ability_context_used": True,
                "draft_reason": reason,
                "main_uncertainty": uncertainty,
            }
        )

    boundaries: list[dict[str, object]] = []
    for upper_no, lower_no in zip(order, order[1:]):
        upper = index[upper_no]
        lower = index[lower_no]
        boundaries.append(
            {
                "upper_horse_no": upper_no,
                "lower_horse_no": lower_no,
                "comparison_priority": _boundary_priority(upper, lower),
                "boundary_summary": (
                    f"{upper_no}番と{lower_no}番をTrend→RaceReview→Abilityの"
                    "同一読み順で直接比較する境界。"
                ),
            }
        )

    target = copy.deepcopy(dict(_as_mapping(general.get("target"))))
    return {
        "synthesis_schema_version": "RaceNote-All-Runner-Synthesis-0.1",
        "synthesis_contract_version": "FullField-Draft-v0.1",
        "general_evidence_sha256": synthesis_sha256(general),
        "target": target,
        "horses": horses,
        "boundaries": boundaries,
        "draft_order_summary": (
            f"{PROFILE_VERSION}: 全馬をDATA_TREND > RACEREVIEW >= ABILITY_ANCHORの"
            "辞書式優先順で読み、加算スコアなしで日次リハーサルのdraftを作成。"
        ),
    }


def _lane_state(horse: Mapping[str, object], lane: str) -> str:
    trend, review = _states(horse)
    if lane == "DATA_TREND":
        return trend
    if lane == "RACEREVIEW":
        return review
    raise ValueError(lane)


def _relation_from_order(
    state_a: str,
    state_b: str,
    order_map: Mapping[str, int],
) -> str:
    value_a = order_map.get(state_a, 0)
    value_b = order_map.get(state_b, 0)
    if value_a == value_b:
        if value_a == 0:
            return "UNKNOWN"
        return "EVEN"
    return "A" if value_a > value_b else "B"


def _ability_relation(a: Mapping[str, object], b: Mapping[str, object]) -> str:
    key_a = _ability_key(a)
    key_b = _ability_key(b)
    if key_a == key_b:
        return "EVEN"
    return "A" if key_a > key_b else "B"


def _lane_judgments(
    a: Mapping[str, object],
    b: Mapping[str, object],
) -> tuple[dict[str, dict[str, object]], str]:
    a_no = int(a["horse_no"])
    b_no = int(b["horse_no"])
    trend_a, review_a = _states(a)
    trend_b, review_b = _states(b)

    trend_relation = _relation_from_order(trend_a, trend_b, TREND_ORDER)
    review_relation = _relation_from_order(review_a, review_b, REVIEW_ORDER)
    ability_relation = _ability_relation(a, b)

    if trend_relation in {"A", "B"}:
        decisive = "DATA_TREND"
    elif review_relation in {"A", "B"}:
        decisive = "RACEREVIEW"
    elif ability_relation in {"A", "B"}:
        decisive = "ABILITY_ANCHOR"
    else:
        decisive = "UNCERTAINTY"

    judgments = {
        "DATA_TREND": {
            "relation": trend_relation,
            "summary": f"Trend state: {a_no}={trend_a}, {b_no}={trend_b}。",
            "evidence_codes": [],
            "source_refs": [],
        },
        "RACEREVIEW": {
            "relation": review_relation,
            "summary": f"RaceReview state: {a_no}={review_a}, {b_no}={review_b}。",
            "evidence_codes": [],
            "source_refs": [],
        },
        "ABILITY_ANCHOR": {
            "relation": ability_relation,
            "summary": (
                f"Ability anchorを同位境界の補助として比較: "
                f"{a_no}={_ability_profile(a)}, {b_no}={_ability_profile(b)}。"
            ),
            "evidence_codes": [
                "ABILITY_TYPICAL",
                "ABILITY_LATEST",
                "ABILITY_PEAK",
                "ABILITY_CONSISTENCY",
            ],
            "source_refs": [],
        },
    }
    return judgments, decisive


def _preferred_from_relation(relation: str, a_no: int, b_no: int) -> int | None:
     if relation == "A":
        return a_no
    if relation == "B":
        return b_no
    return None


def build_pairwise(
    general: Mapping[str, object],
    synthesis_audit: Mapping[str, object],
) -> dict[str, object]:
    order = [int(value) for value in synthesis_audit["draft_order"]]
    index = _horse_index(general)
    comparisons: list[dict[str, object]] = []

    for a_no, b_no in sorted(required_pair_keys(order)):
        a = index[a_no]
        b = index[b_no]
        judgments, decisive = _lane_judgments(a, b)
        preferred = order.index(a_no) < order.index(b_no)
        preferred_no = a_no if preferred else b_no
        preference = "A" if preferred_no == a_no else "B"

        decisive_relation = judgments.get(decisive, {}).get("relation")
        relation_preferred = _preferred_from_relation(
            str(decisive_relation), a_no, b_no
        )
        if decisive != "UNCERTAINTY" and relation_preferred not in {None, preferred_no}:
            raise RuntimeError(
                f"author-order contradiction for pair {a_no}/{b_no}: "
                f"decisive={decisive} relation={decisive_relation}"
            )

        contrary: list[str] = []
        protected: list[str]
        if decisive == "DATA_TREND":
            protected = []
        elif decisive == "RACEREVIEW":
            protected = ["DATA_TREND"]
        else:
            protected = ["DATA_TREND", "RACEREVIEW"]
        for lane in protected:
            lane_preferred = _preferred_from_relation(
                str(judgments[lane]["relation"]), a_no, b_no
            )
            if lane_preferred is not None and lane_preferred != preferred_no:
                contrary.append(lane)

        comparisons.append(
            {
                "horse_a": a_no,
                "horse_b": b_no,
                "lane_judgments": judgments,
                "preference": preference,
                "confidence": (
                    "MEDIUM"
                    if decisive in {"DATA_TREND", "RACEREVIEW"}
                    else "LOW"
                ),
                "decisive_lane": decisive,
                "lower_priority_override": bool(contrary),
                "override_reason": (
                    "日次リハーサルauthor profileの辞書式優先順で下位laneを採用。"
                    if contrary
                    else ""
                ),
                "comparison_summary": (
                    f"{PROFILE_VERSION}: {preferred_no}番を{decisive}境界で暫定優先。"
                ),
                "reversal_conditions": [
                    "より高優先のData TrendまたはRaceReviewに新しい方向性が供給された場合は再比較する。"
                ],
            }
        )

    return {
        "pairwise_schema_version": "RaceNote-Pairwise-Comparison-0.1",
        "pairwise_contract_version": "TrendFirst-Pairwise-v0.1",
        "general_evidence_sha256": synthesis_sha256(general),
        "all_runner_synthesis_sha256": pairwise_sha256(synthesis_audit),
        "target": copy.deepcopy(dict(_as_mapping(general.get("target")))),
        "draft_order": order,
        "final_order": order,
        "comparisons": comparisons,
        "final_order_summary": (
            f"{PROFILE_VERSION}: 必須境界を直接比較し、Synthesis順をPairwiseで監査。"
        ),
    }


def _position_profile(horse: Mapping[str, object]) -> tuple[str, str]:
    interpretation = _as_mapping(horse.get("prediction_interpretation"))
    structure = _as_mapping(interpretation.get("race_structure"))
    position = _as_mapping(structure.get("horse_historical_position"))
    return (
        _text(position.get("tendency")).upper() or "UNKNOWN",
        _text(position.get("variability_status")).upper() or "UNAVAILABLE",
    )


def _scenario_order(
    base: list[int],
    index: Mapping[int, Mapping[str, object]],
    scenario_id: str,
) -> list[int]:
    """Apply one minimal top-boundary position sensitivity probe."""
    order = list(base)
    if len(order) < 2:
        return order

    first_no = order[0]
    second_no = order[1]
    first_tendency, first_variability = _position_profile(index[first_no])
    second_tendency, second_variability = _position_profile(index[second_no])

    if scenario_id == "SLOW":
        first_disadvantaged = first_tendency in {"BACK", "MID"}
        second_advantaged = (
            second_tendency in {"FRONT", "FORWARD"}
            and second_variability == "SINGLE_BAND"
        )
        if first_disadvantaged and second_advantaged:
            order[0], order[1] = order[1], order[0]
    elif scenario_id == "FAST":
        first_disadvantaged = (
            first_tendency in {"FRONT", "FORWARD"}
            and first_variability == "SINGLE_BAND"
        )
        second_less_committed = (
            second_tendency in {"MID", "BACK", "UNKNOWN"}
            or second_variability == "MULTI_BAND"
        )
        if first_disadvantaged and second_less_committed:
            order[0], order[1] = order[1], order[0]
    return order


def build_scenario(
    general: Mapping[str, object],
    pairwise_audit: Mapping[str, object],
) -> dict[str, object]:
    base = [int(value) for value in pairwise_audit["final_order"]]
    index = _horse_index(general)
    scenarios: list[dict[str, object]] = []
    risk_ids: list[str] = []

    for scenario_id in ("SLOW", "MEDIUM", "FAST"):
        if scenario_id == "MEDIUM":
            order = list(base)
        else:
            order = _scenario_order(base, index, scenario_id)
        changed = order != base
        if order[0] != base[0]:
            risk_ids.append(scenario_id)
        scenarios.append(
            {
                "scenario_id": scenario_id,
                "pace": scenario_id,
                "assumption_summary": (
                    f"{PROFILE_VERSION}: {scenario_id}の位置取り感応度を"
                    "歴史的位置の固定度だけで最小限ストレステストする。"
                ),
                "order": order,
                "changed_from_pairwise": changed,
                "scenario_summary": (
                    "Pairwise baselineを維持。"
                     if not changed
                    else "上位隣接1境界のみ位置取り固定度の感応度として入れ替え。"
                ),
                "key_reason_codes": [
                    f"SCENARIO_{scenario_id}",
                    "POSITION_VARIABILITY_CONTEXT",
                ],
                "triggered_reversal_conditions": (
                    ["歴史的位置の固定度と当該pace stressが上位隣接境界で反対方向に作用。"]
                    if changed
                    else []
                ),
            }
        )

    axis_wins = sum(1 for item in scenarios if item["order"][0] == base[0])
    if axis_wins == 3:
        status = "ROBUST"
    elif axis_wins == 2:
        status = "CONDITIONAL"
    else:
        status = "FRAGILE"

    return {
        "scenario_schema_version": "RaceNote-Scenario-Robustness-0.1",
        "scenario_contract_version": "Pace3-Scenario-v0.1",
        "pairwise_audit_sha256": scenario_sha256(pairwise_audit),
        "target": copy.deepcopy(dict(_as_mapping(general.get("target")))),
        "scenarios": scenarios,
        "conclusion": {
            "pairwise_axis_status": status,
            "main_risk_scenario_ids": risk_ids,
            "summary": (
                f"{PROFILE_VERSION}: axis={base[0]}、3 scenario中{axis_wins}回首位。"
                "これはscenario内順位安定性のみを示し、予測信頼度ではない。"
            ),
        },
    }


def _trace_codes(horse: Mapping[str, object]) -> dict[str, list[str]]:
    result = {
        "DATA_TREND": [],
        "RACEREVIEW": [],
        "ABILITY_ANCHOR": [],
        "RACE_STRUCTURE": [],
        "UNCERTAINTY": [],
    }
    lanes = _as_mapping(horse.get("evidence_lanes"))
    data_lane = _as_mapping(lanes.get("data_trend"))
    history = _as_mapping(data_lane.get("horse_history"))
    for raw in _as_list(history.get("observations")):
        item = _as_mapping(raw)
        code = _text(item.get("code"))
        if code and code not in result["DATA_TREND"]:
            result["DATA_TREND"].append(code)
    population = _as_mapping(data_lane.get("population_context"))
    for raw in population.values():
        item = _as_mapping(raw)
        if _text(item.get("status")).upper() == "AVAILABLE":
            code = _text(item.get("code"))
            if code and code not in result["DATA_TREND"]:
                result["DATA_TREND"].append(code)

    review_lane = _as_mapping(lanes.get("racereview"))
    for field in ("primary_positive", "supporting_positive", "concerns", "mixed_context"):
        for raw in _as_list(review_lane.get(field)):
            item = _as_mapping(raw)
            code = _text(item.get("code"))
            if code and code not in result["RACEREVIEW"]:
                result["RACEREVIEW"].append(code)
    profile = _as_mapping(review_lane.get("profile"))
    for signal_name in ("hidden_strength", "fragile_form"):
        signal = _as_mapping(profile.get(signal_name))
        for raw_code in _as_list(signal.get("reason_codes")):
            code = _text(raw_code)
            if code and code not in result["RACEREVIEW"]:
                result["RACEREVIEW"].append(code)
    for raw in _as_list(review_lane.get("uncertainties")):
        item = _as_mapping(raw)
        code = _text(item.get("code"))
        if code and code not in result["UNCERTAINTY"]:
            result["UNCERTAINTY"].append(code)

    ability = _ability_profile(horse)
    ability_fields = (
        ("latest", "ABILITY_LATEST"),
        ("peak", "ABILITY_PEAK"),
        ("typical_median", "ABILITY_TYPICAL"),
        ("minimum", "ABILITY_MINIMUM"),
        ("mad", "ABILITY_CONSISTENCY"),
    )
    for field, code in ability_fields:
        if ability.get(field) is not None:
            result["ABILITY_ANCHOR"].append(code)

    interpretation = _as_mapping(horse.get("prediction_interpretation"))
    structure = _as_mapping(interpretation.get("race_structure"))
    pressure = _text(structure.get("pace_pressure")).upper()
    if pressure and pressure != "UNKNOWN":
        result["RACE_STRUCTURE"].append(f"PACE_PRESSURE_{pressure}")
    position = _as_mapping(structure.get("horse_historical_position"))
    tendency = _text(position.get("tendency")).upper()
    if tendency and tendency != "UNKNOWN":
        result["RACE_STRUCTURE"].append(f"POSITION_TENDENCY_{tendency}")
    return result


def _primary_trace(horse: Mapping[str, object]) -> tuple[str, str]:
    codes = _trace_codes(horse)
    trend_state, review_state = _states(horse)
    if trend_state not in {"NEUTRAL_OR_UNKNOWN", "INSUFFICIENT", ""} and codes["DATA_TREND"]:
        return "DATA_TREND", codes["DATA_TREND"][0]
    if review_state not in {"MIXED_CONTEXT_ONLY", "INSUFFICIENT", ""} and codes["RACEREVIEW"]:
        return "RACEREVIEW", codes["RACEREVIEW"][0]
    if codes["ABILITY_ANCHOR"]:
        preferred = "ABILITY_TYPICAL"
        if preferred in codes["ABILITY_ANCHOR"]:
            return "ABILITY_ANCHOR", preferred
        return "ABILITY_ANCHOR", codes["ABILITY_ANCHOR"][0]
    if codes["UNCERTAINTY"]:
        return "UNCERTAINTY", codes["UNCERTAINTY"][0]
    raise RuntimeError(f"no traceable primary evidence for horse {horse.get('horse_no')}")


def _concern_trace(horse: Mapping[str, object]) -> tuple[str, str]:
    codes = _trace_codes(horse)
    if codes["RACE_STRUCTURE"]:
        return "RACE_STRUCTURE", codes["RACE_STRUCTURE"][0]
    if codes["RACEREVIEW"]:
        return "RACEREVIEW", codes["RACEREVIEW"][0]
    if codes["DATA_TREND"]:
        return "DATA_TREND", codes["DATA_TREND"][0]
    if codes["UNCERTAINTY"]:
        return "UNCERTAINTY", codes["UNCERTAINTY"][0]
    if codes["ABILITY_ANCHOR"]:
        return "ABILITY_ANCHOR", codes["ABILITY_ANCHOR"][0]
    raise RuntimeError(f"no traceable concern evidence for horse {horse.get('horse_no')}")


def _pairwise_support(
    pairwise_audit: Mapping[str, object],
) -> dict[int, set[int]]:
    result: dict[int, set[int]] = {}
    for raw in _as_list(pairwise_audit.get("comparisons")):
        item = _as_mapping(raw)
        preferred = int(item["preferred_horse_no"])
        a_no = int(item["horse_a"])
        b_no = int(item["horse_b"])
        loser = b_no if preferred == a_no else a_no
        result.setdefault(preferred, set()).add(loser)
    return result


def _scenario_risks(
    scenario_audit: Mapping[str, object],
) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for raw in _as_list(scenario_audit.get("horse_sensitivity")):
        item = _as_mapping(raw)
        horse_no = int(item["horse_no"])
        pairwise_rank = int(item["pairwise_rank"])
        ranks = _as_mapping(item.get("scenario_ranks"))
        adverse: list[str] = []
        for scenario_id, raw_rank in ranks.items():
            if int(raw_rank) > pairwise_rank:
                adverse.append(_text(scenario_id).upper())
        result[horse_no] = sorted(set(adverse))
    return result


def _marks(count: int) -> list[str]:
    result = [""] * count
    if count >= 1:
        result[0] = "◎"
    if count >= 2:
        result[1] = "○"
    if count >= 3:
        result[2] = "▲"
    for index in range(3, min(6, count)):
        result[index] = "△"
    return result


def build_forecast(
    general: Mapping[str, object],
    pairwise_audit: Mapping[str, object],
    scenario_audit: Mapping[str, object],
    *,
    frozen_at: str,
) -> dict[str, object]:
    order = [int(value) for value in pairwise_audit["final_order"]]
    index = _horse_index(general)
    supports = _pairwise_support(pairwise_audit)
    risks = _scenario_risks(scenario_audit)
    marks = _marks(len(order))

    count = len(order)
    p_win = 1.0 / float(count)
    p_top2 = float(min(2, count)) / float(count)
    p_top3 = float(min(3, count)) / float(count)

    horses: list[dict[str, object]] = []
    for rank, horse_no in enumerate(order, start=1):
        horse = index[horse_no]
        primary_lane, primary_code = _primary_trace(horse)
        concern_lane, concern_code = _concern_trace(horse)
        direct_support = sorted(supports.get(horse_no, set()))
        horse_name = _text(horse.get("horse_name"))

        horses.append(
            {
                "horse_no": horse_no,
                "horse_name": horse_name,
                "base_rank": rank,
                "final_rank": rank,
                "mark": marks[rank - 1],
                "p_win_base": p_win,
                "p_top2_base": p_top2,
                "p_top3_base": p_top3,
                "p_win_final": p_win,
                "p_top2_final": p_top2,
                "p_top3_final": p_top3,
                "primary_reason": (
                    f"{PROFILE_VERSION}: {primary_lane}の事前Evidenceを主根拠として"
                    "Pairwise順位をFreezeする。"
                ),
                "secondary_support": "",
                "main_concern": (
                    f"{concern_lane}:{concern_code}を主な不確実性として保持。"
                    "Scenario robustnessは予測信頼度へ昇格しない。"
                ),
                "why_above_next": "",
                "scenario_adjustment_reason": (
                    "Scenarioは感応度監査のみで、Pairwise順位を自動置換しない。"
                ),
                "edge_performance": {
                    "status": "NO_MATCH",
                    "profile": "STANDARD",
                    "matches": [],
                    "adjustment_direction": "NONE",
                    "adjustment_reason": "",
                },
                "decision_trace": {
                    "trace_version": "RaceNote-Decision-Trace-0.1",
                    "primary": {
                        "lane": primary_lane,
                        "evidence_codes": [primary_code],
                    },
                    "secondary": {
                        "lane": "NONE",
                        "evidence_codes": [],
                    },
                    "concern": {
                        "lane": concern_lane,
                        "evidence_codes": [concern_code],
                    },
                    "pairwise_support_horse_nos": direct_support,
                    "scenario_risk_ids": risks.get(horse_no, []),
                    "edge_ids": [],
                    "comment_evidence_codes": [
                        primary_code,
                        concern_code,
                    ],
                },
            }
        )

    target = copy.deepcopy(dict(_as_mapping(general.get("target"))))
    date_text = _text(target.get("date")).replace("-", "")
    venue = _text(target.get("venue"))
    race_no = int(target["race_no"])
    forecast_id = (
        f"{date_text}_{venue}_{race_no:02d}_Gen0-DayRehearsal-v01"
    )

    return {
        "forecast_version": "RaceNote-Forecast-Gen0.3",
        "evidence_policy_version": "TrendFirst-RR-Pairwise-Scenario-v0.1",
        "generation_id": "Gen0-DayRehearsal-v01",
        "forecast_id": forecast_id,
        "target": target,
        "source_chain": {
            "general_evidence_sha256": forecast_sha256(general),
            "pairwise_audit_sha256": forecast_sha256(pairwise_audit),
            "scenario_audit_sha256": forecast_sha256(scenario_audit),
        },
        "firewall": {
            "current_jrdb_consensus_visible": False,
            "current_market_visible": False,
            "edge_value_visible": False,
            "training_edge_visible": False,
            "target_result_visible": False,
        },
        "pairwise_order": order,
        "scenario_axis_robustness": _text(
            scenario_audit.get("axis_robustness")
        ),
        "base_order": order,
        "final_order": order,
        "horses": horses,
        "forecast_created_at": frozen_at,
        "result_visibility_status": "HIDDEN",
        "freeze_status": "UNFROZEN",
        "post_freeze_open_order": [
            "JRDB_CONSENSUS",
            "MARKET",
            "EDGE_VALUE",
            "RL_VALUE",
            "BET_PLAN",
        ],
    }


def author_one(
    general: Mapping[str, object],
    *,
    frozen_at: str,
) -> dict[str, object]:
    synthesis_payload = build_synthesis(general)
    synthesis_audit = validate_all_runner_synthesis(
        general,
        synthesis_payload,
    )

    pairwise_payload = build_pairwise(
        general,
        synthesis_audit,
    )
    pairwise_audit = validate_pairwise_comparison_from_synthesis(
        general,
        synthesis_audit,
        pairwise_payload,
    )

    scenario_payload = build_scenario(
        general,
        pairwise_audit,
    )
    scenario_audit = validate_scenario_robustness(
        pairwise_audit,
        scenario_payload,
    )

    forecast_payload = build_forecast(
        general,
        pairwise_audit,
        scenario_audit,
        frozen_at=frozen_at,
    )
    forecast = validate_forecast(
        general,
        pairwise_audit,
        scenario_audit,
        forecast_payload,
    )
    frozen = freeze_forecast(
        forecast,
        frozen_at,
    )
    freeze_audit = audit_frozen_forecast(frozen)
    if freeze_audit["audit_status"] != "PASS":
        raise RuntimeError("freeze audit failed")

    return {
        "profile_version": PROFILE_VERSION,
        "target": copy.deepcopy(dict(_as_mapping(general.get("target")))),
        "field_evidence_summary": copy.deepcopy(
            general.get("field_evidence_summary")
        ),
        "synthesis_payload": synthesis_payload,
        "synthesis_audit": synthesis_audit,
        "pairwise_payload": pairwise_payload,
        "pairwise_audit": pairwise_audit,
        "scenario_payload": scenario_payload,
        "scenario_audit": scenario_audit,
        "forecast_payload": forecast_payload,
        "forecast_validated": forecast,
        "forecast_frozen": frozen,
        "forecast_freeze_audit": freeze_audit,
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_day(
    prepared_root: Path,
    output_root: Path,
    *,
    frozen_at: str,
) -> dict[str, object]:
    general_paths = sorted(prepared_root.rglob("general_evidence.json"))
    if not general_paths:
        raise RuntimeError("prepared root contains no general_evidence.json")

    rows: list[dict[str, object]] = []
    for index_no, general_path in enumerate(general_paths, start=1):
        general = json.loads(general_path.read_text(encoding="utf-8"))
        target = _as_mapping(general.get("target"))
        venue = _text(target.get("venue"))
        race_no = int(target["race_no"])
        race_dir = output_root / f"{venue}_{race_no:02d}R"

        authored = author_one(
            general,
            frozen_at=frozen_at,
        )
        for key in (
            "synthesis_payload",
            "synthesis_audit",
            "pairwise_payload",
            "pairwise_audit",
            "scenario_payload",
            "scenario_audit",
            "forecast_payload",
            "forecast_validated",
            "forecast_frozen",
            "forecast_freeze_audit",
        ):
            _write_json(race_dir / f"{key}.json", authored[key])

        field_summary = _as_mapping(
            authored.get("field_evidence_summary")
        )
        scenario_audit = _as_mapping(authored["scenario_audit"])
        frozen = _as_mapping(authored["forecast_frozen"])
        freeze_audit = _as_mapping(authored["forecast_freeze_audit"])
        rows.append(
            {
                "target": copy.deepcopy(dict(target)),
                "field_evidence_status": _text(
                    field_summary.get("status")
                ),
                "axis_horse_no": scenario_audit.get("axis_horse_no"),
                "axis_robustness": scenario_audit.get("axis_robustness"),
                "final_order": copy.deepcopy(frozen.get("final_order")),
                "forecast_id": frozen.get("forecast_id"),
                "prediction_hash": frozen.get("prediction_hash"),
                "freeze_audit_status": freeze_audit.get("audit_status"),
            }
        )
        print(
            f"[{index_no}/{len(general_paths)}] "
            f"{venue}{race_no}R PASS"
        )

    summary = {
        "status": "PASS",
        "profile_version": PROFILE_VERSION,
        "race_count": len(rows),
        "frozen_at": frozen_at,
        "result_visibility_status": "HIDDEN",
        "races": rows,
    }
    _write_json(output_root / "day_freeze_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prepared-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--frozen-at",
        required=True,
    )
    args = parser.parse_args()

    datetime.fromisoformat(args.frozen_at.replace("Z", "+00:00"))
    summary = run_day(
        args.prepared_root,
        args.output_root,
        frozen_at=args.frozen_at,
    )
    print(
        json.dumps(
            {
                "status": summary["status"],
                "race_count": summary["race_count"],
                "profile_version": summary["profile_version"],
                "output": str(
                    args.output_root / "day_freeze_summary.json"
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
