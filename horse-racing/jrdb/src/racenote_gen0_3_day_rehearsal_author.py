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
            