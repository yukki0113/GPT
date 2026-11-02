from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import build_jrdb_edge_v03_shadow_catalog as target  # noqa: E402


def v02(edge_id: str, template: str, perf: str = "POSITIVE", value: str = "NEUTRAL") -> dict:
    return {
        "edge_id": edge_id,
        "conditions": {"template_id": template, "anchor": {}, "modifiers": {}},
        "performance_evidence_level": "CONFIRMED" if perf != "NEUTRAL" else "NONE",
        "performance_signal": perf,
        "value_evidence_level": "CONFIRMED" if value != "NEUTRAL" else "NONE",
        "value_signal": value,
    }


def test_orthogonal_carries_v02_channels_forward() -> None:
    row = target._annotate(
        v02("E1", "SIRE_DISTANCE_CHANGE_V1", "POSITIVE", "NEGATIVE"),
        {},
        {},
    )
    shadow = row["v03_shadow"]
    assert shadow["shadow_class"] == "ORTHOGONAL"
    assert shadow["reader_facing"] is True
    assert shadow["performance_signal"] == "POSITIVE"
    assert shadow["value_signal"] == "NEGATIVE"
    assert shadow["value_gate"] == "V02_CARRY_FORWARD"


def test_course_frame_is_context_only_even_without_b1_row() -> None:
    row = target._annotate(v02("E2", "COURSE_FRAME_V1"), {}, {})
    shadow = row["v03_shadow"]
    assert shadow["shadow_class"] == "CONTEXT_ONLY"
    assert shadow["reader_facing"] is False


def test_b2b_incremental_child_is_reader_facing_and_uses_incremental_direction() -> None:
    b2b = {
        "E3": {
            "edge_id": "E3",
            "hierarchy": "COURSE_EXACT_WITHIN_ZONE",
            "stage_b2b": {
                "shadow_class": "INCREMENTAL_PERFORMANCE",
                "reason": "INCREMENTAL_PERFORMANCE_GATE_PASS",
                "incremental_performance_direction": "NEGATIVE",
                "is_reversal_vs_v02": True,
            },
        }
    }
    row = target._annotate(
        v02("E3", "COURSE_EXACT_FRAME_V2", "POSITIVE"),
        {"E3": {"edge_id": "E3", "shadow_class": "RAW_INCREMENTAL_METRIC"}},
        b2b,
    )
    shadow = row["v03_shadow"]
    assert shadow["shadow_class"] == "INCREMENTAL_PERFORMANCE"
    assert shadow["reader_facing"] is True
    assert shadow["performance_signal"] == "NEGATIVE"
    assert shadow["value_signal"] == "NEUTRAL"
    assert shadow["is_reversal_vs_v02"] is True


def test_b2b_context_child_is_not_reader_facing() -> None:
    b2b = {
        "E4": {
            "edge_id": "E4",
            "hierarchy": "SIRE_SURFACE_WITHIN_DISTANCE",
            "stage_b2b": {
                "shadow_class": "CONTEXT_ONLY",
                "reason": "INCREMENTAL_PERFORMANCE_GATE_FAIL",
                "incremental_performance_direction": "POSITIVE",
                "is_reversal_vs_v02": False,
            },
        }
    }
    row = target._annotate(
        v02("E4", "SIRE_SURFACE_DISTANCE_V1"),
        {"E4": {"edge_id": "E4", "shadow_class": "RAW_INCREMENTAL_METRIC"}},
        b2b,
    )
    assert row["v03_shadow"]["shadow_class"] == "CONTEXT_ONLY"
    assert row["v03_shadow"]["reader_facing"] is False


def test_b1_insufficient_child_remains_insufficient() -> None:
    b1 = {
        "E5": {
            "edge_id": "E5",
            "shadow_class": "INSUFFICIENT",
            "reason": "PARENT_COMPLEMENT_EMPTY",
            "current_performance_signal": "NEGATIVE",
            "hierarchy": "SIRE_TURN_WITHIN_DISTANCE",
        }
    }
    row = target._annotate(v02("E5", "SIRE_TURN_DISTANCE_V1", "NEGATIVE"), b1, {})
    assert row["v03_shadow"]["shadow_class"] == "INSUFFICIENT"
    assert row["v03_shadow"]["reader_facing"] is False


def test_target_value_only_or_unaudited_row_is_fail_closed() -> None:
    row = target._annotate(
        v02("E6", "SIRE_VENUE_SURFACE_DISTANCE_V2", "NEUTRAL", "POSITIVE"),
        {},
        {},
    )
    shadow = row["v03_shadow"]
    assert shadow["shadow_class"] == "INSUFFICIENT"
    assert shadow["reader_facing"] is False
    assert shadow["value_signal"] == "NEUTRAL"
