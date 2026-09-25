#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RaceNote Forecast Gen0.3 validation and freeze contract.

Gen0.3 is trend-first:
General Evidence -> Pairwise -> Scenario -> Base Forecast
-> EdgeDB performance-only overlay -> Final Forecast -> Freeze.

It does not calculate horse selection automatically. GPT authors probabilities,
rank, marks, and concise reasons; this module validates boundaries and
consistency.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping
from datetime import datetime
from typing import Any

FORECAST_VERSION = "RaceNote-Forecast-Gen0.3"
EVIDENCE_POLICY_VERSION = "TrendFirst-RR-Pairwise-Scenario-v0.1"
DEFAULT_GENERATION_ID = "Gen0-G001"
EXPECTED_GENERAL_SCHEMA = "RaceNote-General-Evidence-0.1"
EXPECTED_PAIRWISE_AUDIT = "RaceNote-Pairwise-Audit-0.1"
EXPECTED_SCENARIO_AUDIT = "RaceNote-Scenario-Robustness-Audit-0.1"
ALLOWED_MARKS = {"◎", "○", "▲", "△", ""}
ALLOWED_EDGE_LEVELS = {"CONFIRMED", "SUGGESTIVE"}
ALLOWED_EDGE_SIGNALS = {"POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL"}
ALLOWED_EDGE_ROLES = {"PRIMARY", "SECONDARY", "CONFLICT"}
FORBIDDEN_EDGE_KEYS = {
    "value_evidence_level",
    "value_signal",
    "value_p_value",
    "value_q_value",
    "value_edge",
}


class ForecastGen03Error(RuntimeError):
    """Forecast Gen0.3 validation failure."""


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ForecastGen03Error(f"{field} must be an object")
    return value


def _list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ForecastGen03Error(f"{field} must be an array")
    return value


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ForecastGen03Error(f"{field} must be positive integer")
    try:
        number = int(value)
        raw = float(value)
    except (TypeError, ValueError) as exc:
        raise ForecastGen03Error(f"{field} must be positive integer") from exc
    if number < 1 or raw != number:
        raise ForecastGen03Error(f"{field} must be positive integer")
    return number


