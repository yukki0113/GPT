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
    changed = verdict == "SWAP"
    return {
        "research": {
            "logic_version": "RaceNote-Human-Context-Reader-0.4.4-candidate",
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
                "hierarchy_reason": "reviewed",
                "single_shot_promotion_reviewed": True,
                "single_shot_promoted": False,
                "single_shot_promotion_reason": "reviewed",
                "coverage_scan_reviewed": True,
                "coverage_scan": {
                    "unmarked_count": 7,
                    "direct_condition_candidate_count": 2,
                    "shortlisted_horse_nos": [6, 7],
                },
                "coverage_best_challenger": challenger,
                "coverage_challenger_case": {
                    "direct_condition": "same distance recent evidence",
                    "ability_proximity": "no material gap",
                    "race_model_fit": "fits expected race shape",
                    "supporting_evidence": "training neutral",
                },
                "coverage_boundary": {
                    "current_delta2": delta2,
                    "direct_condition_comparison": "CHALLENGER_STRONGER",
                    "ability_comparison": "ROUGHLY_EQUAL",
                    "race_model_comparison": "ROUGHLY_EQUAL",
                    "supporting_evidence": "neutral",
                },
                "coverage_verdict": verdict,
                "coverage_changed": changed,
                "coverage_reason": "explicit support-boundary comparison completed",
                "change_attribution": (
                    "COVERAGE_CHALLENGER"
                    if changed
                    else "UNCHANGED_AFTER_INDEPENDENT_REVIEW"
                ),
            }
        },
    }


def test_v044_keep_trace_is_valid() -> None:
    assert validate_consistency_pass(_record("KEEP")) == []


def test_v044_swap_trace_is_valid() -> None:
    assert validate_consistency_pass(_record("SWAP")) == []


def test_v044_swap_requires_direct_condition_advantage() -> None:
    record = _record("SWAP")
    record["decision_trace"]["consistency_pass"]["coverage_boundary"][
        "direct_condition_comparison"
    ] = "ROUGHLY_EQUAL"
    errors = validate_consistency_pass(record)
    assert "SWAP requires challenger stronger on direct condition" in errors


def test_v044_no_eligible_requires_null_challenger() -> None:
    record = _record("KEEP")
    cp = record["decision_trace"]["consistency_pass"]
    cp["coverage_verdict"] = "NO_ELIGIBLE_CHALLENGER"
    cp["coverage_best_challenger"] = None
    cp["coverage_challenger_case"] = None
    cp["coverage_boundary"]["direct_condition_comparison"] = None
    cp["coverage_boundary"]["ability_comparison"] = None
    cp["coverage_boundary"]["race_model_comparison"] = None
    assert validate_consistency_pass(record) == []
