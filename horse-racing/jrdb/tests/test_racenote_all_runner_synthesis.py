#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from racenote_all_runner_synthesis import (  # noqa: E402
    AllRunnerSynthesisError,
    SYNTHESIS_CONTRACT_VERSION,
    SYNTHESIS_SCHEMA_VERSION,
    semantic_sha256,
    validate_all_runner_synthesis,
)


def _interpretation(
    *,
    trend_state: str = "SUPPORTIVE",
    small_sample_only: bool = False,
    review_state: str = "SUPPORTIVE",
    contradiction: str = "NONE",
    positive: list[str] | None = None,
    concern: list[str] | None = None,
) -> dict[str, object]:
    if positive is None:
        positive = ["DATA_TREND_SUPPORT", "RACEREVIEW_SUPPORT"]
    if concern is None:
        concern = []
    return {
        "interpretation_version": "PredictionInterpretation-v0.1",
        "data_trend": {
            "state": trend_state,
            "positive": [],
            "negative": [],
            "neutral": [],
            "unknown": [],
            "best_directional_sample_band": (
                "small" if small_sample_only else "moderate"
            ),
            "small_sample_only": small_sample_only,
            "population_contexts": [],
            "reading_rule": (
                "DIRECTION_PLUS_SAMPLE_SIZE_BEFORE_POPULATION_CONTEXT"
            ),
        },
        "race_structure": {
            "pace_pressure": "MEDIUM",
            "horse_historical_position": {
                "tendency": "FORWARD",
            },
            "running_style_trend_available": True,
            "reading_rule": (
                "RACE_STRUCTURE_IS_RELATIVE_CONTEXT_NOT_AUTOMATIC_DIRECTION"
            ),
            "policy": {},
        },
        "racereview": {
            "state": review_state,
            "hidden_strength_status": "NONE",
            "fragile_form_status": "NONE",
            "contradiction_status": contradiction,
            "repeatability_codes": [],
            "transferability": {
                "state": "UNKNOWN",
                "selected_source_run_count": 0,
                "exact_surface_distance_count": 0,
                "partial_exact_match_count": 0,
                "runs": [],
                "policy": {},
            },
            "reading_rule": (
                "CONTENT_FIRST_THEN_REPEATABILITY_THEN_TARGET_OVERLAP"
            ),
        },
        "ability_anchor": {
            "role": "AVAILABLE_ANCHOR",
            "may_create_upgrade_by_itself": False,
            "may_create_downgrade_by_itself": False,
            "profile": {
                "latest": 60.0,
                "peak": 62.0,
                "typical_median": 59.0,
                "minimum": 55.0,
                "mad": 2.0,
            },
        },
        "positive_case_components": positive,
        "concern_case_components": concern,
        "pairwise_reading_order": [
            "DATA_TREND",
            "RACEREVIEW",
            "ABILITY_ANCHOR",
        ],
        "policy": {
            "no_numeric_score": True,
            "no_positive_evidence_count_voting": True,
            "sample_size_changes_confidence_not_direction": True,
            "rr_repeatability_matters": True,
            "rr_target_overlap_is_transferability_context": True,
            "ability_is_floor_ceiling_anchor": True,
            "final_upgrade_or_downgrade_requires_pairwise": True,
        },
    }


