from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import audit_jrdb_edge_v03_incremental_shadow as target  # noqa: E402


def m(n: int, hits: int, payout: float) -> dict:
    return target._metric(n, hits, payout)


def edge(template: str, values: dict, *, signal: str = "POSITIVE") -> dict:
    return {
        "edge_id": f"{template}-1",
        "performance_signal": signal,
        "performance_evidence_level": "CONFIRMED",
        "value_signal": "NEUTRAL",
        "value_evidence_level": "NONE",
        "conditions": {
            "template_id": template,
            "anchor": values,
            "modifiers": {},
        },
    }


def test_residual_uses_parent_complement_not_parent_average() -> None:
    child = m(20, 8, 2600)
    parent = m(100, 25, 10500)
    result = target._residual(child, parent)
    assert result["parent_complement"]["n"] == 80
    assert result["parent_complement"]["place_hits"] == 17
    assert result["parent_complement"]["place_payout_sum"] == 7900.0
    assert result["incremental_place_rate_diff"] == 0.4 - (17 / 80)
    assert result["incremental_performance_direction"] == "POSITIVE"


def test_exact_frame_is_evaluated_inside_frame_zone() -> None:
    candidate = edge(
        "COURSE_EXACT_FRAME_V2",
        {"venue_code": "06", "surface_code": "1", "distance_m": 1600, "frame_no": 8},
        signal="NEGATIVE",
    )
    agg = {
        "course_zone": {("06", "1", 1600, "OUTER"): m(100, 25, 10000)},
        "course_exact": {("06", "1", 1600, "OUTER", 8): m(40, 5, 2200)},
        "sire_distance": {},
        "sire_surface": {},
        "sire_turn": {},
        "sire_venue_surface": {},
    }
    result = target._evaluate_edge(candidate, agg)
    assert result["shadow_class"] == "RAW_INCREMENTAL_METRIC"
    assert result["metrics"]["parent_complement"]["n"] == 60
    assert result["metrics"]["incremental_performance_direction"] == "NEGATIVE"
    assert result["direction_alignment"]["performance_matches_current"] is True


def test_sire_surface_uses_virtual_sire_distance_context() -> None:
    candidate = edge(
        "SIRE_SURFACE_DISTANCE_V1",
        {"sire_name": "SIRE", "distance_m": 1800, "surface_code": "1"},
        signal="POSITIVE",
    )
    agg = {
        "course_zone": {},
        "course_exact": {},
        "sire_distance": {("SIRE", 1800): m(100, 25, 10000)},
        "sire_surface": {("SIRE", 1800, "1"): m(60, 20, 7200)},
        "sire_turn": {},
        "sire_venue_surface": {},
    }
    result = target._evaluate_edge(candidate, agg)
    assert result["hierarchy"] == "SIRE_SURFACE_WITHIN_DISTANCE"
    assert result["metrics"]["parent_complement"]["n"] == 40
    assert result["metrics"]["incremental_performance_direction"] == "POSITIVE"


def test_course_frame_is_context_only() -> None:
    candidate = edge(
        "COURSE_FRAME_V1",
        {"venue_code": "09", "surface_code": "2", "distance_m": 1800, "frame_zone": "INNER"},
    )
    agg = {
        "course_zone": {("09", "2", 1800, "INNER"): m(120, 30, 11000)},
        "course_exact": {},
        "sire_distance": {},
        "sire_surface": {},
        "sire_turn": {},
        "sire_venue_surface": {},
    }
    result = target._evaluate_edge(candidate, agg)
    assert result["shadow_class"] == "CONTEXT_ONLY"
    assert result["reason"] == "LOWER_ORDER_CONTEXT"


def test_empty_parent_complement_is_insufficient() -> None:
    candidate = edge(
        "SIRE_VENUE_SURFACE_DISTANCE_V2",
        {"sire_name": "SIRE", "distance_m": 2000, "surface_code": "1", "venue_code": "05"},
    )
    same = m(10, 4, 5000)
    agg = {
        "course_zone": {},
        "course_exact": {},
        "sire_distance": {},
        "sire_surface": {("SIRE", 2000, "1"): same},
        "sire_turn": {},
        "sire_venue_surface": {("SIRE", 2000, "1", "05"): same},
    }
    result = target._evaluate_edge(candidate, agg)
    assert result["shadow_class"] == "INSUFFICIENT"
    assert result["reason"] == "EMPTY_PARENT_COMPLEMENT"

def test_performance_alignment_bucket_keeps_neutral_separate() -> None:
    same = {
        "current_performance_signal": "POSITIVE",
        "metrics": {"incremental_performance_direction": "POSITIVE"},
        "direction_alignment": {"performance_matches_current": True},
    }
    opposite = {
        "current_performance_signal": "POSITIVE",
        "metrics": {"incremental_performance_direction": "NEGATIVE"},
        "direction_alignment": {"performance_matches_current": False},
    }
    neutral = {
        "current_performance_signal": "POSITIVE",
        "metrics": {"incremental_performance_direction": "NEUTRAL"},
        "direction_alignment": {"performance_matches_current": False},
    }
    assert target._performance_alignment_bucket(same) == "performance_same"
    assert target._performance_alignment_bucket(opposite) == "performance_opposite"
    assert target._performance_alignment_bucket(neutral) == "performance_neutral"

