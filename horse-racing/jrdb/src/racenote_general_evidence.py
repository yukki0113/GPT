#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the general RaceNote evidence view for GPT comparison.

The v0.1 contract encodes the user-preferred reading order:

    DATA / TRENDS > RACEREVIEW >= SIMPLE ABILITY

This is an ordinal reasoning contract, not a numeric weighting model.

The builder joins:
- RaceNote INDEPENDENT view
- RaceReview-backed Horse Evidence Card

It then exposes three evidence lanes:
1. data_trend
2. racereview
3. ability_anchor

Current market, current JRDB consensus, and Training Edge remain hidden.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import statistics
from collections.abc import Mapping
from pathlib import Path

GENERAL_SCHEMA_VERSION = "RaceNote-General-Evidence-0.1"
GENERAL_LOGIC_VERSION = "TrendFirst-RR-AbilityAnchor-v0.1"
EXPECTED_RR_CARD_SCHEMA = "RaceNote-Horse-Evidence-Card-0.1"

DECISION_ORDER = (
    "DATA_TREND",
    "RACEREVIEW",
    "ABILITY_ANCHOR",
)

SAMPLE_BAND_ORDER = {
    "none": 0,
    "small": 1,
    "moderate": 2,
    "sufficient": 3,
}


class GeneralEvidenceError(RuntimeError):
    """Raised when general RaceNote evidence cannot be built safely."""


def _text(value: object) -> str:
    """Return stripped text or an empty string."""
    if value is None:
        return ""
    return str(value).strip()