def _general() -> dict[str, object]:
    return {
        "general_schema_version": "RaceNote-General-Evidence-0.1",
        "general_logic_version": "TrendFirst-RR-AbilityAnchor-v0.1",
        "target": {
            "date": "2026-09-26",
            "venue": "中山",
            "race_no": 11,
            "race_name": "テストS",
        },
        "priority_policy": {
            "relation": "DATA_TREND > RACEREVIEW >= ABILITY_ANCHOR",
            "decision_order": [
                "DATA_TREND",
                "RACEREVIEW",
                "ABILITY_ANCHOR",
            ],
            "numeric_weights": None,
            "rules": {},
        },
        "firewall": {
            "current_jrdb_consensus_visible": False,
            "current_market_visible": False,
            "training_edge_visible": False,
        },
        "race_data_context": {},
        "race_structure": {},
        "horses": [
            {
                "horse_no": 1,
                "horse_name": "A",
                "prediction_interpretation": _interpretation(
                    trend_state="MIXED",
                    small_sample_only=True,
                    review_state="MIXED",
                    contradiction="MIXED",
                    positive=[
                        "DATA_TREND_MIXED_SUPPORT",
                        "RACEREVIEW_MIXED_SUPPORT",
                    ],
                    concern=[
                        "DATA_TREND_MIXED_CONCERN",
                        "RACEREVIEW_MIXED_CONCERN",
                    ],
                ),
            },
            {
                "horse_no": 2,
                "horse_name": "B",
                "prediction_interpretation": _interpretation(),
            },
            {
                "horse_no": 3,
                "horse_name": "C",
                "prediction_interpretation": _interpretation(
                    review_state="FRAGILE_FORM",
                    positive=["DATA_TREND_SUPPORT"],
                    concern=["RACEREVIEW_CONCERN"],
                ),
            },
            {
                "horse_no": 4,
                "horse_name": "D",
                "prediction_interpretation": _interpretation(
                    trend_state="OPPOSED",
                    positive=["RACEREVIEW_SUPPORT"],
                    concern=["DATA_TREND_OPPOSITION"],
                ),
            },
        ],
        "next_stage": {
            "name": "PAIRWISE_COMPARISON",
            "required_read_order": [
                "DATA_TREND",
                "RACEREVIEW",
                "ABILITY_ANCHOR",
            ],
            "status": "CONTRACT_IMPLEMENTED",
            "contract_version": "TrendFirst-Pairwise-v0.1",
        },
    }


def _runner(
    horse_no: int,
    draft_rank: int,
    *,
    confidence: str,
    primary_lane: str,
    positive: list[str],
    concern: list[str],
) -> dict[str, object]:
    return {
        "horse_no": horse_no,
        "draft_rank": draft_rank,
        "confidence": confidence,
        "primary_lane": primary_lane,
        "positive_components": positive,
        "concern_components": concern,
        "ability_context_used": True,
        "draft_reason": "全馬の上位Evidenceを比較して暫定位置を決めた。",
        "main_uncertainty": "Pairwiseで直接比較して確定する必要がある。",
    }


def _payload(general: dict[str, object]) -> dict[str, object]:
    return {
        "synthesis_schema_version": SYNTHESIS_SCHEMA_VERSION,
        "synthesis_contract_version": SYNTHESIS_CONTRACT_VERSION,
        "general_evidence_sha256": semantic_sha256(general),
        "target": copy.deepcopy(general["target"]),
        "horses": [
            _runner(
                2,
                1,
                confidence="HIGH",
                primary_lane="DATA_TREND",
                positive=[
                    "DATA_TREND_SUPPORT",
                    "RACEREVIEW_SUPPORT",
                ],
                concern=[],
            ),
            _runner(
                1,
                2,
                confidence="LOW",
                primary_lane="MIXED",
                positive=[
                    "DATA_TREND_MIXED_SUPPORT",
                    "RACEREVIEW_MIXED_SUPPORT",
                ],
                concern=[
                    "DATA_TREND_MIXED_CONCERN",
                    "RACEREVIEW_MIXED_CONCERN",
                ],
            ),
            _runner(
                3,
                3,
                confidence="MEDIUM",
                primary_lane="DATA_TREND",
                positive=["DATA_TREND_SUPPORT"],
                concern=["RACEREVIEW_CONCERN"],
            ),
            _runner(
                4,
                4,
                confidence="MEDIUM",
                primary_lane="RACEREVIEW",
                positive=["RACEREVIEW_SUPPORT"],
                concern=["DATA_TREND_OPPOSITION"],
            ),
        ],
        "boundaries": [
            {
                "upper_horse_no": 2,
                "lower_horse_no": 1,
                "comparison_priority": "HIGH",
                "boundary_summary": "1番はmixedかつ小母数で重点比較。",
            },
            {
                "upper_horse_no": 1,
                "lower_horse_no": 3,
                "comparison_priority": "HIGH",
                "boundary_summary": "1番の不確実性が大きく重点比較。",
            },
            {
                "upper_horse_no": 3,
                "lower_horse_no": 4,
                "comparison_priority": "STANDARD",
                "boundary_summary": "通常の隣接比較。",
            },
        ],
        "draft_order_summary": (
            "データ傾向を先に全馬比較し、RaceReviewで補強・反証を確認。"
        ),
    }


