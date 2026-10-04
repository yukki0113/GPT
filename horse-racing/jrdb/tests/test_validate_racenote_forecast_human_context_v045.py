from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from validate_racenote_forecast_human_context import validate_consistency_pass


def _record(verdict: str = "KEEP") -> dict:
    challenger = {"horse_no": 6, "horse_name": "Challenger"}
    delta2 = {"horse_no": 5, "horse_name": "Delta2"}
    final_delta2 = challenger if verdict == "SWAP" else delta2
    return {
        "research": {
            "logic_version": "RaceNote-Human-Context-Reader-0.4.5-candidate",
        },
        "prediction": {
            "marks": {
                "main": {"horse_no": 1, "horse_name": "Main"},
                "second": {"horse_no": 2, "horse_name": "Second"},
                "third": {"horse_no": 3, "horse_name": "Third"},
                "others": [
                    {"horse_no": 4, "horse_name": "Delta1"},
                    final_delta2,
                ],
            }
        },
        "decision_trace": {
            "consistency_pass": {
                "hierarchy_reviewed": True,
                "hierarchy_changed": False,
                "hierarchy_reason": None,
                "single_shot_promotion_reviewed": True,
                "single_shot_promoted": False,
                "single_shot_promotion_reason": None,
                "coverage_scan_reviewed": True,
                "coverage_scan": {
                    "unmarked_count": 7,
                    "shortlisted_horse_nos": [6, 7],
                },
                "coverage_best_challenger": challenger,
                "coverage_boundary": {
                    "current_delta2": delta2,
                    "direct_condition_comparison": (
                        "CHALLENGER_STRONGER" if verdict == "SWAP" else "DELTA2_STRONGER"
                    ),
                    "ability_comparison": "ROUGHLY_EQUAL",
                    "race_model_comparison": "ROUGHLY_EQUAL",
                },
                "coverage_verdict": verdict,
                "coverage_changed": verdict == "SWAP",
                "coverage_reason": "explicit support-boundary comparison completed",
                "change_attribution": (
                    "COVERAGE_CHALLENGER"
                    if verdict == "SWAP"
                    else "UNCHANGED_AFTER_INDEPENDENT_REVIEW"
                ),
            }
        },
    }


def test_v045_keep_trace_is_valid() -> None:
    assert validate_consistency_pass(_record("KEEP")) == []


def test_v045_swap_trace_is_valid() -> None:
    assert validate_consistency_pass(_record("SWAP")) == []


def test_v045_swap_requires_direct_condition_advantage() -> None:
    record = _record("SWAP")
    record["decision_trace"]["consistency_pass"]["coverage_boundary"][
        "direct_condition_comparison"
    ] = "ROUGHLY_EQUAL"
    errors = validate_consistency_pass(record)
    assert "SWAP requires challenger stronger on direct condition" in errors


def test_v045_no_eligible_trace_is_valid() -> None:
    record = _record("KEEP")
    cp = record["decision_trace"]["consistency_pass"]
    cp["coverage_scan"]["shortlisted_horse_nos"] = []
    cp["coverage_best_challenger"] = None
    cp["coverage_boundary"]["direct_condition_comparison"] = None
    cp["coverage_boundary"]["ability_comparison"] = None
    cp["coverage_boundary"]["race_model_comparison"] = None
    cp["coverage_verdict"] = "NO_ELIGIBLE_CHALLENGER"
    assert validate_consistency_pass(record) == []


def test_v045_no_eligible_rejects_shortlist() -> None:
    record = _record("KEEP")
    cp = record["decision_trace"]["consistency_pass"]
    cp["coverage_best_challenger"] = None
    cp["coverage_boundary"]["direct_condition_comparison"] = None
    cp["coverage_boundary"]["ability_comparison"] = None
    cp["coverage_boundary"]["race_model_comparison"] = None
    cp["coverage_verdict"] = "NO_ELIGIBLE_CHALLENGER"
    errors = validate_consistency_pass(record)
    assert "NO_ELIGIBLE_CHALLENGER requires empty shortlist" in errors