def _finite(value: object) -> float | None:
    """Return a finite float or None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _positive_int(value: object, field: str) -> int:
    """Return a positive integer and fail closed otherwise."""
    if isinstance(value, bool):
        raise GeneralEvidenceError(
            f"{field} must be a positive integer"
        )
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise GeneralEvidenceError(
            f"{field} must be a positive integer"
        ) from exc
    if number < 1:
        raise GeneralEvidenceError(
            f"{field} must be a positive integer"
        )
    return number


def _mapping(value: object, field: str) -> Mapping[str, object]:
    """Require one mapping."""
    if not isinstance(value, Mapping):
        raise GeneralEvidenceError(f"{field} must be an object")
    return value


def _list(value: object, field: str) -> list[object]:
    """Require one list."""
    if not isinstance(value, list):
        raise GeneralEvidenceError(f"{field} must be an array")
    return value


def _date_text(value: object) -> str:
    """Normalize date-like text to YYYY-MM-DD without guessing."""
    text = _text(value)
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) != 8:
        raise GeneralEvidenceError(f"invalid date: {value!r}")
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"


def _sample_band(summary: Mapping[str, object]) -> str:
    """Return one known sample-size band."""
    value = _text(summary.get("sample_size_band")).lower()
    if value in SAMPLE_BAND_ORDER:
        return value
    return "none"


def _rate(summary: Mapping[str, object], field: str) -> float | None:
    """Read one historical percentage rate."""
    value = _finite(summary.get(field))
    if value is None:
        return None
    return value


def _starts(summary: Mapping[str, object]) -> int:
    """Return historical start count or zero."""
    value = summary.get("starts")
    if value is None or isinstance(value, bool):
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    if number < 0:
        return 0
    return number


def _direction_from_delta(delta: float | None) -> str:
    """Describe an observed rate delta without threshold calibration."""
    if delta is None:
        return "UNKNOWN"
    if delta > 0.0:
        return "POSITIVE"
    if delta < 0.0:
        return "NEGATIVE"
    return "NEUTRAL"


def _rate_delta(
    condition: Mapping[str, object],
    career: Mapping[str, object],
    field: str,
) -> float | None:
    """Return condition minus career percentage-point delta."""
    if _starts(condition) == 0:
        return None
    if _starts(career) == 0:
        return None

    condition_rate = _rate(condition, field)
    career_rate = _rate(career, field)
    if condition_rate is None or career_rate is None:
        return None
    return round(condition_rate - career_rate, 1)


def _trend_observation(
    code: str,
    label: str,
    condition: Mapping[str, object],
    career: Mapping[str, object],
) -> dict[str, object]:
    """Build one horse-history trend observation relative to career."""
    top3_delta = _rate_delta(condition, career, "top3_rate")
    win_delta = _rate_delta(condition, career, "win_rate")

    return {
        "code": code,
        "label": label,
        "direction": _direction_from_delta(top3_delta),
        "sample_size_band": _sample_band(condition),
        "condition": copy.deepcopy(dict(condition)),
        "career_baseline": {
            "starts": _starts(career),
            "win_rate": _rate(career, "win_rate"),
            "top3_rate": _rate(career, "top3_rate"),
        },
        "delta_pp": {
            "win_rate": win_delta,
            "top3_rate": top3_delta,
        },
        "interpretation_status": (
            "OBSERVED_RATE_DIFFERENCE_NOT_CAUSAL"
        ),
    }


def _distance_range_label(item: Mapping[str, object]) -> str:
    """Return a deterministic distance-range label."""
    minimum = item.get("min_m")
    maximum = item.get("max_m")
    minimum_text = _text(minimum)
    if maximum is None:
        return f"{minimum_text}m+"
    return f"{minimum_text}-{_text(maximum)}m"


def _horse_history_trends(
    profile: Mapping[str, object] | None,
) -> dict[str, object]:
    """Build horse-condition trend evidence from historical profile."""
    if profile is None:
        return {
            "status": "UNAVAILABLE",
            "observations": [],
            "source": None,
        }

    career_raw = profile.get("career")
    if not isinstance(career_raw, Mapping):
        return {
            "status": "UNAVAILABLE",
            "observations": [],
            "source": _text(profile.get("source")),
        }

    career = career_raw
    observations: list[dict[str, object]] = []

    fixed_dimensions = (
        ("same_surface", "SAME_SURFACE", "同馬場種別"),
        ("same_distance", "SAME_DISTANCE", "同距離"),
        ("same_venue", "SAME_VENUE", "同競馬場"),
    )

    for field, code, label in fixed_dimensions:
        raw = profile.get(field)
        if not isinstance(raw, Mapping):
            continue
        observations.append(
            _trend_observation(
                code,
                label,
                raw,
                career,
            )
        )

    ranges = profile.get("distance_ranges")
    if isinstance(ranges, list):
        for index, raw_range in enumerate(ranges, start=1):
            if not isinstance(raw_range, Mapping):
                continue
            label = _distance_range_label(raw_range)
            observations.append(
                _trend_observation(
                    f"DISTANCE_RANGE_{index}",
                    label,
                    raw_range,
                    career,
                )
            )

    return {
        "status": "AVAILABLE",
        "source": _text(profile.get("source")),
        "source_window_start": _text(
            profile.get("source_window_start")
        ),
        "as_of_exclusive": _text(
            profile.get("as_of_exclusive")
        ),
        "career": copy.deepcopy(dict(career)),
        "observations": observations,
    }


def _stat_context(
    raw: object,
    code: str,
) -> dict[str, object]:
    """Keep one population/statistical context without inventing a baseline."""
    if not isinstance(raw, Mapping):
        return {
            "code": code,
            "status": "UNAVAILABLE",
        }

    return {
        "code": code,
        "status": "AVAILABLE",
        "sample_size_band": _sample_band(raw),
        "summary": copy.deepcopy(dict(raw)),
        "interpretation_status": (
            "CONTEXT_FOR_RELATIVE_COMPARISON_NOT_STANDALONE_SCORE"
        ),
    }


def _current_frame_context(
    race: Mapping[str, object],
    horse: Mapping[str, object],
) -> dict[str, object]:
    """Return the race-level frame statistic for the horse's current frame."""
    basic = horse.get("basic")
    if not isinstance(basic, Mapping):
        return {
            "code": "FRAME_TREND",
            "status": "UNAVAILABLE",
        }

    frame_no = basic.get("frame_no")
    if frame_no is None:
        return {
            "code": "FRAME_TREND",
            "status": "UNAVAILABLE",
        }

    race_trends = race.get("race_trends")
    if not isinstance(race_trends, Mapping):
        return {
            "code": "FRAME_TREND",
            "status": "UNAVAILABLE",
            "frame_no": frame_no,
        }

    frames = race_trends.get("frame")
    if not isinstance(frames, Mapping):
        return {
            "code": "FRAME_TREND",
            "status": "UNAVAILABLE",
            "frame_no": frame_no,
        }

    frame_key = str(frame_no)
    raw = frames.get(frame_key)
    if not isinstance(raw, Mapping):
        return {
            "code": "FRAME_TREND",
            "status": "UNAVAILABLE",
            "frame_no": frame_no,
        }

    return {
        "code": "FRAME_TREND",
        "status": "AVAILABLE",
        "frame_no": frame_no,
        "sample_size_band": _sample_band(raw),
        "summary": copy.deepcopy(dict(raw)),
        "interpretation_status": (
            "RACE_LEVEL_TREND_CONTEXT_NOT_STANDALONE_SCORE"
        ),
    }


