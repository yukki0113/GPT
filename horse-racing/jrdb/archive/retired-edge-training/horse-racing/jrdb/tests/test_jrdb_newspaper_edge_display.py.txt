"""Focused tests for human-readable Newspaper Edge memo projection."""
from __future__ import annotations

import re
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


def test_sire_line_code_is_projected_with_jrdb_master_label() -> None:
    """Legacy sire-line codes are translated without changing raw evidence."""
    raw = _legacy_match(
        edge_id="SIRE-LINE-TURN",
        display_text="＋ 系統1206は右回り2000mで好走傾向",
        template_id="SIRE_LINE_TURN_DISTANCE_V1",
        anchor={"sire_line_code": "1206"},
        modifiers={"distance_m": 2000, "turn_code": "1"},
        performance_signal="POSITIVE",
    )

    memo = adapter.normalize_match(raw, context="test")

    assert memo["condition_text"] == "父系ヘイロー系は右回り2000m"
    assert memo["memo_text"] == "＋ 父系ヘイロー系は右回り2000mで好走傾向"
    assert memo["display_text"] == raw["display_text"]
    assert memo["evidence"] == raw["evidence"]


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


def test_v02_enabled_templates_are_projected_without_machine_codes() -> None:
    """Enabled v0.2 templates expose readable conditions while retaining raw evidence."""
    cases = [
        (
            "COURSE_EXACT_FRAME_V2",
            {"venue_code": "09", "surface_code": "2", "distance_m": 1800},
            {"frame_no": 2},
            "＋ venue_code=09 / surface_code=2 / distance_m=1800 / frame_no=2",
            "阪神ダート1800mの2枠",
        ),
        (
            "SIRE_BROODMARE_SIRE_V2",
            {"sire_name": "キズナ"},
            {"broodmare_sire_name": "キングカメハメハ"},
            "＋ キズナ産駒 / broodmare_sire_name=キングカメハメハ",
            "キズナ産駒×母父キングカメハメハ",
        ),
        (
            "SIRE_AGE_V2",
            {"sire_name": "キズナ"},
            {"horse_age": 3},
            "＋ キズナ産駒 / horse_age=3",
            "キズナ産駒は3歳",
        ),
        (
            "SIRE_VENUE_SURFACE_DISTANCE_V2",
            {"sire_name": "キズナ"},
            {"venue_code": "10", "surface_code": "1", "distance_m": 2000},
            "＋ キズナ産駒 / venue_code=10, surface_code=1, distance_m=2000",
            "キズナ産駒は小倉芝2000m",
        ),
        (
            "BROODMARE_SIRE_SURFACE_DISTANCE_V2",
            {"broodmare_sire_name": "キングカメハメハ"},
            {"surface_code": "2", "distance_m": 1800},
            "＋ broodmare_sire_name=キングカメハメハ / surface_code=2, distance_m=1800",
            "母父キングカメハメハはダート1800m",
        ),
        (
            "SIRE_TRACK_CONDITION_V2",
            {"sire_name": "キズナ"},
            {"surface_code": "1", "track_condition_bucket": "2"},
            "＋ キズナ産駒 / surface_code=1, track_condition_bucket=2",
            "キズナ産駒は芝・稍重馬場",
        ),
        (
            "RECENT_UPTREND_SURFACE_DISTANCE_V2",
            {"surface_code": "1", "distance_m": 1600},
            {"uptrend_code": "2"},
            "＋ surface_code=1 / distance_m=1600 / uptrend_code=2",
            "芝1600m・上昇度A",
        ),
        (
            "RECENT_TRAINING_ARROW_SURFACE_DISTANCE_V2",
            {"surface_code": "1", "distance_m": 1600},
            {"training_arrow_code": "1"},
            "＋ surface_code=1 / distance_m=1600 / training_arrow_code=1",
            "芝1600m・調教デキ抜群",
        ),
        (
            "RECENT_STABLE_EVAL_SURFACE_DISTANCE_V2",
            {"surface_code": "2", "distance_m": 1800},
            {"stable_evaluation_code": "4"},
            "＋ surface_code=2 / distance_m=1800 / stable_evaluation_code=4",
            "ダート1800m・厩舎評価弱気",
        ),
        (
            "RECENT_ROTATION_SURFACE_DISTANCE_V2",
            {"surface_code": "1", "distance_m": 2000},
            {"rotation_interval": 3},
            "＋ surface_code=1 / distance_m=2000 / rotation_interval=3",
            "芝2000m・ローテ間隔3",
        ),
        (
            "JOCKEY_VENUE_DISTANCE_V2",
            {"jockey_code": "10339"},
            {"venue_code": "05", "distance_m": 1600},
            "＋ jockey_code=10339 / venue_code=05 / distance_m=1600",
            "騎手×東京1600m",
        ),
    ]
    machine_pattern = re.compile(
        r"(?:_code|_bucket|venue_code|surface_code|distance_m|frame_no|horse_age|rotation_interval)="
    )

    for template_id, anchor, modifiers, display_text, expected_condition in cases:
        raw = _legacy_match(
            edge_id=template_id,
            display_text=display_text,
            template_id=template_id,
            anchor=anchor,
            modifiers=modifiers,
            performance_signal="POSITIVE",
        )

        memo = adapter.normalize_match(raw, context="test")

        assert memo["condition_text"] == expected_condition
        assert memo["memo_text"] == f"＋ {expected_condition}で好走傾向"
        assert not machine_pattern.search(memo["memo_text"])
        assert memo["display_text"] == display_text
        assert memo["evidence"] == raw["evidence"]


def test_rotation_zero_remains_human_readable() -> None:
    """A zero rotation interval is rendered as a number, not a field=value token."""
    raw = _legacy_match(
        edge_id="RECENT-ROTATION-ZERO",
        display_text="＋ surface_code=1 / distance_m=1200 / rotation_interval=0",
        template_id="RECENT_ROTATION_SURFACE_DISTANCE_V2",
        anchor={"surface_code": "1", "distance_m": 1200},
        modifiers={"rotation_interval": 0},
        performance_signal="POSITIVE",
    )

    memo = adapter.normalize_match(raw, context="test")

    assert memo["condition_text"] == "芝1200m・ローテ間隔0"
    assert memo["memo_text"] == "＋ 芝1200m・ローテ間隔0で好走傾向"


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
