"""Tests for JRDB Edge Registry pre-race matching."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import jrdb_edge_matcher as matcher  # noqa: E402


def edge(**kw):
    row = {
        "edge_id": "EDGE-1", "registry_version": "test", "family": "PEDIGREE",
        "validation_class": "LIFECYCLE", "policy_id": "LIFECYCLE_SIRE_V1",
        "polarity": "POSITIVE", "performance_signal": "POSITIVE", "value_signal": "NEUTRAL",
        "status": "ACTIVE", "display_text": "＋ SireA産駒", "strength_score": 32.0,
        "confidence_band": "A", "sample_n": 280, "unique_horses": 77, "unique_races": 190,
        "place_rate": .31, "place_roi": 1.04, "baseline_place_rate": .25, "performance_lift": 1.24,
        "last_validated_at": "2025-12-31", "next_review_at": "2026-06-29", "expires_at": "2027-12-31",
        "conditions": {"template_id": "SIRE_TURN_DISTANCE_V1", "template_version": "2026-09-09.v1",
                       "anchor": {"sire_name": "SireA"}, "modifiers": {"turn_code": "1", "distance_m": 1600},
                       "baseline": "same_anchor"},
    }
    row.update(kw); return row


def runner(**kw):
    row = {"race_key": "R1", "horse_no": 1, "race_date": "2026-09-09", "venue_code": "06",
           "surface_code": "1", "distance_m": 1600, "turn_code": "1", "frame_zone": "INNER",
           "sire_name": "SireA", "sire_line_code": "1206", "distance_change_bucket": "EXTEND",
           "surface_transition": "1->1", "frame_transition": "MIDDLE->INNER"}
    row.update(kw); return row


def test_exact_match_and_review_due():
    rows = matcher.match_runner([edge()], runner())
    assert [r["edge_id"] for r in rows] == ["EDGE-1"]
    assert rows[0]["evidence"]["review_due"] is True


def test_string_codes_are_not_numeric_coerced():
    assert matcher.match_runner([edge()], runner(turn_code=1)) == []


def test_missing_field_does_not_match():
    r = runner(); del r["turn_code"]
    assert matcher.match_runner([edge()], r) == []


def test_expired_is_not_served():
    assert matcher.match_runner([edge(expires_at="2026-08-31")], runner()) == []


def test_provisional_is_opt_in():
    e = edge(status="PROVISIONAL")
    assert matcher.match_runner([e], runner()) == []
    assert len(matcher.match_runner([e], runner(), statuses=("ACTIVE", "PROVISIONAL"))) == 1


def test_stronger_match_sorts_first():
    rows = matcher.match_runner([edge(edge_id="W", strength_score=10), edge(edge_id="S", strength_score=40)], runner())
    assert [r["edge_id"] for r in rows] == ["S", "W"]


def test_unsupported_condition_fails_closed(tmp_path: Path):
    e = edge(); e["conditions"]["modifiers"] = {"future_result": "x"}
    p = tmp_path / "r.jsonl"; p.write_text(json.dumps(e) + "\n", encoding="utf-8")
    try: matcher.load_registry(p)
    except ValueError as exc: assert "unsupported condition field" in str(exc)
    else: raise AssertionError("must fail closed")
