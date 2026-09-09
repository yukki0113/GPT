"""Regression tests for frozen JRDB Edge canonical buckets."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jrdb_edge_canonical import (  # noqa: E402
    derive_transition_features,
    distance_bucket,
    distance_change_bucket,
    frame_zone,
    transition,
)


def test_frame_zone_boundaries():
    assert [frame_zone(v) for v in (1, 3, 4, 6, 7, 8)] == [
        "INNER", "INNER", "MIDDLE", "MIDDLE", "OUTER", "OUTER"
    ]


def test_distance_bucket_boundaries():
    expected = {
        -400: "LARGE_SHORTEN",
        -399: "SHORTEN",
        -200: "SHORTEN",
        -199: "SAME_BAND",
        199: "SAME_BAND",
        200: "EXTEND",
        399: "EXTEND",
        400: "LARGE_EXTEND",
    }
    assert {value: distance_bucket(value) for value in expected} == expected


def test_distance_change_is_current_minus_previous():
    assert distance_change_bucket(1800, 1600) == "EXTEND"
    assert distance_change_bucket(1200, 1600) == "LARGE_SHORTEN"


def test_transition_preserves_string_codes():
    assert transition("01", "1") == "01->1"
    assert transition("", "1") is None
    assert transition(None, "1") is None


def test_derive_transition_features_matches_contract():
    row = derive_transition_features(
        current_distance=1800,
        current_surface_code="2",
        current_frame_no=8,
        previous_distance=1600,
        previous_surface_code="1",
        previous_frame_no=4,
    )
    assert row == {
        "frame_zone": "OUTER",
        "distance_change_m": 200,
        "distance_change_bucket": "EXTEND",
        "surface_transition": "1->2",
        "frame_transition": "MIDDLE->OUTER",
    }


def test_missing_previous_fact_keeps_current_zone_only():
    row = derive_transition_features(
        current_distance=1600,
        current_surface_code="1",
        current_frame_no=2,
    )
    assert row["frame_zone"] == "INNER"
    assert row["distance_change_bucket"] is None
    assert row["surface_transition"] is None
    assert row["frame_transition"] is None