def _data_trend_lane(
    race: Mapping[str, object],
    horse: Mapping[str, object],
) -> dict[str, object]:
    """Build the highest-priority data/trend lane."""
    profile_raw = horse.get("historical_profile")
    profile: Mapping[str, object] | None = None
    if isinstance(profile_raw, Mapping):
        profile = profile_raw

    stats = horse.get("stats")
    if not isinstance(stats, Mapping):
        stats = {}

    return {
        "priority_rank": 1,
        "priority_relation": "HIGHEST",
        "horse_history": _horse_history_trends(profile),
        "population_context": {
            "frame": _current_frame_context(race, horse),
            "sire": _stat_context(stats.get("sire"), "SIRE_TREND"),
            "jockey": _stat_context(
                stats.get("jockey"),
                "JOCKEY_TREND",
            ),
        },
        "policy": {
            "small_sample_is_not_zero_evidence": True,
            "sample_size_must_be_visible": True,
            "rate_difference_is_not_causality": True,
            "no_additive_trend_score": True,
        },
    }


def _recent_run_rows(
    horse: Mapping[str, object],
) -> list[Mapping[str, object]]:
    """Return recent historical runs sorted newest first."""
    raw_runs = horse.get("recent_runs")
    if not isinstance(raw_runs, list):
        return []

    sortable: list[tuple[str, Mapping[str, object]]] = []
    for raw_run in raw_runs:
        if not isinstance(raw_run, Mapping):
            continue
        race = raw_run.get("race")
        if not isinstance(race, Mapping):
            continue
        date_text = _text(race.get("date"))
        sortable.append((date_text, raw_run))

    sortable.sort(
        key=lambda item: item[0],
        reverse=True,
    )
    return [item[1] for item in sortable]


def _ability_observations(
    horse: Mapping[str, object],
) -> list[dict[str, object]]:
    """Extract prior-run IDM observations with provenance."""
    rows: list[dict[str, object]] = []

    for raw_run in _recent_run_rows(horse):
        race = raw_run.get("race")
        performance = raw_run.get("performance")
        result = raw_run.get("result")

        if not isinstance(race, Mapping):
            continue
        if not isinstance(performance, Mapping):
            continue

        idm = _finite(performance.get("idm"))
        if idm is None:
            continue

        finish = None
        if isinstance(result, Mapping):
            finish = result.get("finish")

        rows.append(
            {
                "date": _text(race.get("date")),
                "venue": _text(race.get("venue")),
                "race_no": race.get("race_no"),
                "surface": _text(race.get("surface")),
                "distance_m": race.get("distance_m"),
                "class": _text(race.get("class")),
                "grade": _text(race.get("grade")),
                "finish": finish,
                "idm": idm,
            }
        )

    return rows


