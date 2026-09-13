from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import racenote_forecast_gen0 as gen0  # noqa: E402


def _horse(
    horse_no: int,
    rank: int,
    mark: str,
    name: str,
) -> dict:
    """Build one compact horse-comparison fixture."""
    return {
        "horse_no": horse_no,
        "horse_name": name,
        "gpt_rank": rank,
        "mark": mark,
        "strengths": "強み",
        "risks": "リスク",
        "evidence_summary": "RaceNote evidence summary",
        "evidence_conflicts": "",
        "relative_comparison": "近い候補との比較",
        "primary_factor_codes": ["F01"],
        "supporting_factor_codes": ["F03"],
        "risk_factor_codes": ["F04"],
        "ability_reading": "能力評価",
        "suitability_reading": "適性評価",
        "pace_position_reading": "展開評価",
        "condition_training_reading": "状態評価",
        "recent_form_reading": "近走評価",
        "history_reading": "履歴評価",
        "context_reading": "補助統計評価",
        "uncertainty": "小",
    }


def _forecast() -> dict:
    """Build a valid blinded historical Gen0 forecast fixture."""
    return {
        "generation_id": "Gen0-G000",
        "target_date": "2025-08-24",
        "venue": "新潟",
        "race_no": 11,
        "race_key": "04250811",
        "evaluation_mode": "BLINDED_HISTORICAL",
        "source": {
            "schema": "1.0",
            "reader_view_version": "0.1",
            "semantic_sha256": "a" * 64,
            "artifact_ref": "race_bundle_20250824_新潟_11.json",
        },
        "forecast_created_at": "2026-09-13T13:10:00+09:00",
        "pre_race_guard_status": "PASS",
        "result_visibility_status": "HIDDEN",
        "race_reading": {
            "shape_summary": "先行馬が少なく前寄りを重視する",
            "expected_pace": "M",
            "important_condition_factors": "位置取りと基礎能力の両立",
            "primary_factor_codes": ["F03", "F01"],
            "de_emphasized_factor_codes": ["F08"],
        },
        "horses": [
            _horse(3, 1, "◎", "テストホースA"),
            _horse(7, 2, "○", "テストホースB"),
            _horse(1, 3, "▲", "テストホースC"),
        ],
        "factor_usage": [
            {
                "factor_code": "F03",
                "scope": "RACE",
                "importance": "HIGH",
                "direction": "POSITIVE",
                "role": "PRIMARY",
                "judgment_summary": "前有利と判断",
                "evidence_summary": "脚質構成と予測位置",
                "evidence_ref": "pace",
                "pre_result_note": "",
            },
            {
                "factor_code": "F04",
                "scope": "HORSE",
                "horse_no": 3,
                "importance": "MEDIUM",
                "direction": "MIXED",
                "role": "RISK",
                "judgment_summary": "状態は上向きだが絶対視しない",
                "evidence_summary": "training / condition",
                "evidence_ref": "horse:3",
                "pre_result_note": "",
            },
        ],
        "final_prediction": {
            "axis_horse_no": 3,
            "confidence": "B",
            "axis_reason": "能力上位に加えて今回の位置取りが最も噛み合う",
            "uncertainty_summary": "展開想定が外れた場合は差が縮まる",
            "alternatives": "7番",
        },
    }


def test_freeze_and_projection_are_deterministic() -> None:
    """A valid forecast freezes and projects to all pre-result ledger tabs."""
    frozen = gen0.freeze_forecast(
        _forecast(),
        "2026-09-13T13:11:00+09:00",
    )
    rows = gen0.to_ledger_rows(frozen)

    assert frozen["freeze_status"] == "FROZEN"
    assert len(frozen["prediction_hash"]) == 64
    assert rows["予想Freeze"][0]["mark_◎"] == "3"
    assert rows["予想Freeze"][0]["evaluation_mode"] == "BLINDED_HISTORICAL"
    assert rows["馬別評価"][0]["race_horse_key"] == "0425081103"
    assert rows["ファクター使用"][0]["factor_name"] == "展開・位置取り"
    assert rows["Freeze監査"][0]["audit_status"] == "PASS"


def test_hash_is_stable_for_same_prediction() -> None:
    """The same normalized prediction body produces the same hash."""
    first = gen0.freeze_forecast(
        _forecast(),
        "2026-09-13T13:11:00+09:00",
    )
    second = gen0.freeze_forecast(
        _forecast(),
        "2026-09-13T13:12:00+09:00",
    )
    assert first["prediction_hash"] == second["prediction_hash"]


def test_result_field_is_rejected_before_freeze() -> None:
    """Post-race fields fail closed anywhere in the pre-result payload."""
    payload = _forecast()
    payload["horses"][0]["finish_position"] = 1
    with pytest.raises(gen0.ForecastValidationError, match="post-race field"):
        gen0.freeze_forecast(payload, "2026-09-13T13:11:00+09:00")


def test_axis_must_equal_single_double_circle_mark() -> None:
    """The axis is a GPT conclusion but its record must be internally consistent."""
    payload = _forecast()
    payload["final_prediction"]["axis_horse_no"] = 7
    with pytest.raises(gen0.ForecastValidationError, match="axis_horse_no must be the ◎"):
        gen0.freeze_forecast(payload, "2026-09-13T13:11:00+09:00")


def test_primary_factor_cannot_be_deemphasized_simultaneously() -> None:
    """Factor-observation metadata must not contradict itself."""
    payload = _forecast()
    payload["race_reading"]["de_emphasized_factor_codes"] = ["F03"]
    with pytest.raises(gen0.ForecastValidationError, match="both primary and de-emphasized"):
        gen0.freeze_forecast(payload, "2026-09-13T13:11:00+09:00")


def test_tampering_is_detected_by_freeze_audit() -> None:
    """Post-freeze edits to prediction content invalidate the hash audit."""
    frozen = gen0.freeze_forecast(
        _forecast(),
        "2026-09-13T13:11:00+09:00",
    )
    tampered = copy.deepcopy(frozen)
    tampered["final_prediction"]["axis_reason"] = "事後に書き換えた理由"
    audit = gen0.audit_frozen_forecast(tampered)
    assert audit["hash_match"] is False
    assert audit["audit_status"] == "FAIL"


def test_result_must_be_acquired_after_freeze() -> None:
    """Result acquisition at or before freeze time fails forward integrity."""
    frozen = gen0.freeze_forecast(
        _forecast(),
        "2026-09-13T13:11:00+09:00",
    )
    audit = gen0.audit_frozen_forecast(
        frozen,
        result_acquired_at="2026-09-13T13:10:59+09:00",
    )
    assert audit["freeze_before_result"] is False
    assert audit["audit_status"] == "FAIL"


def test_true_forward_mode_is_accepted() -> None:
    """The same contract can later serve genuine current-race forecasts."""
    payload = _forecast()
    payload["evaluation_mode"] = "TRUE_FORWARD"
    frozen = gen0.freeze_forecast(
        payload,
        "2026-09-13T13:11:00+09:00",
    )
    assert frozen["evaluation_mode"] == "TRUE_FORWARD"
