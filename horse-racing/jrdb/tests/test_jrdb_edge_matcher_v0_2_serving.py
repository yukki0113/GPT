from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import jrdb_edge_matcher_v0_2 as matcher


def _edge(
    edge_id: str,
    status: str,
    level: str,
    signal: str,
    group: str,
    specificity: int,
) -> dict:
    return {
        "edge_id": edge_id,
        "status": status,
        "registry_status": status,
        "display_text": edge_id,
        "polarity": signal,
        "family": "PEDIGREE",
        "performance_signal": signal,
        "value_signal": "NEUTRAL",
        "performance_evidence_level": level,
        "value_evidence_level": "NONE",
        "redundancy_group_id": group,
        "specificity": specificity,
        "conditions": {
            "template_id": "T",
            "anchor": {"sire_name": "S"},
            "modifiers": {"distance_m": 1600},
        },
    }


RUNNER = {
    "race_date": "2026-09-12",
    "sire_name": "S",
    "distance_m": 1600,
}


def test_confirmed_only_excludes_suggestive() -> None:
    registry = [
        _edge("A", "ACTIVE", "CONFIRMED", "POSITIVE", "G", 1),
        _edge("S", "REJECTED", "SUGGESTIVE", "POSITIVE", "G", 2),
    ]

    rows = matcher.match_runner(registry, RUNNER)

    assert [row["edge_id"] for row in rows] == ["A"]


def test_standard_confirmed_precedes_same_direction_suggestive() -> None:
    registry = [
        _edge("A", "ACTIVE", "CONFIRMED", "POSITIVE", "G", 1),
        _edge("S", "REJECTED", "SUGGESTIVE", "POSITIVE", "G", 2),
    ]

    rows = matcher.match_runner(
        registry,
        RUNNER,
        profile=matcher.PROFILE_STANDARD,
    )
    by_id = {row["edge_id"]: row for row in rows}

    assert by_id["A"]["presentation"]["performance"]["role"] == "PRIMARY"
    assert by_id["S"]["presentation"]["performance"]["role"] == "SECONDARY"


def test_opposite_direction_is_retained_as_conflict() -> None:
    registry = [
        _edge("P", "REJECTED", "SUGGESTIVE", "POSITIVE", "G", 1),
        _edge("N", "REJECTED", "SUGGESTIVE", "NEGATIVE", "G", 2),
    ]

    rows = matcher.match_runner(
        registry,
        RUNNER,
        profile=matcher.PROFILE_STANDARD,
    )

    assert {row["presentation"]["performance"]["role"] for row in rows} == {"CONFLICT"}
    assert all(row["presentation"]["performance"]["conflict"] for row in rows)


def test_legacy_active_publication_remains_compatible() -> None:
    legacy = {
        "edge_id": "L",
        "status": "ACTIVE",
        "display_text": "legacy",
        "polarity": "POSITIVE",
        "conditions": {
            "anchor": {"sire_name": "S"},
            "modifiers": {"distance_m": 1600},
        },
    }

    assert matcher.edge_matches_runner(legacy, RUNNER) is not None
