from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import racenote_forecast_gen0_2 as g  # noqa: E402


def _horse(no, name, base_rank, final_rank, mark, wb, t2b, t3b, wf, t2f, t3f, direction="NONE"):
    return {
        "horse_no": no,
        "horse_name": name,
        "base_rank": base_rank,
        "final_rank": final_rank,
        "mark": mark,
        "p_win_base": wb,
        "p_top2_base": t2b,
        "p_top3_base": t3b,
        "p_win_final": wf,
        "p_top2_final": t2f,
        "p_top3_final": t3f,
        "primary_factor_codes": ["F01"],
        "supporting_factor_codes": [],
        "risk_factor_codes": [],
        "edge_overlay": {
            "matched_edge_ids": [] if direction == "NONE" else [f"E-{no}"],
            "edge_families": [] if direction == "NONE" else ["TEST"],
            "performance_signal_summary": "",
            "edge_adjustment_direction": direction,
            "edge_adjustment_reason": "",
            "axis_changed_due_to_edge": False,
        },
    }


def _forecast():
    return {
        "generation_id": "Gen0-G001",
        "target_date": "2025-01-01",
        "venue": "中山",
        "race_no": 1,
        "race_key": "06250101",
        "evaluation_mode": "BLINDED_HISTORICAL",
        "source": {
            "schema": "1.0",
            "reader_view_version": "0.1",
            "source_semantic_sha256": "a" * 64,
            "independent_semantic_sha256": "b" * 64,
            "artifact_ref": "test",
            "firewall_version": "Gen0.2-Firewall-0.1",
        },
        "input_firewall": {
            "jrdb_consensus_visibility_status": "HIDDEN",
            "market_visibility_status": "HIDDEN",
            "training_edge_forecast_status": "NOT_USED",
            "independent_view_audit_status": "PASS",
        },
        "edge_source": {
            "status": "USED",
            "performance_only": True,
            "value_signal_visibility_status": "HIDDEN_FROM_FORECAST",
            "asof_status": "PASS",
            "matcher_version": "test",
            "catalog_ref": "edge-catalog",
            "catalog_semantic_sha256": "c" * 64,
        },
        "forecast_created_at": "2026-09-17T09:00:00+09:00",
        "pre_race_guard_status": "PASS",
        "result_visibility_status": "HIDDEN",
        "race_reading": {
            "shape_summary": "独立に展開を推定",
            "expected_pace": "M",
            "important_condition_factors": "条件",
            "primary_factor_codes": ["F01"],
            "de_emphasized_factor_codes": ["F08"],
        },
        "horses": [
            _horse(1, "A", 1, 2, "○", 0.40, 0.75, 1.00, 0.35, 0.70, 1.00, "NEGATIVE"),
            _horse(2, "B", 2, 1, "◎", 0.35, 0.70, 1.00, 0.40, 0.76, 1.00, "POSITIVE"),
            _horse(3, "C", 3, 3, "▲", 0.25, 0.55, 1.00, 0.25, 0.54, 1.00),
        ],
        "factor_usage": [{
            "factor_code": "E01",
            "scope": "RACE",
            "impact": "STRONG",
            "direction": "MIXED",
            "evidence_quality": "GOOD",
            "role": "SUPPORT",
        }],
        "final_prediction": {
            "axis_horse_no": 2,
            "confidence": "B",
            "axis_reason": "base比較後にEdgeDB performanceも踏まえBを首位",
            "evidence_uncertainty": "MEDIUM",
            "uncertainty_reasons": "上位接近",
        },
    }


def test_freeze_probability_and_edge_projection():
    frozen = g.freeze_forecast(_forecast(), "2026-09-17T09:01:00+09:00")
    assert frozen["forecast_version"] == "RaceNote-Forecast-Gen0.2"
    assert len(frozen["base_snapshot_hash"]) == 64
    assert len(frozen["prediction_hash"]) == 64
    rows = g.to_ledger_rows(frozen)
    assert len(rows["確率評価"]) == 3
    assert len(rows["EdgeDB補正"]) == 3
    assert rows["予想Freeze"][0]["axis_horse_no"] == 2
    assert rows["予想Freeze"][0]["reader_view_version"] == "0.1"
    assert "firewall_version=Gen0.2-Firewall-0.1" in rows["予想Freeze"][0]["notes"]
    assert rows["ファクター使用"][0]["importance"] == "HIGH"
    assert g.audit_frozen_forecast(frozen)["audit_status"] == "PASS"


def test_value_signal_is_forbidden_in_prediction_overlay():
    bad = _forecast()
    bad["horses"][0]["edge_overlay"]["value_signal"] = "POSITIVE"
    with pytest.raises(g.ForecastValidationError):
        g.validate_forecast(bad)


def test_consensus_and_market_must_be_after_forecast_freeze():
    frozen = g.freeze_forecast(_forecast(), "2026-09-17T09:01:00+09:00")
    consensus = {
        "view_kind": "JRDB_CONSENSUS",
        "horses": [{
            "horse_no": 1,
            "ability": {"idm": 60, "total_index": 70},
            "jrdb_ratings": {"marks": {"total": "◎"}},
            "pace": {"forecast_positions": {"finish": {"order": 1}}},
        }],
    }
    with pytest.raises(g.ForecastValidationError):
        g.build_consensus_record(frozen, consensus, "2026-09-17T09:00:30+09:00")
    rec = g.build_consensus_record(frozen, consensus, "2026-09-17T09:02:00+09:00")
    assert rec["records"][0]["jrdb_idm"] == 60

    market = {
        "view_kind": "MARKET",
        "horses": [{"horse_no": 2, "market": {"base_win_odds": 4.0, "base_win_rank": 2}}],
    }
    mv = g.build_market_value_record(frozen, market, "2026-09-17T09:03:00+09:00")
    assert mv["records"][0]["fair_win_odds"] == pytest.approx(2.5)
    assert mv["records"][0]["win_ev_raw"] == pytest.approx(0.6)


def test_probability_totals_fail_closed():
    bad = _forecast()
    bad["horses"][0]["p_win_final"] = 0.55
    with pytest.raises(g.ForecastValidationError):
        g.validate_forecast(bad)