def _probability(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise ForecastGen03Error(f"{field} must be probability")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ForecastGen03Error(f"{field} must be probability") from exc
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ForecastGen03Error(f"{field} must be within [0,1]")
    return number


def _datetime(value: object, field: str) -> datetime:
    text = _text(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        result = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ForecastGen03Error(f"{field} must be ISO datetime") from exc
    if result.tzinfo is None:
        raise ForecastGen03Error(f"{field} must include timezone")
    return result


def semantic_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _target_key(target: Mapping[str, object]) -> tuple[str, str, int]:
    date_text = _text(target.get("date"))
    venue = _text(target.get("venue"))
    race_no = _positive_int(target.get("race_no"), "target.race_no")
    if not date_text or not venue:
        raise ForecastGen03Error("target date/venue required")
    return date_text, venue, race_no


def _validate_source_chain(
    general: Mapping[str, object],
    pairwise: Mapping[str, object],
    scenario: Mapping[str, object],
) -> list[int]:
    if _text(general.get("general_schema_version")) != EXPECTED_GENERAL_SCHEMA:
        raise ForecastGen03Error("unsupported General Evidence schema")
    if _text(pairwise.get("audit_schema_version")) != EXPECTED_PAIRWISE_AUDIT:
        raise ForecastGen03Error("unsupported Pairwise audit schema")
    if _text(pairwise.get("status")) != "PASS":
        raise ForecastGen03Error("Pairwise audit must PASS")
    if _text(scenario.get("audit_schema_version")) != EXPECTED_SCENARIO_AUDIT:
        raise ForecastGen03Error("unsupported Scenario audit schema")
    if _text(scenario.get("status")) != "PASS":
        raise ForecastGen03Error("Scenario audit must PASS")

    general_target = _mapping(general.get("target"), "general.target")
    pairwise_target = _mapping(pairwise.get("target"), "pairwise.target")
    scenario_target = _mapping(scenario.get("target"), "scenario.target")
    keys = {
        _target_key(general_target),
        _target_key(pairwise_target),
        _target_key(scenario_target),
    }
    if len(keys) != 1:
        raise ForecastGen03Error("source target mismatch")

    if _text(pairwise.get("general_evidence_sha256")).lower() != semantic_sha256(general):
        raise ForecastGen03Error("Pairwise does not bind to General Evidence")
    if _text(scenario.get("pairwise_audit_sha256")).lower() != semantic_sha256(pairwise):
        raise ForecastGen03Error("Scenario does not bind to Pairwise audit")

    if scenario.get("pairwise_recheck_recommended") is True:
        raise ForecastGen03Error(
            "Scenario says Pairwise recheck is required before forecast"
        )

    raw_order = _list(pairwise.get("final_order"), "pairwise.final_order")
    order = [
        _positive_int(value, "pairwise.final_order")
        for value in raw_order
    ]
    if not order or len(order) != len(set(order)):
        raise ForecastGen03Error("invalid Pairwise final order")
    return order


def _validate_order(
    raw: object,
    field: str,
    runners: set[int],
) -> list[int]:
    values = _list(raw, field)
    result = [_positive_int(value, field) for value in values]
    if len(result) != len(set(result)) or set(result) != runners:
        raise ForecastGen03Error(
            f"{field} must contain every runner exactly once"
        )
    return result


def _walk_forbidden_edge(value: object, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in FORBIDDEN_EDGE_KEYS:
                raise ForecastGen03Error(
                    f"Edge value field forbidden before Freeze: {path}.{key}"
                )
            _walk_forbidden_edge(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_forbidden_edge(child, f"{path}[{index}]")


def _edge_overlay(
    raw: object,
    horse_no: int,
) -> dict[str, object]:
    overlay = _mapping(raw, f"horse[{horse_no}].edge_performance")
    _walk_forbidden_edge(overlay)

    status = _text(overlay.get("status")).upper()
    if status not in {"USED", "NO_MATCH", "UNAVAILABLE"}:
        raise ForecastGen03Error("edge status invalid")

    matches: list[dict[str, object]] = []
    seen_groups: set[tuple[str, str]] = set()
    raw_matches = _list(
        overlay.get("matches", []),
        f"horse[{horse_no}].edge_performance.matches",
    )
    for index, raw_match in enumerate(raw_matches, start=1):
        match = _mapping(
            raw_match,
            f"horse[{horse_no}].edge_performance.matches[{index}]",
        )
        edge_id = _text(match.get("edge_id"))
        family = _text(match.get("family"))
        level = _text(match.get("performance_evidence_level")).upper()
        signal = _text(match.get("signal")).upper()
        role = _text(match.get("presentation_role")).upper()
        group = _text(match.get("redundancy_group_id")) or edge_id
        if not edge_id or not family:
            raise ForecastGen03Error("Edge ID/family required")
        if level not in ALLOWED_EDGE_LEVELS:
            raise ForecastGen03Error("Edge performance level invalid")
        if signal not in ALLOWED_EDGE_SIGNALS:
            raise ForecastGen03Error("Edge performance signal invalid")
        if role not in ALLOWED_EDGE_ROLES:
            raise ForecastGen03Error("Edge presentation role invalid")

        identity = (group, signal)
        if role == "PRIMARY" and identity in seen_groups:
            raise ForecastGen03Error(
                "duplicate PRIMARY evidence in one redundancy group/signal"
            )
        if role == "PRIMARY":
            seen_groups.add(identity)

        matches.append(
            {
                "edge_id": edge_id,
                "family": family,
                "performance_evidence_level": level,
                "signal": signal,
                "presentation_role": role,
                "conflict": bool(match.get("conflict", False)),
                "redundancy_group_id": group,
            }
        )

    if status == "USED" and not matches:
        raise ForecastGen03Error("USED Edge overlay requires matches")
    if status != "USED" and matches:
        raise ForecastGen03Error("non-USED Edge overlay must not contain matches")

    reason = _text(overlay.get("adjustment_reason"))
    direction = _text(overlay.get("adjustment_direction")).upper()
    if direction not in {"POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL", "NONE"}:
        raise ForecastGen03Error("Edge adjustment direction invalid")
    if status == "USED" and not reason:
        raise ForecastGen03Error("Edge adjustment reason required when used")

    return {
        "status": status,
        "profile": _text(overlay.get("profile")) or "STANDARD",
        "matches": matches,
        "adjustment_direction": direction,
        "adjustment_reason": reason,
    }


def _horse(
    raw: object,
    index: int,
    runners: set[int],
) -> dict[str, object]:
    horse = _mapping(raw, f"horses[{index}]")
    horse_no = _positive_int(
        horse.get("horse_no"),
        f"horses[{index}].horse_no",
    )
    if horse_no not in runners:
        raise ForecastGen03Error("forecast references unknown runner")

    base_rank = _positive_int(
        horse.get("base_rank"),
        f"horses[{index}].base_rank",
    )
    final_rank = _positive_int(
        horse.get("final_rank"),
        f"horses[{index}].final_rank",
    )
    mark = _text(horse.get("mark"))
    if mark not in ALLOWED_MARKS:
        raise ForecastGen03Error("unsupported mark")

    probabilities: dict[str, float] = {}
    for stage in ("base", "final"):
        for kind in ("win", "top2", "top3"):
            key = f"p_{kind}_{stage}"
            probabilities[key] = _probability(
                horse.get(key),
                f"horses[{index}].{key}",
            )
        if not (
            probabilities[f"p_win_{stage}"]
            <= probabilities[f"p_top2_{stage}"]
            <= probabilities[f"p_top3_{stage}"]
        ):
            raise ForecastGen03Error(
                f"probability nesting invalid for horse {horse_no}"
            )

    scenario_reason = _text(horse.get("scenario_adjustment_reason"))
    edge = _edge_overlay(
        horse.get("edge_performance", {}),
        horse_no,
    )
    return {
        "horse_no": horse_no,
        "horse_name": _text(horse.get("horse_name")),
        "base_rank": base_rank,
        "final_rank": final_rank,
        "mark": mark,
        **probabilities,
        "primary_reason": _text(horse.get("primary_reason")),
        "secondary_support": _text(horse.get("secondary_support")),
        "main_concern": _text(horse.get("main_concern")),
        "why_above_next": _text(horse.get("why_above_next")),
        "scenario_adjustment_reason": scenario_reason,
        "edge_performance": edge,
    }


def _probability_totals(
    horses: list[dict[str, object]],
    stage: str,
) -> None:
    count = len(horses)
    targets = {
        "win": 1.0,
        "top2": float(min(2, count)),
        "top3": float(min(3, count)),
    }
    tolerances = {
        "win": 0.005,
        "top2": 0.05,
        "top3": 0.05,
    }
    for kind in ("win", "top2", "top3"):
        total = sum(float(horse[f"p_{kind}_{stage}"]) for horse in horses)
        if abs(total - targets[kind]) > tolerances[kind]:
            raise ForecastGen03Error(
                f"sum p_{kind}_{stage}={total:.6f} expected {targets[kind]}"
            )


def validate_forecast(
    general: Mapping[str, object],
    pairwise: Mapping[str, object],
    scenario: Mapping[str, object],
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Validate one authored Gen0.3 forecast."""
    pairwise_order = _validate_source_chain(
        general,
        pairwise,
        scenario,
    )
    runners = set(pairwise_order)

    if _text(payload.get("forecast_version")) != FORECAST_VERSION:
        raise ForecastGen03Error("forecast_version must be Gen0.3")
    if _text(payload.get("evidence_policy_version")) != EVIDENCE_POLICY_VERSION:
        raise ForecastGen03Error("evidence policy version mismatch")

    target = _mapping(payload.get("target"), "forecast.target")
    if _target_key(target) != _target_key(
        _mapping(general.get("target"), "general.target")
    ):
        raise ForecastGen03Error("forecast target mismatch")

    source = _mapping(payload.get("source_chain"), "forecast.source_chain")
    expected_hashes = {
        "general_evidence_sha256": semantic_sha256(general),
        "pairwise_audit_sha256": semantic_sha256(pairwise),
        "scenario_audit_sha256": semantic_sha256(scenario),
    }
    for key, expected in expected_hashes.items():
        if _text(source.get(key)).lower() != expected:
            raise ForecastGen03Error(f"source hash mismatch: {key}")

    base_order = _validate_order(
        payload.get("base_order"),
        "forecast.base_order",
        runners,
    )
    final_order = _validate_order(
        payload.get("final_order"),
        "forecast.final_order",
        runners,
    )

    raw_horses = _list(payload.get("horses"), "forecast.horses")
    horses = [
        _horse(raw, index, runners)
        for index, raw in enumerate(raw_horses, start=1)
    ]
    if len(horses) != len(runners):
        raise ForecastGen03Error("forecast must contain every runner")
    if len({int(horse["horse_no"]) for horse in horses}) != len(horses):
        raise ForecastGen03Error("duplicate forecast runner")

    base_rank_map = {
        int(horse["horse_no"]): int(horse["base_rank"])
        for horse in horses
    }
    final_rank_map = {
        int(horse["horse_no"]): int(horse["final_rank"])
        for horse in horses
    }
    if sorted(base_rank_map, key=base_rank_map.get) != base_order:
        raise ForecastGen03Error("base_order/base_rank mismatch")
    if sorted(final_rank_map, key=final_rank_map.get) != final_order:
        raise ForecastGen03Error("final_order/final_rank mismatch")

    expected_ranks = set(range(1, len(runners) + 1))
    if set(base_rank_map.values()) != expected_ranks:
        raise ForecastGen03Error("base ranks must be contiguous")
    if set(final_rank_map.values()) != expected_ranks:
        raise ForecastGen03Error("final ranks must be contiguous")

    pairwise_rank = {horse_no: rank for rank, horse_no in enumerate(pairwise_order, 1)}
    for horse in horses:
        horse_no = int(horse["horse_no"])
        changed = int(horse["base_rank"]) != pairwise_rank[horse_no]
        if changed and not _text(horse.get("scenario_adjustment_reason")):
            raise ForecastGen03Error(
                "scenario adjustment reason required when base rank "
                "differs from Pairwise rank"
            )

    base_rank_by_no = base_rank_map
    for horse in horses:
        horse_no = int(horse["horse_no"])
        edge_used = horse["edge_performance"]["status"] == "USED"
        rank_changed = int(horse["final_rank"]) != base_rank_by_no[horse_no]
        if rank_changed and not edge_used:
            raise ForecastGen03Error(
                "final rank may differ from base rank only with Edge performance evidence"
            )
        if rank_changed and not _text(
            horse["edge_performance"]["adjustment_reason"]
        ):
            raise ForecastGen03Error(
                "Edge rank change requires adjustment reason"
            )

    _probability_totals(horses, "base")
    _probability_totals(horses, "final")

    marks = [str(horse["mark"]) for horse in horses]
    if marks.count("◎") != 1 or marks.count("○") > 1 or marks.count("▲") > 1:
        raise ForecastGen03Error("mark cardinality invalid")
    axis = min(horses, key=lambda item: int(item["final_rank"]))
    if axis["mark"] != "◎":
        raise ForecastGen03Error("final rank 1 must be ◎")
    if float(axis["p_win_final"]) < max(float(h["p_win_final"]) for h in horses) - 1e-12:
        raise ForecastGen03Error("◎ must have maximum final win probability")

    for horse in horses:
        if not _text(horse.get("primary_reason")):
            raise ForecastGen03Error("primary_reason required")
        if not _text(horse.get("main_concern")):
            raise ForecastGen03Error("main_concern required")

    created_at = _text(payload.get("forecast_created_at"))
    _datetime(created_at, "forecast_created_at")

    generation_id = _text(payload.get("generation_id")) or DEFAULT_GENERATION_ID
    forecast_id = _text(payload.get("forecast_id"))
    if not forecast_id:
        date_text, venue, race_no = _target_key(target)
        forecast_id = (
            f"{date_text.replace('-', '')}_{venue}_{race_no:02d}_{generation_id}"
        )

    return {
        "forecast_version": FORECAST_VERSION,
        "evidence_policy_version": EVIDENCE_POLICY_VERSION,
        "generation_id": generation_id,
        "forecast_id": forecast_id,
        "target": copy.deepcopy(dict(target)),
        "source_chain": expected_hashes,
        "firewall": {
            "current_jrdb_consensus_visible": False,
            "current_market_visible": False,
            "edge_value_visible": False,
            "training_edge_visible": False,
            "target_result_visible": False,
        },
        "pairwise_order": pairwise_order,
        "scenario_axis_robustness": _text(
            scenario.get("axis_robustness")
        ),
        "base_order": base_order,
        "final_order": final_order,
        "horses": sorted(
            horses,
            key=lambda item: int(item["final_rank"]),
        ),
        "forecast_created_at": created_at,
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


def _prediction_hash(forecast: Mapping[str, object]) -> str:
    value = copy.deepcopy(dict(forecast))
    value.pop("prediction_hash", None)
    value.pop("frozen_at", None)
    value["freeze_status"] = "UNFROZEN"
    return semantic_sha256(value)


def freeze_forecast(
    forecast: Mapping[str, object],
    frozen_at: str,
) -> dict[str, object]:
    if _text(forecast.get("forecast_version")) != FORECAST_VERSION:
        raise ForecastGen03Error("only validated Gen0.3 forecast can freeze")
    created = _datetime(
        forecast.get("forecast_created_at"),
        "forecast_created_at",
    )
    frozen = _datetime(frozen_at, "frozen_at")
    if frozen < created:
        raise ForecastGen03Error("frozen_at precedes forecast_created_at")

    output = copy.deepcopy(dict(forecast))
    output["prediction_hash"] = _prediction_hash(forecast)
    output["freeze_status"] = "FROZEN"
    output["frozen_at"] = frozen_at
    return output


def audit_frozen_forecast(
    frozen: Mapping[str, object],
) -> dict[str, object]:
    if _text(frozen.get("freeze_status")) != "FROZEN":
        raise ForecastGen03Error("freeze_status must be FROZEN")
    expected = _text(frozen.get("prediction_hash")).lower()
    if len(expected) != 64:
        raise ForecastGen03Error("prediction_hash invalid")
    actual = _prediction_hash(frozen)
    return {
        "forecast_id": _text(frozen.get("forecast_id")),
        "forecast_version": FORECAST_VERSION,
        "prediction_hash": expected,
        "recomputed_hash": actual,
        "hash_match": expected == actual,
        "audit_status": "PASS" if expected == actual else "FAIL",
        "freeze_status": "FROZEN",
        "post_freeze_layers_may_open": expected == actual,
    }
