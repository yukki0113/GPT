"""Regression tests for Phase1 Edge temporal validation and registry promotion gates."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import jrdb_edge_temporal_validator as validator  # noqa: E402


def _mart(tmp_path: Path) -> Path:
    path = tmp_path / "edge_mart.sqlite"
    connection = sqlite3.connect(path)
    connection.execute(
        """CREATE TABLE edge_runner_fact(
          race_key TEXT,horse_no INTEGER,race_date TEXT,venue_code TEXT,distance_m INTEGER,
          surface_code TEXT,turn_code TEXT,frame_zone TEXT,horse_id TEXT,sire_name TEXT,
          sire_line_code TEXT,broodmare_sire_name TEXT,broodmare_sire_line_code TEXT,
          jockey_code TEXT,trainer_code TEXT,distance_change_bucket TEXT,surface_transition TEXT,
          frame_transition TEXT,prev1_race_date TEXT,label_win_hit INTEGER,label_place_hit INTEGER,
          label_win_payout INTEGER,label_place_payout INTEGER,calculation_status TEXT
        )"""
    )
    rows = []
    serial = 0
    for year in range(2010, 2026):
        for index in range(20):
            race_date = f"{year}-{index % 12 + 1:02d}-{index % 27 + 1:02d}"
            horse_id = f"H{year}_{index}"
            target_hit = int(index % 2 == 0)
            serial += 1
            rows.append(
                (
                    f"R{serial}",1,race_date,"05",1600,"1","1","OUTER",horse_id,"SireA","1206",
                    None,None,"J","T","EXTEND","1->1","INNER->OUTER",f"{year - 1}-12-01",
                    0,target_hit,0,240 if target_hit else 0,"ELIGIBLE",
                )
            )
            baseline_hit = int(index % 4 == 0)
            serial += 1
            rows.append(
                (
                    f"R{serial}",2,race_date,"05",1800,"1","2","INNER",horse_id + "b","SireA","1206",
                    None,None,"J","T","SAME_BAND","1->1","INNER->INNER",f"{year - 1}-12-01",
                    0,baseline_hit,0,280 if baseline_hit else 0,"ELIGIBLE",
                )
            )
    connection.executemany(
        "INSERT INTO edge_runner_fact VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    connection.commit()
    connection.close()
    return path


def _candidate(policy_id: str) -> dict:
    return {
        "candidate_id": "EDGE-CAND-TEST",
        "template_id": "SIRE_TURN_DISTANCE_TEST",
        "template_version": "test.v1",
        "family": "PEDIGREE",
        "anchor_type": "sire",
        "anchor": {"sire_name": "SireA"},
        "modifiers": {"turn_code": "1", "distance_m": 1600},
        "baseline": "same_anchor",
        "policy_id": policy_id,
        "as_of_date": "2025-12-31",
        "first_observed_date": "2010-01-01",
        "last_observed_date": "2025-12-20",
    }


def test_lifecycle_candidate_requires_multi_period_consistency(tmp_path: Path) -> None:
    catalog = json.loads((ROOT / "config/jrdb_edge_validation_policies_v0_1.json").read_text(encoding="utf-8"))
    result = validator.validate_candidate(_mart(tmp_path), _candidate("LIFECYCLE_SIRE_V1"), catalog)
    assert result["status"] == "ACTIVE"
    assert result["performance_signal"] == "POSITIVE"
    assert result["value_signal"] == "POSITIVE"
    assert result["performance_consistency_ratio"] == 1.0
    assert result["value_consistency_ratio"] == 1.0
    assert len(result["slices"]) == 3


def test_negative_value_is_relative_to_anchor_not_absolute_100_percent() -> None:
    catalog = json.loads((ROOT / "config/jrdb_edge_validation_policies_v0_1.json").read_text(encoding="utf-8"))
    policy = catalog["policies"]["LIFECYCLE_SIRE_V1"]
    performance, value = validator.classify_signals(
        {"performance_lift": 1.0, "place_roi_vs_baseline": 0.80, "place_roi": 1.05},
        policy,
    )
    assert performance == "NEUTRAL"
    assert value == "NEGATIVE"


def test_emerging_candidate_cannot_skip_provisional_stage(tmp_path: Path) -> None:
    catalog = json.loads((ROOT / "config/jrdb_edge_validation_policies_v0_1.json").read_text(encoding="utf-8"))
    candidate = _candidate("EMERGING_SIRE_V1")
    result = validator.validate_candidate(_mart(tmp_path), candidate, catalog)
    assert result["status"] == "PROVISIONAL"
    assert result["decision"] == "PROVISIONAL"


def test_two_of_three_consistency_meets_two_thirds_policy_boundary(tmp_path: Path, monkeypatch) -> None:
    catalog = json.loads((ROOT / "config/jrdb_edge_validation_policies_v0_1.json").read_text(encoding="utf-8"))
    candidate = _candidate("LIFECYCLE_SIRE_V1")
    candidate["as_of_date"] = "2026-08-23"
    calls = {"count": 0}

    def fake_metrics(*args, **kwargs):
        calls["count"] += 1
        lift = 1.20 if calls["count"] != 4 else 0.90
        return {
            "sample_n": 150 if calls["count"] == 1 else 30,
            "unique_horses": 30,
            "unique_races": 100,
            "baseline_first_date": "2026-01-01",
            "largest_horse_sample_share": 0.05,
            "largest_return_share": 0.10,
            "performance_lift": lift,
            "place_roi_vs_baseline": 1.0,
            "place_roi": 0.8,
        }

    monkeypatch.setattr(validator, "_metrics", fake_metrics)
    result = validator.validate_candidate(tmp_path / "edge.sqlite", candidate, catalog)
    assert result["performance_consistency_ratio"] == 2 / 3
    assert "PERFORMANCE_TIME_INSTABILITY" not in result["failure_reasons"]
    assert result["status"] == "ACTIVE"
