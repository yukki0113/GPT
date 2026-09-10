"""Focused tests for human-readable Newspaper Edge memo projection."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import jrdb_newspaper_edge_adapter as adapter  # noqa: E402


def _legacy_match(
    *,
    edge_id: str,
    display_text: str,
    template_id: str,
    anchor: dict[str, object],
    modifiers: dict[str, object],
    performance_signal: str,
) -> dict[str, object]:
    """Build one legacy matcher Edge with structured published evidence."""
    return {
        "edge_id": edge_id,
        "display_text": display_text,
        "status": "ACTIVE",
        "evidence": {
            "performance_signal": performance_signal,
            "template_id": template_id,
            "conditions": {
                "anchor": anchor,
                "modifiers": modifiers,
            },
        },
    }


def test_machine_pedigree_display_is_projected_to_japanese() -> None:
    """Legacy field=value text becomes a concise human-facing memo."""
    raw = _legacy_match(
        edge_id="SIRE-SURFACE",
        display_text="＋ ロードカナロア産駒 / distance_m=1600, surface_code=1",
        template_id="SIRE_SURFACE_DISTANCE_V1",
        anchor={"sire_name": "ロードカナロア"},
        modifiers={"distance_m": 1600, "surface_code": "1"},
        performance_signal="POSITIVE",
    )

    memo = adapter.normalize_match(raw, context="test")

    assert memo["condition_text"] == "ロードカナロア産駒は芝1600m"
    assert memo["memo_text"] == "＋ ロードカナロア産駒は芝1600mで好走傾向"
    assert memo["display_text"] == raw["display_text"]


def test_machine_transition_display_is_projected_to_japanese() -> None:
    """Canonical transition codes are translated without rematching the Edge."""
    raw = _legacy_match(
        edge_id="SIRE-TRANSITION",
        display_text="－ リオンディーズ産駒 / surface_transition=2->1",
        template_id="SIRE_SURFACE_TRANSITION_V1",
        anchor={"sire_name": "リオンディーズ"},
        modifiers={"surface_transition": "2->1"},
        performance_signal="NEGATIVE",
    )

    memo = adapter.normalize_match(raw, context="test")

    assert memo["condition_text"] == "リオンディーズ産駒はダート→芝替わり"
    assert memo["memo_text"] == "－ リオンディーズ産駒はダート→芝替わりで苦戦傾向"


def test_machine_course_display_is_projected_to_japanese() -> None:
    """Course/frame canonical codes are translated with official venue codes."""
    raw = _legacy_match(
        edge_id="COURSE-FRAME",
        display_text="＋ distance_m=1700 / surface_code=2 / venue_code=01 / frame_zone=MIDDLE",
        template_id="COURSE_FRAME_V1",
        anchor={"distance_m": 1700, "surface_code": "2", "venue_code": "01"},
        modifiers={"frame_zone": "MIDDLE"},
        performance_signal="POSITIVE",
    )

    memo = adapter.normalize_match(raw, context="test")

    assert memo["condition_text"] == "札幌ダート1700mの中枠"
    assert memo["memo_text"] == "＋ 札幌ダート1700mの中枠で好走傾向"


def test_existing_human_display_text_remains_authoritative() -> None:
    """Already human-authored display text is preserved verbatim."""
    raw = _legacy_match(
        edge_id="HUMAN-TEXT",
        display_text="＋ 東京芝1600mで好走傾向",
        template_id="COURSE_FRAME_V1",
        anchor={"distance_m": 1600, "surface_code": "1", "venue_code": "05"},
        modifiers={"frame_zone": "OUTER"},
        performance_signal="POSITIVE",
    )

    memo = adapter.normalize_match(raw, context="test")

    assert memo["memo_text"] == "＋ 東京芝1600mで好走傾向"
    assert memo["display_text"] == "＋ 東京芝1600mで好走傾向"
