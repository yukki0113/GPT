#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from racenote_pairwise_comparison import (  # noqa: E402
    PAIRWISE_CONTRACT_VERSION,
    PAIRWISE_SCHEMA_VERSION,
    PairwiseComparisonError,
    build_comparison_request,
    required_pair_keys,
    semantic_sha256,
    validate_pairwise_comparison,
)


def _general_evidence() -> dict[str, object]:
    horses: list[dict[str, object]] = []
    for horse_no, name, peak in (
        (1, "トレンド型", 60.0),
        (2, "RR型", 61.0),
        (3, "能力型", 65.0),
        (4, "比較馬", 58.0),
    ):
        horses.append(
            {
                "horse_no": horse_no,
                "horse_name": name,
                "horse_id": f"H{horse_no}",
                "current_facts": {},
                "evidence_lanes": {
                    "data_trend": {
                        "priority_rank": 1,
                        "priority_relation": "HIGHEST",
                        "horse_history": {
                            "status": "AVAILABLE",
                            "source": "JRDB Analysis Lite",
                            "observations": [],
                        },
                        "population_context": {},
                        "policy": {},
                    },
                    "racereview": {
                        "priority_rank": 2,
                        "priority_relation": "SECOND",
                        "card_scope": "RACEREVIEW_HISTORY_V0_1",
                        "source_run_contexts": [],
                        "primary_positive": [],
                        "supporting_positive": [],
                        "concerns": [],
                        "mixed_context": [],
                        "profile": {},
                        "uncertainties": [],
                        "comment_evidence": {},
                    },
                    "ability_anchor": {
                        "priority_rank": 3,
                        "priority_relation": "ANCHOR_ONLY",
                        "status": "AVAILABLE",
                        "observed_count": 2,
                        "observations": [],
                        "profile": {
                            "latest": peak,
                            "peak": peak,
                            "typical_median": peak,
                            "minimum": peak,
                            "mad": 0.0,
                        },
                        "policy": {
                            "may_auto_rank": False,
                        },
                    },
                },
                "prediction_interpretation": {
                    "interpretation_version": "PredictionInterpretation-v0.1",
                    "data_trend": {
                        "state": "SUPPORTIVE",
                        "positive": [],
                        "negative": [],
                        "neutral": [],
                        "unknown": [],
                        "best_directional_sample_band": "small",
                        "small_sample_only": True,
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
                        "policy": {
                            "no_automatic_style_mapping_v0_1": True,
                        },
                    },
                    "racereview": {
                        "state": "SUPPORTIVE",
                        "hidden_strength_status": "NONE",
                        "fragile_form_status": "NONE",
                        "contradiction_status": "NONE",
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
                            "latest": peak,
                            "peak": peak,
                            "typical_median": peak,
                            "minimum": peak,
                            "mad": 0.0,
                        },
                    },
                    "positive_case_components": [
                        "DATA_TREND_SUPPORT"
                    ],
                    "concern_case_components": [],
                    "pairwise_reading_order": [
                        "DATA_TREND",
                        "RACEREVIEW",
                        "ABILITY_ANCHOR",
                    ],
                    "policy": {
                        "no_numeric_score": True,
                    },
                },
                "comparison_status": "NOT_YET_PAIRWISE_COMPARED",
            }
        )

    return {
        "general_schema_version": "RaceNote-General-Evidence-0.1",
        "general_logic_version": "TrendFirst-RR-AbilityAnchor-v0.1",
        "target": {
            "date": "2026-09-25",
            "venue": "中山",
            "race_no": 11,
            "race_name": "テストステークス",
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
        "race_structure": {
            "structure_version": "IndependentRaceStructure-v0.1",
            "status": "AVAILABLE",
            "pace_pressure": "MEDIUM",
            "front_or_forward_tendency_count": 2,
            "known_position_profile_count": 4,
            "runner_count": 4,
            "horses": [],
            "policy": {},
        },
        "horses": horses,
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


def _lane(
    relation: str,
    summary: str,
    code: str,
) -> dict[str, object]:
    return {
        "relation": relation,
        "summary": summary,
        "evidence_codes": [code],
        "source_refs": [],
    }


def _comparison(
    horse_a: int,
    horse_b: int,
    *,
    preference: str,
    data_relation: str,
    rr_relation: str,
    ability_relation: str,
    decisive_lane: str,
    override: bool = False,
    override_reason: str = "",
) -> dict[str, object]:
    return {
        "horse_a": horse_a,
        "horse_b": horse_b,
        "lane_judgments": {
            "DATA_TREND": _lane(
                data_relation,
                "条件・傾向の比較要約",
                "TREND",
            ),
            "RACEREVIEW": _lane(
                rr_relation,
                "過去走内容の比較要約",
                "RR",
            ),
            "ABILITY_ANCHOR": _lane(
                ability_relation,
                "単純能力anchorの比較要約",
                "ABILITY",
            ),
        },
        "preference": preference,
        "confidence": "MEDIUM",
        "decisive_lane": decisive_lane,
        "lower_priority_override": override,
        "override_reason": override_reason,
        "comparison_summary": "優先Evidenceを横比較した結果。",
        "reversal_conditions": [
            "想定した条件優位が成立しない場合は逆転余地。",
        ],
    }


def _valid_payload() -> dict[str, object]:
    general = _general_evidence()
    comparisons = [
        _comparison(
            1,
            2,
            preference="A",
            data_relation="A",
            rr_relation="B",
            ability_relation="B",
            decisive_lane="DATA_TREND",
        ),
        _comparison(
            2,
            3,
            preference="A",
            data_relation="A",
            rr_relation="A",
            ability_relation="B",
            decisive_lane="RACEREVIEW",
        ),
        _comparison(
            3,
            4,
            preference="A",
            data_relation="A",
            rr_relation="EVEN",
            ability_relation="A",
            decisive_lane="DATA_TREND",
        ),
        _comparison(
            1,
            3,
            preference="A",
            data_relation="A",
            rr_relation="A",
            ability_relation="B",
            decisive_lane="DATA_TREND",
        ),
        _comparison(
            1,
            4,
            preference="A",
            data_relation="A",
            rr_relation="A",
            ability_relation="A",
            decisive_lane="DATA_TREND",
        ),
    ]

    return {
        "pairwise_schema_version": PAIRWISE_SCHEMA_VERSION,
        "pairwise_contract_version": PAIRWISE_CONTRACT_VERSION,
        "general_evidence_sha256": semantic_sha256(general),
        "target": copy.deepcopy(general["target"]),
        "draft_order": [3, 1, 2, 4],
        "comparisons": comparisons,
        "final_order": [1, 2, 3, 4],
        "final_order_summary": (
            "傾向を先に読み、RRで補強し、能力はanchorとして最終順を確定。"
        ),
    }


class RaceNotePairwiseComparisonTest(unittest.TestCase):
    def test_required_pairs_cover_adjacent_and_top_challengers(self) -> None:
        self.assertEqual(
            required_pair_keys([1, 2, 3, 4]),
            {
                (1, 2),
                (2, 3),
                (3, 4),
                (1, 3),
                (1, 4),
            },
        )

    def test_valid_trend_first_pairwise_contract_passes(self) -> None:
        general = _general_evidence()
        payload = _valid_payload()

        audit = validate_pairwise_comparison(
            general,
            payload,
        )

        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(audit["final_order"], [1, 2, 3, 4])
        self.assertEqual(audit["comparison_count"], 5)
        self.assertEqual(
            audit["lower_priority_override_count"],
            0,
        )
        self.assertEqual(
            audit["next_stage"]["name"],
            "SCENARIO_ROBUSTNESS",
        )
        movements = {
            item["horse_no"]: item["movement"]
            for item in audit["order_changes"]
        }
        self.assertEqual(movements[1], 1)
        self.assertEqual(movements[3], -2)

    def test_ability_override_requires_explicit_reason(self) -> None:
        general = _general_evidence()
        payload = _valid_payload()
        payload["comparisons"][0] = _comparison(
            1,
            2,
            preference="A",
            data_relation="B",
            rr_relation="B",
            ability_relation="A",
            decisive_lane="ABILITY_ANCHOR",
            override=True,
            override_reason="上位Evidenceは小母数かつ相互矛盾が大きい。",
        )

        audit = validate_pairwise_comparison(
            general,
            payload,
        )
        self.assertEqual(
            audit["lower_priority_override_count"],
            1,
        )
        first = audit["comparisons"][0]
        self.assertEqual(
            first["contrary_higher_priority_lanes"],
            ["DATA_TREND", "RACEREVIEW"],
        )

    def test_ability_override_without_reason_fails_closed(self) -> None:
        general = _general_evidence()
        payload = _valid_payload()
        payload["comparisons"][0] = _comparison(
            1,
            2,
            preference="A",
            data_relation="B",
            rr_relation="B",
            ability_relation="A",
            decisive_lane="ABILITY_ANCHOR",
            override=True,
            override_reason="",
        )

        with self.assertRaises(PairwiseComparisonError):
            validate_pairwise_comparison(
                general,
                payload,
            )

    def test_mixed_decision_cannot_bypass_data_conflict(self) -> None:
        general = _general_evidence()
        payload = _valid_payload()
        payload["comparisons"][0] = _comparison(
            1,
            2,
            preference="A",
            data_relation="B",
            rr_relation="A",
            ability_relation="A",
            decisive_lane="MIXED",
            override=False,
        )

        with self.assertRaises(PairwiseComparisonError):
            validate_pairwise_comparison(
                general,
                payload,
            )

    def test_missing_required_pair_fails_closed(self) -> None:
        general = _general_evidence()
        payload = _valid_payload()
        payload["comparisons"] = payload["comparisons"][:-1]

        with self.assertRaises(PairwiseComparisonError):
            validate_pairwise_comparison(
                general,
                payload,
            )

    def test_final_order_must_match_required_pair_preferences(self) -> None:
        general = _general_evidence()
        payload = _valid_payload()
        payload["comparisons"][0]["preference"] = "B"

        with self.assertRaises(PairwiseComparisonError):
            validate_pairwise_comparison(
                general,
                payload,
            )

    def test_general_evidence_hash_mismatch_fails_closed(self) -> None:
        general = _general_evidence()
        payload = _valid_payload()
        payload["general_evidence_sha256"] = "0" * 64

        with self.assertRaises(PairwiseComparisonError):
            validate_pairwise_comparison(
                general,
                payload,
            )

    def test_pairwise_requires_prediction_interpretation(self) -> None:
        general = _general_evidence()
        del general["horses"][0]["prediction_interpretation"]

        with self.assertRaises(PairwiseComparisonError):
            build_comparison_request(
                general,
                [1, 2, 3, 4],
            )

    def test_pairwise_rejects_ability_only_upgrade_policy(self) -> None:
        general = _general_evidence()
        general["horses"][0]["prediction_interpretation"][
            "ability_anchor"
        ]["may_create_upgrade_by_itself"] = True

        with self.assertRaises(PairwiseComparisonError):
            build_comparison_request(
                general,
                [1, 2, 3, 4],
            )

    def test_request_builder_does_not_choose_winners(self) -> None:
        general = _general_evidence()
        request = build_comparison_request(
            general,
            [3, 1, 2, 4],
        )

        self.assertTrue(
            request["instructions"]["do_not_score"]
        )
        self.assertTrue(
            request["instructions"]["do_not_use_market"]
        )
        self.assertTrue(
            request["instructions"][
                "use_prediction_interpretation_first"
            ]
        )
        self.assertTrue(
            request["instructions"][
                "verify_interpretation_against_evidence_lanes"
            ]
        )
        for pair in request["required_pairs_for_draft"]:
            self.assertEqual(
                pair["horse_a_interpretation"][
                    "interpretation_version"
                ],
                "PredictionInterpretation-v0.1",
            )
            self.assertEqual(
                pair["horse_b_interpretation"][
                    "interpretation_version"
                ],
                "PredictionInterpretation-v0.1",
            )
            author_fields = pair["author_fields"]
            self.assertIsNone(author_fields["preference"])
            self.assertIsNone(author_fields["decisive_lane"])


if __name__ == "__main__":
    unittest.main()
