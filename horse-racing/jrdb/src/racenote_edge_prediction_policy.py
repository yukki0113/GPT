#!/usr/bin/env python3
"""Deterministic RaceNote Edge consumer policies.

This module does not discover or match Edge conditions and does not compute the
v0.2 base model. It consumes an already ordered v0.2 top-five candidate set
and the canonical Edge Matcher output attached to those horses.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

VERSION = "1.1-P-gated-0.1"
MARKS = ("◎", "○", "▲", "△1", "△2")
CONFIDENCE_MAGNITUDE = {"A": 2, "B": 1}
SIGNALS = {"POSITIVE": 1, "NEGATIVE": -1}
AXIS_GOOD_GUARD = 0.04
EPS = 1e-12


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    return float(value)


def _horse_no(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("horse_no must be positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("horse_no must be positive integer") from exc
    if number <= 0 or str(number) != str(value).strip() and not isinstance(value, int):
        try:
            if float(value) != number:
                raise ValueError("horse_no must be positive integer")
        except (TypeError, ValueError) as exc:
            raise ValueError("horse_no must be positive integer") from exc
    return number


def _validate_top_five(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if len(rows) != 5:
        raise ValueError("exactly five v0.2 candidates are required")
    normalized: list[dict[str, Any]] = []
    seen: set[int] = set()
    for idx, row in enumerate(rows, 1):
        if not isinstance(row, Mapping):
            raise ValueError(f"candidate {idx} must be an object")
        no = _horse_no(row.get("horse_no"))
        if no in seen:
            raise ValueError(f"duplicate horse_no: {no}")
        seen.add(no)
        good = _number(row.get("good"), f"horse {no} good")
        ability = _number(row.get("ability_good"), f"horse {no} ability_good")
        if not 0 <= good <= 1 or not 0 <= ability <= 1:
            raise ValueError(f"horse {no} good/ability_good must be within [0,1]")
        matches = row.get("edge_matches", [])
        if not isinstance(matches, list):
            raise ValueError(f"horse {no} edge_matches must be a list")
        item = dict(row)
        item.update({"horse_no": no, "good": good, "ability_good": ability, "edge_matches": matches})
        normalized.append(item)
    base_good = normalized[0]["good"]
    if any(row["good"] > base_good + EPS for row in normalized[1:]):
        raise ValueError("v0.2 P1 must not have lower Good than a later top-five candidate")
    return normalized


def _eligible_signal(edge: Mapping[str, Any], signal_field: str) -> tuple[str, str, int] | None:
    if str(edge.get("status", "")) != "ACTIVE":
        return None
    evidence = edge.get("evidence")
    if not isinstance(evidence, Mapping):
        raise ValueError("ACTIVE Edge must contain evidence object")
    raw_signal = evidence.get(signal_field)
    if raw_signal in (None, ""):
        return None
    signal = str(raw_signal).upper()
    if signal == "NEUTRAL":
        return None
    if signal not in SIGNALS:
        raise ValueError(f"unsupported {signal_field}: {raw_signal}")
    family = evidence.get("family")
    if family in (None, ""):
        raise ValueError(f"eligible {signal_field} Edge requires evidence.family")
    confidence = str(edge.get("confidence_band", "")).upper()
    if confidence not in CONFIDENCE_MAGNITUDE:
        raise ValueError(f"eligible Edge requires confidence_band A/B: {edge.get('edge_id')}")
    review_due = evidence.get("review_due")
    if not isinstance(review_due, bool):
        raise ValueError(f"eligible Edge requires boolean evidence.review_due: {edge.get('edge_id')}")
    magnitude = CONFIDENCE_MAGNITUDE[confidence] - (1 if review_due else 0)
    magnitude = max(0, magnitude)
    return str(family), signal, magnitude


def aggregate_family_votes(matches: Sequence[Mapping[str, Any]], signal_field: str) -> dict[str, int]:
    """Aggregate eligible ACTIVE Edges to one signed vote per family."""
    strongest: dict[str, dict[str, int]] = defaultdict(lambda: {"POSITIVE": 0, "NEGATIVE": 0})
    for edge in matches:
        if not isinstance(edge, Mapping):
            raise ValueError("edge_matches entries must be objects")
        parsed = _eligible_signal(edge, signal_field)
        if parsed is None:
            continue
        family, signal, magnitude = parsed
        strongest[family][signal] = max(strongest[family][signal], magnitude)

    votes: dict[str, int] = {}
    for family in sorted(strongest):
        pos = strongest[family]["POSITIVE"]
        neg = strongest[family]["NEGATIVE"]
        if pos == neg:
            vote = 0
        elif pos > neg:
            vote = pos
        else:
            vote = -neg
        votes[family] = vote
    return votes


def _polarity(value: int) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def _clamp_tier(value: int) -> int:
    return max(-2, min(2, int(value)))


def _explanation_edge_ids(matches: Sequence[Mapping[str, Any]]) -> tuple[str | None, str | None]:
    ranked: dict[str, list[tuple[int, float, str]]] = {"POSITIVE": [], "NEGATIVE": []}
    for edge in matches:
        if not isinstance(edge, Mapping) or str(edge.get("status", "")) != "ACTIVE":
            continue
        evidence = edge.get("evidence")
        if not isinstance(evidence, Mapping):
            continue
        signal = str(evidence.get("performance_signal") or "").upper()
        if signal not in SIGNALS:
            continue
        confidence = str(edge.get("confidence_band") or "").upper()
        if confidence not in CONFIDENCE_MAGNITUDE:
            continue
        review_due = evidence.get("review_due")
        if not isinstance(review_due, bool):
            continue
        magnitude = max(0, CONFIDENCE_MAGNITUDE[confidence] - (1 if review_due else 0))
        strength = edge.get("strength_score")
        try:
            strength_value = float(strength) if strength is not None else 0.0
        except (TypeError, ValueError):
            strength_value = 0.0
        edge_id = str(edge.get("edge_id") or "")
        if edge_id:
            ranked[signal].append((magnitude, strength_value, edge_id))

    def pick(signal: str) -> str | None:
        rows = ranked[signal]
        if not rows:
            return None
        rows.sort(key=lambda x: (-x[0], -x[1], x[2]))
        return rows[0][2]

    return pick("POSITIVE"), pick("NEGATIVE")


def apply_policies(v0_top_five: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Apply frozen v1.0-R and authoritative v1.1-P gated policies.

    Input order is the original v0.2 mark order. Each row must contain
    ``horse_no``, ``good``, ``ability_good`` and ``edge_matches``.
    """
    horses = _validate_top_five(v0_top_five)
    base_good = horses[0]["good"]

    diagnostics: list[dict[str, Any]] = []
    for base_rank, horse in enumerate(horses, 1):
        performance_votes = aggregate_family_votes(horse["edge_matches"], "performance_signal")
        family_sum = sum(performance_votes.values())
        performance_tier = _clamp_tier(family_sum)
        performance_polarity = _polarity(family_sum)
        value_votes = aggregate_family_votes(horse["edge_matches"], "value_signal")
        value_tier = _clamp_tier(sum(value_votes.values()))
        support_id, oppose_id = _explanation_edge_ids(horse["edge_matches"])
        good_gap = base_good - horse["good"]
        diagnostics.append({
            "horse_no": horse["horse_no"],
            "base_rank": base_rank,
            "good": horse["good"],
            "ability_good": horse["ability_good"],
            "performance_family_votes": performance_votes,
            "family_vote_sum": family_sum,
            "performance_edge_tier": performance_tier,
            "performance_edge_polarity": performance_polarity,
            "value_family_votes": value_votes,
            "value_edge_tier": value_tier,
            "good_gap_from_base_axis": good_gap,
            "axis_eligible": good_gap <= AXIS_GOOD_GUARD + EPS,
            "supporting_edge_id": support_id,
            "opposing_edge_id": oppose_id,
        })

    by_no = {row["horse_no"]: row for row in diagnostics}

    v10_rows = []
    for horse in horses:
        d = by_no[horse["horse_no"]]
        edge_adjustment = 0.02 * d["performance_edge_tier"]
        edge_aware_good = min(1.0, max(0.0, horse["good"] + edge_adjustment))
        v10_rows.append((horse, edge_aware_good, edge_adjustment))
    v10_rows.sort(key=lambda x: (-x[1], -x[0]["good"], -x[0]["ability_good"], x[0]["horse_no"]))
    v10_order = [row[0]["horse_no"] for row in v10_rows]

    base_axis_no = horses[0]["horse_no"]
    base_polarity = by_no[base_axis_no]["performance_edge_polarity"]
    challengers = [
        horse for horse in horses[1:]
        if by_no[horse["horse_no"]]["axis_eligible"]
        and by_no[horse["horse_no"]]["performance_edge_polarity"] > base_polarity
    ]
    challengers.sort(key=lambda horse: (
        -by_no[horse["horse_no"]]["performance_edge_polarity"],
        -horse["good"],
        horse["horse_no"],
    ))
    selected_axis_no = challengers[0]["horse_no"] if challengers else base_axis_no
    v11_order = [selected_axis_no] + [horse["horse_no"] for horse in horses if horse["horse_no"] != selected_axis_no]

    v02_order = [horse["horse_no"] for horse in horses]

    def marked(order: Sequence[int]) -> list[dict[str, Any]]:
        return [{"mark": MARKS[idx], "horse_no": no} for idx, no in enumerate(order)]

    return {
        "policy_version": VERSION,
        "result_data_used": False,
        "v0_2_control": {
            "axis_horse_no": v02_order[0],
            "marks": marked(v02_order),
        },
        "v1_0_R_frozen": {
            "axis_horse_no": v10_order[0],
            "axis_changed": v10_order[0] != base_axis_no,
            "marks": marked(v10_order),
            "rows": [
                {
                    "horse_no": horse["horse_no"],
                    "edge_adjustment": adjustment,
                    "edge_aware_good": edge_good,
                }
                for horse, edge_good, adjustment in v10_rows
            ],
        },
        "v1_1_P_candidate": {
            "axis_horse_no": selected_axis_no,
            "axis_changed": selected_axis_no != base_axis_no,
            "base_axis_polarity": base_polarity,
            "axis_good_guard": AXIS_GOOD_GUARD,
            "marks": marked(v11_order),
        },
        "horses": diagnostics,
    }