def _median_absolute_deviation(values: list[float]) -> float | None:
    """Return median absolute deviation for a non-empty finite series."""
    if not values:
        return None
    center = statistics.median(values)
    deviations = [abs(value - center) for value in values]
    return round(float(statistics.median(deviations)), 2)


def _ability_anchor(
    horse: Mapping[str, object],
) -> dict[str, object]:
    """Build a non-ranking simple-ability anchor from prior-run IDM only."""
    observations = _ability_observations(horse)
    values = [
        float(item["idm"])
        for item in observations
    ]

    if not values:
        return {
            "priority_rank": 3,
            "priority_relation": "ANCHOR_ONLY",
            "status": "UNAVAILABLE",
            "observed_count": 0,
            "observations": [],
            "profile": {
                "latest": None,
                "peak": None,
                "typical_median": None,
                "minimum": None,
                "mad": None,
            },
            "policy": {
                "current_entry_idm_used": False,
                "current_total_index_used": False,
                "may_auto_rank": False,
            },
        }

    latest = values[0]
    peak = max(values)
    minimum = min(values)
    typical = float(statistics.median(values))
    mad = _median_absolute_deviation(values)

    return {
        "priority_rank": 3,
        "priority_relation": "ANCHOR_ONLY",
        "status": "AVAILABLE",
        "observed_count": len(values),
        "observations": observations,
        "profile": {
            "latest": latest,
            "peak": peak,
            "typical_median": round(typical, 2),
            "minimum": minimum,
            "mad": mad,
        },
        "policy": {
            "current_entry_idm_used": False,
            "current_total_index_used": False,
            "may_auto_rank": False,
            "interpretation": (
                "ABILITY_FLOOR_CEILING_CONTEXT_NOT_FINAL_ORDER"
            ),
        },
    }


def _rr_lane(card: Mapping[str, object]) -> dict[str, object]:
    """Project the RaceReview card as the second-priority lane."""
    return {
        "priority_rank": 2,
        "priority_relation": "SECOND",
        "card_scope": _text(card.get("card_scope")),
        "primary_positive": copy.deepcopy(
            card.get("primary_positive", [])
        ),
        "supporting_positive": copy.deepcopy(
            card.get("supporting_positive", [])
        ),
        "concerns": copy.deepcopy(card.get("concerns", [])),
        "mixed_context": copy.deepcopy(
            card.get("mixed_context", [])
        ),
        "profile": copy.deepcopy(card.get("profile", {})),
        "uncertainties": copy.deepcopy(
            card.get("uncertainties", [])
        ),
        "comment_evidence": copy.deepcopy(
            card.get("comment_evidence", {})
        ),
    }


def _validate_independent_view(
    independent: Mapping[str, object],
) -> None:
    """Validate the independent firewall boundary."""
    if _text(independent.get("view_kind")).upper() != "INDEPENDENT":
        raise GeneralEvidenceError(
            "general evidence requires INDEPENDENT view"
        )

    policy = _mapping(independent.get("policy"), "independent.policy")
    if policy.get("current_jrdb_consensus_visible") is not False:
        raise GeneralEvidenceError(
            "current JRDB consensus must remain hidden"
        )
    if policy.get("current_market_visible") is not False:
        raise GeneralEvidenceError(
            "current market must remain hidden"
        )
    if policy.get("training_edge_visible") is not False:
        raise GeneralEvidenceError(
            "Training Edge must remain hidden"
        )


def _validate_rr_cards(
    rr_cards: Mapping[str, object],
) -> None:
    """Validate the RaceReview card source boundary."""
    if (
        _text(rr_cards.get("card_schema_version"))
        != EXPECTED_RR_CARD_SCHEMA
    ):
        raise GeneralEvidenceError(
            "unsupported Horse Evidence Card schema"
        )

    policy = _mapping(rr_cards.get("policy"), "rr.policy")
    if policy.get("market_visibility_status") != "HIDDEN_NOT_CONSUMED":
        raise GeneralEvidenceError(
            "RaceReview card opened market unexpectedly"
        )
    if (
        policy.get("jrdb_current_consensus_status")
        != "HIDDEN_NOT_CONSUMED"
    ):
        raise GeneralEvidenceError(
            "RaceReview card opened current JRDB consensus"
        )


