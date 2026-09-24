from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import audit_jrdb_edge_v03_incremental_shadow as b1  # noqa: E402
import audit_jrdb_edge_v03_statistical_shadow as target  # noqa: E402


def test_bh_qvalues_preserve_order_and_control_monotonicity() -> None:
    values = [0.01, 0.04, 0.03, None]
    q = target._bh_qvalues(values)
    assert q[0] == 0.03
    assert q[1] == 0.04
    assert q[2] == 0.04
    assert q[3] is None


def test_two_proportion_detects_clear_difference() -> None:
    child = b1._metric(200, 80, 20000)
    comp = b1._metric(200, 40, 20000)
    p_value = target._two_proportion_p_value(child, comp)
    assert p_value is not None
    assert p_value < 0.001


def test_temporal_grid_reports_direction_sensitivity() -> None:
    years = [
        {
            "year": 2022,
            "child": b1._metric(20, 8, 2000),
            "parent_complement": b1._metric(20, 4, 2000),
            "incremental_place_rate_diff": 0.20,
            "incremental_place_roi_diff": 0.00,
        },
        {
            "year": 2023,
            "child": b1._metric(20, 7, 2000),
            "parent_complement": b1._metric(20, 5, 2000),
            "incremental_place_rate_diff": 0.10,
            "incremental_place_roi_diff": 0.00,
        },
        {
            "year": 2024,
            "child": b1._metric(4, 0, 0),
            "parent_complement": b1._metric(4, 2, 1000),
            "incremental_place_rate_diff": -0.50,
            "incremental_place_roi_diff": -2.50,
        },
    ]
    result = target._temporal_grid(years, "incremental_place_rate_diff", "POSITIVE")
    assert result["1"]["eligible_years"] == 3
    assert result["1"]["same_direction_years"] == 2
    assert result["1"]["opposite_direction_years"] == 1
    assert result["5"]["eligible_years"] == 2
    assert result["5"]["sign_consistency"] == 1.0


def test_bootstrap_is_deterministic_and_positive_for_strong_signal() -> None:
    years = []
    for year in range(2020, 2024):
        years.append(
            {
                "year": year,
                "child": b1._metric(100, 40, 10000),
                "parent_complement": b1._metric(100, 20, 10000),
            }
        )
    first = target._bootstrap_performance(years, "EDGE-X", 1000, 0.95, "POSITIVE")
    second = target._bootstrap_performance(years, "EDGE-X", 1000, 0.95, "POSITIVE")
    assert first == second
    assert first["ci_low"] > 0
    assert first["ci_excludes_zero_in_full_direction"] is True


def test_group_spec_exact_frame_uses_zone_parent() -> None:
    row = {
        "template_id": "COURSE_EXACT_FRAME_V2",
        "conditions": {
            "template_id": "COURSE_EXACT_FRAME_V2",
            "anchor": {
                "venue_code": "06",
                "surface_code": "1",
                "distance_m": 1600,
                "frame_no": 8,
            },
            "modifiers": {},
        },
    }
    spec = target._group_spec(row)
    assert spec is not None
    assert spec["parent_name"] == "course_zone"
    assert spec["parent_key"] == ("06", "1", 1600, "OUTER")
    assert spec["child_key"] == ("06", "1", 1600, "OUTER", 8)
