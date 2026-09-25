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


def _boundary_priority(upper: Mapping[str, object], lower: Mapping[str, objec