def _target_key(target: Mapping[str, object]) -> tuple[str, str, int]:
    """Return normalized race identity."""
    date_text = _date_text(target.get("date"))
    venue = _text(target.get("venue"))
    race_no = _positive_int(target.get("race_no"), "race_no")
    return date_text, venue, race_no


def _rr_by_horse_no(
    rr_cards: Mapping[str, object],
) -> dict[int, Mapping[str, object]]:
    """Index RaceReview cards by horse number."""
    raw_horses = _list(rr_cards.get("horses"), "rr.horses")
    result: dict[int, Mapping[str, object]] = {}

    for index, raw_horse in enumerate(raw_horses, start=1):
        horse = _mapping(raw_horse, f"rr.horses[{index}]")
        horse_no = _positive_int(
            horse.get("horse_no"),
            f"rr.horses[{index}].horse_no",
        )
        if horse_no in result:
            raise GeneralEvidenceError(
                f"duplicate RaceReview horse_no: {horse_no}"
            )
        result[horse_no] = horse

    return result


def _identity_check(
    independent_horse: Mapping[str, object],
    rr_card: Mapping[str, object],
    horse_no: int,
) -> None:
    """Fail closed on conflicting stable horse IDs."""
    basic = _mapping(
        independent_horse.get("basic"),
        f"horse[{horse_no}].basic",
    )
    independent_id = _text(basic.get("horse_id"))
    rr_id = _text(rr_card.get("horse_id"))

    if independent_id and rr_id and independent_id != rr_id:
        raise GeneralEvidenceError(
            "horse_id mismatch between independent view and RaceReview "
            f"card: horse_no={horse_no}"
        )


def _rotation_interval(horse: Mapping[str, object]) -> object:
    """Return current factual rotation interval without processed condition."""
    condition = horse.get("condition_facts")
    if not isinstance(condition, Mapping):
        return None
    return condition.get("rotation_interval")


def _race_data_context(
    race: Mapping[str, object],
) -> dict[str, object]:
    """Keep current race conditions and available race-level trend data."""
    keys = (
        "date",
        "venue",
        "race_no",
        "race_name",
        "surface",
        "distance_m",
        "turn",
        "course_layout",
        "race_type",
        "class",
        "race_conditions",
        "weight_rule",
        "grade",
        "field_size",
    )
    conditions: dict[str, object] = {}
    for key in keys:
        if key in race:
            conditions[key] = copy.deepcopy(race[key])

    race_trends = race.get("race_trends")
    trends: dict[str, object] = {}
    if isinstance(race_trends, Mapping):
        trends = copy.deepcopy(dict(race_trends))

    trend_sources: list[str] = []
    if "frame" in trends:
        trend_sources.append("FRAME")
    if "running_style" in trends:
        trend_sources.append("RUNNING_STYLE")

    return {
        "conditions": conditions,
        "available_trends": trends,
        "trend_sources_v0_1": trend_sources,
        "independent_future_trend_sources": [
            "PACE_PATTERN",
            "TRACK_CONDITION",
            "COURSE_LAYOUT",
        ],
        "post_freeze_trend_sources": [
            "POPULARITY",
        ],
        "policy": {
            "available_trend_data_precedes_ability_anchor": True,
            "missing_future_source_is_not_negative_evidence": True,
        },
    }


