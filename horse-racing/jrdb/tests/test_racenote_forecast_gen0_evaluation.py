from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import racenote_forecast_gen0 as gen0  # noqa: E402
import racenote_forecast_gen0_evaluation as evaluation  # noqa: E402


def _forecast() -> dict:
    """Build and freeze a compact Gen0 fixture."""
    payload = {
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
            "artifact_ref": "race_bundle.json",
        },
        "forecast_created_at": "2026-09-13T13:10:00+09:00",
        "pre_race_guard_status": "PASS",
        "result_visibility_status": "HIDDEN",
        "race_reading": {
            "shape_summary": "前寄り",
            "expected_pace": "M",
            "important_condition_factors": "位置取り",
            "primary_factor_codes": ["F03"],
            "de_emphasized_factor_codes": ["F08"],
        },
        "horses": [
            {
                "horse_no": 3,
                "horse_name": "A",
                "gpt_rank": 1,
                "mark": "◎",
                "primary_factor_codes": ["F03"],
                "supporting_factor_codes": ["F01"],
                "risk_factor_codes": ["F04"],
            },
            {
                "horse_no": 7,
                "horse_name": "B",
                "gpt_rank": 2,
                "mark": "○",
                "primary_factor_codes": ["F01"],
                "supporting_factor_codes": ["F03"],
                "risk_factor_codes": [],
            },
            {
                "horse_no": 1,
                "horse_name": "C",
                "gpt_rank": 3,
                "mark": "▲",
                "primary_factor_codes": ["F01"],
                "supporting_factor_codes": [],
                "risk_factor_codes": ["F02"],
            },
        ],
        "factor_usage": [
            {
                "factor_code": "F03",
                "scope": "RACE",
                "importance": "HIGH",
                "direction": "POSITIVE",
                "role": "PRIMARY",
                "judgment_summary": "前有利",
                "evidence_summary": "pace",
            },
            {
                "factor_code": "F04",
                "scope": "HORSE",
                "horse_no": 3,
                "importance": "MEDIUM",
                "direction": "MIXED",
                "role": "RISK",
                "judgment_summary": "状態に不確実性",
                "evidence_summary": "training",
            },
        ],
        "final_prediction": {
            "axis_horse_no": 3,
            "confidence": "B",
            "axis_reason": "展開と能力",
            "uncertainty_summary": "展開次第",
            "alternatives": "7",
        },
    }
    return gen0.freeze_forecast(
        payload,
        "2026-09-13T13:11:00+09:00",
    )


def _results() -> list[dict]:
    """Return one complete official result fixture."""
    return [
        {
            "horse_no": 1,
            "finish_position": 3,
            "final_odds": 8.1,
            "final_popularity": 4,
        },
        {
            "horse_no": 3,
            "finish_position": 2,
            "final_odds": 3.2,
            "final_popularity": 1,
        },
        {
            "horse_no": 7,
            "finish_position": 1,
            "final_odds": 5.0,
            "final_popularity": 2,
        },
    ]


def _review() -> dict:
    """Return one qualitative reading review fixture."""
    return {
        "race_reading_grade": "MIXED",
        "ability_reading_eval": "GOOD",
        "suitability_eval": "GOOD",
        "pace_position_eval": "POOR",
        "condition_training_eval": "MIXED",
        "recent_form_eval": "GOOD",
        "history_eval": "GOOD",
        "uncertainty_eval": "GOOD",
        "primary_failure_category": "PACE_OVERVALUATION",
        "post_race_summary": "展開を重く見すぎて○を◎より下に置いた。",
    }


def _factor_reviews() -> list[dict]:
    """Return post-race reviews for every frozen factor usage row."""
    return [
        {
            "factor_code": "F03",
            "post_relevance": "MISLEADING",
            "outcome_summary": "想定した前有利が成立しなかった。",
            "over_under_eval": "OVER",
            "evidence_quality": "MIXED",
            "recurring_pattern_tag": "PACE_OVER",
        },
        {
            "factor_code": "F04",
            "horse_no": 3,
            "post_relevance": "NEUTRAL",
            "outcome_summary": "状態懸念は勝敗の主因と確認できない。",
            "over_under_eval": "APPROPRIATE",
            "evidence_quality": "UNRESOLVED",
        },
    ]


def test_build_post_race_rows_keeps_prediction_immutable() -> None:
    """Post-race projection computes objective metrics on separate rows."""
    frozen = _forecast()
    before_hash = frozen["prediction_hash"]
    output = evaluation.build_post_race_rows(
        frozen,
        _results(),
        {"ref": "SED-result", "sha256": "b" * 64},
        "2026-09-13T13:20:00+09:00",
        _review(),
        _factor_reviews(),
        "2026-09-13T13:25:00+09:00",
    )

    assert frozen["prediction_hash"] == before_hash
    assert output["振返り"][0]["axis_finish"] == 2
    assert output["振返り"][0]["axis_win_flag"] is False
    assert output["振返り"][0]["winner_horse_no"] == "7"
    assert output["振返り"][0]["winner_mark"] == "○"
    assert output["振返り"][0]["winner_in_marks"] is True
    assert output["振返り"][0]["top3_marks_count"] == 3
    assert output["Freeze監査"][0]["audit_status"] == "PASS"
    assert len(output["ファクター検証"]) == 2


def test_incomplete_result_set_is_rejected() -> None:
    """Every frozen horse must have an official result or abnormal record."""
    frozen = _forecast()
    with pytest.raises(evaluation.EvaluationValidationError, match="incomplete"):
        evaluation.validate_result_rows(
            frozen,
            _results()[:-1],
            {"ref": "SED-result", "sha256": "b" * 64},
            "2026-09-13T13:20:00+09:00",
        )


def test_result_before_freeze_is_rejected() -> None:
    """Post-race processing fails closed when result time precedes freeze."""
    frozen = _forecast()
    with pytest.raises(
        evaluation.EvaluationValidationError,
        match="freeze-before-result",
    ):
        evaluation.validate_result_rows(
            frozen,
            _results(),
            {"ref": "SED-result", "sha256": "b" * 64},
            "2026-09-13T13:10:59+09:00",
        )


def test_all_pre_result_factor_usage_requires_review() -> None:
    """Factor effectiveness is reviewable only if every used factor is joined."""
    frozen = _forecast()
    with pytest.raises(evaluation.EvaluationValidationError, match="missing post-race factor review"):
        evaluation.build_post_race_rows(
            frozen,
            _results(),
            {"ref": "SED-result", "sha256": "b" * 64},
            "2026-09-13T13:20:00+09:00",
            _review(),
            _factor_reviews()[:-1],
            "2026-09-13T13:25:00+09:00",
        )
