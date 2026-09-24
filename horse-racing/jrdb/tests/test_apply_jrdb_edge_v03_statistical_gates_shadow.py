from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import apply_jrdb_edge_v03_statistical_gates_shadow as target  # noqa: E402


POLICY = {
    "performance_gate": {
        "multiple_testing": {"q_max": 0.05},
        "temporal": {
            "yearly_min_child_n": 10,
            "yearly_min_parent_complement_n": 10,
            "min_eligible_years": 6,
            "min_full_period_same_direction_fraction": 2 / 3,
            "recent_eligible_year_count": 4,
            "min_recent_same_direction_fraction": 0.75,
        },
    },
    "classification": {
        "performance_pass": "INCREMENTAL_PERFORMANCE",
        "insufficient_temporal_coverage": "INSUFFICIENT",
        "sufficient_but_gate_fail": "CONTEXT_ONLY",
    },
}


def row(
    *,
    q: float = 0.01,
    ci_pass: bool = True,
    years: int = 8,
    consistency: float = 0.75,
    recent: float = 0.75,
    current: str = "POSITIVE",
    incremental: str = "POSITIVE",
) -> dict:
    return {
        "edge_id": "EDGE-X",
        "template_id": "SIRE_SURFACE_DISTANCE_V1",
        "current_performance_signal": current,
        "performance": {
            "q_value_global_bh": q,
            "bootstrap": {
                "confidence": 0.95,
                "ci_low": 0.01,
                "ci_high": 0.10,
                "ci_excludes_zero_in_full_direction": ci_pass,
            },
            "temporal_sensitivity": {
                "10": {
                    "eligible_years": years,
                    "sign_consistency": consistency,
                    "recent4_sign_consistency": recent,
                }
            },
        },
        "b1_metrics": {
            "incremental_performance_direction": incremental,
        },
    }


def test_frozen_gate_passes_supported_incremental_performance() -> None:
    result = target._classify(row(), POLICY)
    assert result["stage_b2b"]["shadow_class"] == "INCREMENTAL_PERFORMANCE"
    assert result["stage_b2b"]["performance_gate_pass"] is True
    assert result["stage_b2b"]["failed_checks"] == []


def test_frozen_gate_keeps_supported_reversal() -> None:
    result = target._classify(
        row(current="POSITIVE", incremental="NEGATIVE"),
        POLICY,
    )
    assert result["stage_b2b"]["shadow_class"] == "INCREMENTAL_PERFORMANCE"
    assert result["stage_b2b"]["is_reversal_vs_v02"] is True


def test_temporal_coverage_failure_is_insufficient() -> None:
    result = target._classify(row(years=5), POLICY)
    assert result["stage_b2b"]["shadow_class"] == "INSUFFICIENT"
    assert "temporal_coverage" in result["stage_b2b"]["failed_checks"]


def test_significance_failure_is_absorbed_to_context() -> None:
    result = target._classify(row(q=0.20), POLICY)
    assert result["stage_b2b"]["shadow_class"] == "CONTEXT_ONLY"
    assert result["stage_b2b"]["performance_gate_pass"] is False
    assert "global_fdr_q" in result["stage_b2b"]["failed_checks"]


def test_recent_three_of_four_boundary_passes() -> None:
    result = target._classify(row(recent=0.75), POLICY)
    assert result["stage_b2b"]["shadow_class"] == "INCREMENTAL_PERFORMANCE"


def test_full_two_thirds_boundary_passes() -> None:
    result = target._classify(row(consistency=2 / 3), POLICY)
    assert result["stage_b2b"]["shadow_class"] == "INCREMENTAL_PERFORMANCE"
