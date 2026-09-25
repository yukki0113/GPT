#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from racenote_forecast_gen0_3 import (  # noqa: E402
    EVIDENCE_POLICY_VERSION,
    FORECAST_VERSION,
    ForecastGen03Error,
    audit_frozen_forecast,
    freeze_forecast,
    semantic_sha256,
    validate_forecast,
)


def _general_horse(
    horse_no: int,
    name: str,
) -> dict[str, object]:
    return {
        "horse_no": horse_no,
        "horse_name": name,
        "horse_id": f"H{horse_no}",
        "evidence_lanes": {
            "data_trend": {
                "horse_history": {
                    "observations": [
                        {
                            "code": "SAME_DISTANCE",
                            "direction": "POSITIVE",
                            "sample_size_band": "small",
                            "redundancy_group_id": "DISTANCE",
                        }
                    ]
                },
                "population_context": {
                    "frame": {
                        "code": "FRAME_TREND",
                        "status": "AVAILABLE",
                    },
                    "sire": {
                        "code": "SIRE_TREND",
                        "status": "AVAILABLE",
                    },
                    "jockey": {
                        "code": "JOCKEY_TREND",
                        "status": "AVAILABLE",
                    },
                },
            },
            "racereview": {
                "primary_positive": [
                    {
                        "code": "RESULT_UNDERRATES_TIME",
                    }
                ],
                "supporting_positive": [],
                "concerns": [],
                "mixed_context": [],
                "profile": {
                    "hidden_strength": {
                        "reason_codes": [
                            "RESULT_UNDERRATES_TIME"
                        ]
                    },
                    "fragile_form": {
                        "reason_codes": []
                    },
                },
                "uncertainties": [],
            },
            "ability_anchor": {
                "profile": {
                    "latest": 60.0,
                    "peak": 62.0,
                    "typical_median": 59.0,
                    "minimum": 55.0,
                    "mad": 2.0,
                }
            },
        },
        "prediction_interpretation": {
            "race_structure": {
                "pace_pressure": "MEDIUM",
                "horse_historical_position": {
                    "tendency": "FORWARD",
                },
            }
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
        "race_structure": {
            "structure_version": "IndependentRaceStructure-v0.1",
            "status": "AVAILABLE",
            "pace_pressure": "MEDIUM",
            "front_or_forward_tendency_count": 2,
            "known_position_profile_count": 3,
            "runner_count": 3,
            "horses": [],
            "policy": {},
        },
        "horses": [
            _general_horse(1, "A"),
            _general_horse(2, "B"),
            _general_horse(3, "C"),
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


def _pairwise(general: dict[str, object]) -> dict[str, object]:
    return {
        "audit_schema_version": "RaceNote-Pairwise-Audit-0.1",
        "status": "PASS",
        "general_evidence_sha256": semantic_sha256(general),
        "target": copy.deepcopy(general["target"]),
        "policy": {
            "numeric_score_used": False,
            "market_visible": False,
            "jrdb_current_consensus_visible": False,
            "training_edge_visible": False,
        },
        "final_order": [1, 2, 3],
        "comparisons": [
            {
                "horse_a": 1,
                "horse_b": 2,
                "preferred_horse_no": 1,
            },
            {
                "horse_a": 2,
                "horse_b": 3,
                "preferred_horse_no": 2,
            },
            {
                "horse_a": 1,
                "horse_b": 3,
                "preferred_horse_no": 1,
            },
        ],
    }


def _scenario(
    pairwise: dict[str, object],
) -> dict[str, object]:
    return {
        "audit_schema_version": "RaceNote-Scenario-Robustness-Audit-0.1",
        "status": "PASS",
        "pairwise_audit_sha256": semantic_sha256(pairwise),
        "target": copy.deepcopy(pairwise["target"]),
        "axis_robustness": "ROBUST",
        "pairwise_recheck_recommended": False,
        "horse_sensitivity": [
            {
                "horse_no": 1,
                "pairwise_rank": 1,
                "scenario_ranks": {
                    "SLOW": 1,
                    "MEDIUM": 1,
                    "FAST": 1,
                },
            },
            {
                "horse_no": 2,
                "pairwise_rank": 2,
                "scenario_ranks": {
                    "SLOW": 2,
                    "MEDIUM": 2,
                    "FAST": 2,
                },
            },
            {
                "horse_no": 3,
                "pairwise_rank": 3,
                "scenario_ranks": {
                    "SLOW": 3,
                    "MEDIUM": 3,
                    "FAST": 3,
                },
            },
        ],
        "scenarios": [
            {
                "scenario_id": "SLOW",
                "order": [1, 2, 3],
                "key_reason_codes": ["PACE_SLOW"],
            },
            {
                "scenario_id": "MEDIUM",
                "order": [1, 2, 3],
                "key_reason_codes": ["PACE_MEDIUM"],
            },
            {
                "scenario_id": "FAST",
                "order": [1, 2, 3],
                "key_reason_codes": ["PACE_FAST"],
            },
        ],
    }


def _edge_none() -> dict[str, object]:
    return {
        "status": "NO_MATCH",
        "profile": "STANDARD",
        "matches": [],
        "adjustment_direction": "NONE",
        "adjustment_reason": "",
    }


def _edge_positive(edge_id: str) -> dict[str, object]:
    return {
        "status": "USED",
        "profile": "STANDARD",
        "matches": [
            {
                "edge_id": edge_id,
                "family": "DISTANCE",
                "performance_evidence_level": "CONFIRMED",
                "signal": "POSITIVE",
                "presentation_role": "PRIMARY",
                "conflict": False,
                "redundancy_group_id": "DISTANCE:1600",
            }
        ],
        "adjustment_direction": "POSITIVE",
        "adjustment_reason": "独立予想後にperformance evidenceを補助採用。",
    }


def _horse(
    horse_no: int,
    name: str,
    rank: int,
    p_win: float,
    p_top2: float,
    mark: str,
) -> dict[str, object]:
    return {
        "horse_no": horse_no,
        "horse_name": name,
        "base_rank": rank,
        "final_rank": rank,
        "mark": mark,
        "p_win_base": p_win,
        "p_top2_base": p_top2,
        "p_top3_base": 1.0,
        "p_win_final": p_win,
        "p_top2_final": p_top2,
        "p_top3_final": 1.0,
        "primary_reason": "データ・傾向を最優先に比較。",
        "secondary_support": "RaceReviewで内容を補強。",
        "main_concern": "展開変化には注意。",
        "why_above_next": "条件Evidenceで一歩上。",
        "scenario_adjustment_reason": "",
        "edge_performance": _edge_none(),
        "decision_trace": {
            "trace_version": "RaceNote-Decision-Trace-0.1",
            "primary": {
                "lane": "DATA_TREND",
                "evidence_codes": ["SAME_DISTANCE"],
            },
            "secondary": {
                "lane": "RACEREVIEW",
                "evidence_codes": [
                    "RESULT_UNDERRATES_TIME"
                ],
            },
            "concern": {
                "lane": "SCENARIO",
                "evidence_codes": ["SCENARIO_FAST"],
            },
            "pairwise_support_horse_nos": (
                [2] if horse_no == 1
                else [3] if horse_no == 2
                else []
            ),
            "scenario_risk_ids": [],
            "edge_ids": [],
            "comment_evidence_codes": [
                "SAME_DISTANCE",
                "RESULT_UNDERRATES_TIME",
                "SCENARIO_FAST",
            ],
        },
    }


def _payload(
    general: dict[str, object],
    pairwise: dict[str, object],
    scenario: dict[str, object],
) -> dict[str, object]:
    return {
        "forecast_version": FORECAST_VERSION,
        "evidence_policy_version": EVIDENCE_POLICY_VERSION,
        "generation_id": "Gen0-G001",
        "forecast_id": "20260926_中山_11_Gen0-G001",
        "target": copy.deepcopy(general["target"]),
        "source_chain": {
            "general_evidence_sha256": semantic_sha256(general),
            "pairwise_audit_sha256": semantic_sha256(pairwise),
            "scenario_audit_sha256": semantic_sha256(scenario),
        },
        "base_order": [1, 2, 3],
        "final_order": [1, 2, 3],
        "horses": [
            _horse(1, "A", 1, 0.50, 0.80, "◎"),
            _horse(2, "B", 2, 0.30, 0.70, "○"),
            _horse(3, "C", 3, 0.20, 0.50, "▲"),
        ],
        "forecast_created_at": "2026-09-26T09:00:00+09:00",
    }


class RaceNoteForecastGen03Test(unittest.TestCase):
    def test_valid_trend_first_forecast_passes(self) -> None:
        general = _general()
        pairwise = _pairwise(general)
        scenario = _scenario(pairwise)
        payload = _payload(general, pairwise, scenario)

        result = validate_forecast(
            general,
            pairwise,
            scenario,
            payload,
        )

        self.assertEqual(result["forecast_version"], FORECAST_VERSION)
        self.assertEqual(result["pairwise_order"], [1, 2, 3])
        self.assertEqual(result["scenario_axis_robustness"], "ROBUST")
        self.assertFalse(result["firewall"]["edge_value_visible"])
        self.assertEqual(
            result["horses"][0]["decision_trace"][
                "short_comment_status"
            ],
            "SOURCE_READY",
        )
        self.assertEqual(
            result["horses"][0]["decision_trace"]["primary"][
                "evidence_codes"
            ],
            ["SAME_DISTANCE"],
        )
        self.assertEqual(
            result["post_freeze_open_order"],
            [
                "JRDB_CONSENSUS",
                "MARKET",
                "EDGE_VALUE",
                "RL_VALUE",
                "BET_PLAN",
            ],
        )

    def test_fragile_scenario_must_be_rechecked_before_forecast(self) -> None:
        general = _general()
        pairwise = _pairwise(general)
        scenario = _scenario(pairwise)
        scenario["axis_robustness"] = "FRAGILE"
        scenario["pairwise_recheck_recommended"] = True
        payload = _payload(general, pairwise, scenario)
        payload["source_chain"]["scenario_audit_sha256"] = semantic_sha256(
            scenario
        )

        with self.assertRaises(ForecastGen03Error):
            validate_forecast(
                general,
                pairwise,
                scenario,
                payload,
            )

    def test_edge_value_field_is_forbidden(self) -> None:
        general = _general()
        pairwise = _pairwise(general)
        scenario = _scenario(pairwise)
        payload = _payload(general, pairwise, scenario)
        payload["horses"][0]["edge_performance"] = _edge_positive("E1")
        payload["horses"][0]["edge_performance"]["matches"][0][
            "value_signal"
        ] = "POSITIVE"

        with self.assertRaises(ForecastGen03Error):
            validate_forecast(
                general,
                pairwise,
                scenario,
                payload,
            )

    def test_final_rank_change_requires_edge_performance(self) -> None:
        general = _general()
        pairwise = _pairwise(general)
        scenario = _scenario(pairwise)
        payload = _payload(general, pairwise, scenario)
        payload["final_order"] = [2, 1, 3]
        payload["horses"][0]["final_rank"] = 2
        payload["horses"][0]["mark"] = "○"
        payload["horses"][0]["p_win_final"] = 0.35
        payload["horses"][1]["final_rank"] = 1
        payload["horses"][1]["mark"] = "◎"
        payload["horses"][1]["p_win_final"] = 0.45
        payload["horses"][2]["p_win_final"] = 0.20

        with self.assertRaises(ForecastGen03Error):
            validate_forecast(
                general,
                pairwise,
                scenario,
                payload,
            )

    def test_unknown_decision_evidence_code_fails_closed(self) -> None:
        general = _general()
        pairwise = _pairwise(general)
        scenario = _scenario(pairwise)
        payload = _payload(general, pairwise, scenario)
        payload["horses"][0]["decision_trace"]["primary"][
            "evidence_codes"
        ] = ["NOT_REAL_EVIDENCE"]

        with self.assertRaises(ForecastGen03Error):
            validate_forecast(
                general,
                pairwise,
                scenario,
                payload,
            )

    def test_axis_trace_requires_direct_pairwise_support_vs_runner_up(self) -> None:
        general = _general()
        pairwise = _pairwise(general)
        scenario = _scenario(pairwise)
        payload = _payload(general, pairwise, scenario)
        payload["horses"][0]["decision_trace"][
            "pairwise_support_horse_nos"
        ] = [3]

        with self.assertRaises(ForecastGen03Error):
            validate_forecast(
                general,
                pairwise,
                scenario,
                payload,
            )

    def test_scenario_risk_trace_must_match_actual_rank_drop(self) -> None:
        general = _general()
        pairwise = _pairwise(general)
        scenario = _scenario(pairwise)
        scenario["horse_sensitivity"][0]["scenario_ranks"][
            "FAST"
        ] = 2
        scenario["scenarios"][2]["order"] = [2, 1, 3]
        payload = _payload(general, pairwise, scenario)
        payload["source_chain"]["scenario_audit_sha256"] = semantic_sha256(
            scenario
        )

        with self.assertRaises(ForecastGen03Error):
            validate_forecast(
                general,
                pairwise,
                scenario,
                payload,
            )

    def test_comment_evidence_must_be_subset_of_decision_trace(self) -> None:
        general = _general()
        pairwise = _pairwise(general)
        scenario = _scenario(pairwise)
        payload = _payload(general, pairwise, scenario)
        payload["horses"][0]["decision_trace"][
            "comment_evidence_codes"
        ].append("ABILITY_PEAK")

        with self.assertRaises(ForecastGen03Error):
            validate_forecast(
                general,
                pairwise,
                scenario,
                payload,
            )

    def test_edge_performance_can_justify_final_rank_change(self) -> None:
        general = _general()
        pairwise = _pairwise(general)
        scenario = _scenario(pairwise)
        payload = _payload(general, pairwise, scenario)
        payload["final_order"] = [2, 1, 3]
        payload["horses"][0]["final_rank"] = 2
        payload["horses"][0]["mark"] = "○"
        payload["horses"][0]["p_win_final"] = 0.35
        payload["horses"][0]["edge_performance"] = _edge_positive("E-A")
        payload["horses"][0]["decision_trace"]["edge_ids"] = ["E-A"]
        payload["horses"][1]["final_rank"] = 1
        payload["horses"][1]["mark"] = "◎"
        payload["horses"][1]["p_win_final"] = 0.45
        payload["horses"][1]["edge_performance"] = _edge_positive("E-B")
        payload["horses"][1]["decision_trace"]["edge_ids"] = ["E-B"]
        payload["horses"][2]["p_win_final"] = 0.20

        result = validate_forecast(
            general,
            pairwise,
            scenario,
            payload,
        )
        self.assertEqual(result["final_order"], [2, 1, 3])

    def test_used_edge_requires_edge_id_in_decision_trace(self) -> None:
        general = _general()
        pairwise = _pairwise(general)
        scenario = _scenario(pairwise)
        payload = _payload(general, pairwise, scenario)
        payload["horses"][0]["edge_performance"] = _edge_positive("E1")

        with self.assertRaises(ForecastGen03Error):
            validate_forecast(
                general,
                pairwise,
                scenario,
                payload,
            )

    def test_pairwise_rank_change_to_base_requires_scenario_reason(self) -> None:
        general = _general()
        pairwise = _pairwise(general)
        scenario = _scenario(pairwise)
        payload = _payload(general, pairwise, scenario)
        payload["base_order"] = [2, 1, 3]
        payload["final_order"] = [2, 1, 3]
        payload["horses"][0]["base_rank"] = 2
        payload["horses"][0]["final_rank"] = 2
        payload["horses"][0]["mark"] = "○"
        payload["horses"][1]["base_rank"] = 1
        payload["horses"][1]["final_rank"] = 1
        payload["horses"][1]["mark"] = "◎"

        with self.assertRaises(ForecastGen03Error):
            validate_forecast(
                general,
                pairwise,
                scenario,
                payload,
            )

    def test_freeze_is_hash_auditable(self) -> None:
        general = _general()
        pairwise = _pairwise(general)
        scenario = _scenario(pairwise)
        result = validate_forecast(
            general,
            pairwise,
            scenario,
            _payload(general, pairwise, scenario),
        )
        frozen = freeze_forecast(
            result,
            "2026-09-26T09:01:00+09:00",
        )
        audit = audit_frozen_forecast(frozen)

        self.assertEqual(frozen["freeze_status"], "FROZEN")
        self.assertEqual(audit["audit_status"], "PASS")
        self.assertTrue(audit["post_freeze_layers_may_open"])

        broken = copy.deepcopy(frozen)
        broken["horses"][0]["primary_reason"] = "改ざん"
        broken_audit = audit_frozen_forecast(broken)
        self.assertEqual(broken_audit["audit_status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