class RaceNoteAllRunnerSynthesisTest(unittest.TestCase):
    def test_valid_full_field_synthesis_passes(self) -> None:
        general = _general()
        audit = validate_all_runner_synthesis(
            general,
            _payload(general),
        )

        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(audit["draft_order"], [2, 1, 3, 4])
        self.assertFalse(audit["policy"]["numeric_score_used"])
        self.assertFalse(
            audit["policy"]["ability_may_be_primary_basis"]
        )
        self.assertEqual(
            [
                (
                    item["upper_horse_no"],
                    item["lower_horse_no"],
                )
                for item in audit["high_priority_boundaries"]
            ],
            [(2, 1), (1, 3)],
        )
        self.assertEqual(
            audit["next_stage"]["name"],
            "PAIRWISE_COMPARISON",
        )

    def test_missing_runner_fails_closed(self) -> None:
        general = _general()
        payload = _payload(general)
        payload["horses"] = payload["horses"][:-1]

        with self.assertRaises(AllRunnerSynthesisError):
            validate_all_runner_synthesis(general, payload)

    def test_non_contiguous_draft_rank_fails_closed(self) -> None:
        general = _general()
        payload = _payload(general)
        payload["horses"][3]["draft_rank"] = 5

        with self.assertRaises(AllRunnerSynthesisError):
            validate_all_runner_synthesis(general, payload)

    def test_unknown_interpretation_component_fails_closed(self) -> None:
        general = _general()
        payload = _payload(general)
        payload["horses"][0]["positive_components"] = [
            "MADE_UP_SIGNAL"
        ]

        with self.assertRaises(AllRunnerSynthesisError):
            validate_all_runner_synthesis(general, payload)

    def test_ability_cannot_be_primary_lane(self) -> None:
        general = _general()
        payload = _payload(general)
        payload["horses"][0]["primary_lane"] = "ABILITY_ANCHOR"

        with self.assertRaises(AllRunnerSynthesisError):
            validate_all_runner_synthesis(general, payload)

    def test_mixed_requires_trend_and_review_components(self) -> None:
        general = _general()
        payload = _payload(general)
        payload["horses"][1]["positive_components"] = [
            "DATA_TREND_MIXED_SUPPORT"
        ]
        payload["horses"][1]["concern_components"] = [
            "DATA_TREND_MIXED_CONCERN"
        ]

        with self.assertRaises(AllRunnerSynthesisError):
            validate_all_runner_synthesis(general, payload)

    def test_high_priority_boundary_cannot_be_hidden(self) -> None:
        general = _general()
        payload = _payload(general)
        payload["boundaries"][0]["comparison_priority"] = "STANDARD"

        with self.assertRaises(AllRunnerSynthesisError):
            validate_all_runner_synthesis(general, payload)

    def test_general_hash_mismatch_fails_closed(self) -> None:
        general = _general()
        payload = _payload(general)
        payload["general_evidence_sha256"] = "0" * 64

        with self.assertRaises(AllRunnerSynthesisError):
            validate_all_runner_synthesis(general, payload)


if __name__ == "__main__":
    unittest.main()
