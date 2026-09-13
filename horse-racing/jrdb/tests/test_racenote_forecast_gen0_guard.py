from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import racenote_forecast_gen0 as gen0  # noqa: E402
import racenote_forecast_gen0_guard as guard  # noqa: E402


def _frozen() -> dict:
    """Build one valid frozen forecast for input-completeness tests."""
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
                "horse_no": 1,
                "horse_name": "A",
                "gpt_rank": 1,
                "mark": "◎",
                "primary_factor_codes": ["F01"],
                "supporting_factor_codes": ["F03"],
                "risk_factor_codes": [],
            },
            {
                "horse_no": 2,
                "horse_name": "B",
                "gpt_rank": 2,
                "mark": "○",
                "primary_factor_codes": ["F03"],
                "supporting_factor_codes": ["F01"],
                "risk_factor_codes": ["F04"],
            },
        ],
        "factor_usage": [
            {
                "factor_code": "F03",
                "scope": "RACE",
                "importance": "HIGH",
                "direction": "POSITIVE",
                "role": "PRIMARY",
            },
            {
                "factor_code": "F04",
                "scope": "HORSE",
                "horse_no": 2,
                "importance": "MEDIUM",
                "direction": "NEGATIVE",
                "role": "RISK",
            },
        ],
        "final_prediction": {
            "axis_horse_no": 1,
            "confidence": "B",
            "axis_reason": "能力と展開のバランス",
            "uncertainty_summary": "展開次第",
            "alternatives": "2",
        },
    }
    return gen0.freeze_forecast(
        payload,
        "2026-09-13T13:11:00+09:00",
    )


def _source_horses() -> list[dict]:
    """Return authoritative runner identities from the source race."""
    return [
        {"horse_no": 1, "horse_name": "A"},
        {"horse_no": 2, "horse_name": "B"},
    ]


def test_complete_runner_set_and_unique_factor_usage_pass() -> None:
    """A complete all-runner forecast passes the source-completeness guard."""
    audit = guard.audit_forecast_input_completeness(
        _frozen(),
        _source_horses(),
    )
    assert audit["audit_status"] == "PASS"
    assert audit["source_runner_count"] == 2
    assert audit["forecast_runner_count"] == 2
    assert audit["factor_usage_identity_unique"] is True


def test_missing_source_runner_is_rejected() -> None:
    """GPT cannot silently omit a runner from all-runner comparison."""
    frozen = _frozen()
    source = _source_horses() + [{"horse_no": 3, "horse_name": "C"}]
    with pytest.raises(guard.ForecastGuardError, match="coverage mismatch"):
        guard.audit_forecast_input_completeness(frozen, source)


def test_factor_usage_for_non_source_runner_is_rejected() -> None:
    """Horse-scoped factor notes must point to a runner in the source race."""
    frozen = _frozen()
    frozen["factor_usage"][1]["horse_no"] = 9
    frozen["prediction_hash"] = gen0.compute_prediction_hash(frozen)
    with pytest.raises(guard.ForecastGuardError, match="non-source horse_no"):
        guard.audit_forecast_input_completeness(frozen, _source_horses())


def test_duplicate_factor_usage_identity_is_rejected() -> None:
    """Duplicate factor records cannot create ambiguous post-race joins."""
    frozen = _frozen()
    duplicate = copy.deepcopy(frozen["factor_usage"][0])
    frozen["factor_usage"].append(duplicate)
    frozen["prediction_hash"] = gen0.compute_prediction_hash(frozen)
    with pytest.raises(guard.ForecastGuardError, match="duplicate factor usage identity"):
        guard.audit_forecast_input_completeness(frozen, _source_horses())