def build_general_evidence(
    independent_view: Mapping[str, object],
    rr_cards: Mapping[str, object],
) -> dict[str, object]:
    """Build the trend-first general evidence structure."""
    _validate_independent_view(independent_view)
    _validate_rr_cards(rr_cards)

    race = _mapping(independent_view.get("race"), "independent.race")
    rr_target = _mapping(rr_cards.get("target"), "rr.target")

    independent_key = _target_key(race)
    rr_key = _target_key(rr_target)
    if independent_key != rr_key:
        raise GeneralEvidenceError(
            "target mismatch between independent view and RaceReview card"
        )

    rr_index = _rr_by_horse_no(rr_cards)
    raw_horses = _list(
        independent_view.get("horses"),
        "independent.horses",
    )
    if not raw_horses:
        raise GeneralEvidenceError(
            "independent view contains no horses"
        )

    output_horses: list[dict[str, object]] = []
    seen: set[int] = set()

    for index, raw_horse in enumerate(raw_horses, start=1):
        horse = _mapping(
            raw_horse,
            f"independent.horses[{index}]",
        )
        basic = _mapping(
            horse.get("basic"),
            f"independent.horses[{index}].basic",
        )
        horse_no = _positive_int(
            basic.get("horse_no"),
            f"independent.horses[{index}].basic.horse_no",
        )
        if horse_no in seen:
            raise GeneralEvidenceError(
                f"duplicate independent horse_no: {horse_no}"
            )
        seen.add(horse_no)

        rr_card = rr_index.get(horse_no)
        if rr_card is None:
            raise GeneralEvidenceError(
                f"missing RaceReview card for horse_no={horse_no}"
            )
        _identity_check(horse, rr_card, horse_no)

        output_horses.append(
            {
                "horse_no": horse_no,
                "horse_name": _text(basic.get("horse_name")),
                "horse_id": _text(basic.get("horse_id")),
                "current_facts": {
                    "frame_no": basic.get("frame_no"),
                    "jockey": basic.get("jockey"),
                    "trainer": basic.get("trainer"),
                    "carried_weight_kg": basic.get(
                        "carried_weight_kg"
                    ),
                    "rotation_interval": _rotation_interval(
                        horse
                    ),
                },
                "evidence_lanes": {
                    "data_trend": _data_trend_lane(
                        race,
                        horse,
                    ),
                    "racereview": _rr_lane(rr_card),
                    "ability_anchor": _ability_anchor(horse),
                },
                "comparison_status": "NOT_YET_PAIRWISE_COMPARED",
            }
        )

    return {
        "general_schema_version": GENERAL_SCHEMA_VERSION,
        "general_logic_version": GENERAL_LOGIC_VERSION,
        "target": {
            "date": independent_key[0],
            "venue": independent_key[1],
            "race_no": independent_key[2],
            "race_name": _text(race.get("race_name")),
        },
        "priority_policy": {
            "relation": "DATA_TREND > RACEREVIEW >= ABILITY_ANCHOR",
            "decision_order": list(DECISION_ORDER),
            "numeric_weights": None,
            "rules": {
                "data_trend_read_first": True,
                "racereview_read_second": True,
                "ability_anchor_read_last": True,
                "ability_may_auto_rank": False,
                "lower_priority_override_requires_reason": True,
                "higher_priority_missing_is_not_negative": True,
                "small_sample_must_remain_visible": True,
                "contradictions_must_be_preserved": True,
            },
        },
        "firewall": {
            "current_jrdb_consensus_visible": False,
            "current_market_visible": False,
            "training_edge_visible": False,
        },
        "race_data_context": _race_data_context(race),
        "horses": sorted(
            output_horses,
            key=lambda horse: int(horse["horse_no"]),
        ),
        "next_stage": {
            "name": "PAIRWISE_COMPARISON",
            "required_read_order": list(DECISION_ORDER),
            "status": "CONTRACT_IMPLEMENTED",
            "contract_version": "TrendFirst-Pairwise-v0.1",
        },
    }


def main() -> int:
    """Build one general evidence JSON file."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--independent-view",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--racereview-card",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    args = parser.parse_args()

    independent = json.loads(
        args.independent_view.read_text(encoding="utf-8")
    )
    rr_cards = json.loads(
        args.racereview_card.read_text(encoding="utf-8")
    )
    result = build_general_evidence(
        independent,
        rr_cards,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": "PASS",
                "general_schema_version": GENERAL_SCHEMA_VERSION,
                "horse_count": len(result["horses"]),
                "priority_relation": result[
                    "priority_policy"
                ]["relation"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
