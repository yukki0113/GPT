#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from racenote_scenario_robustness import (  # noqa: E402
    SCENARIO_CONTRACT_VERSION,
    SCENARIO_SCHEMA_VERSION,
    ScenarioRobustnessError,
    semantic_sha256,
    validate_scenario_robustness,
)


def _pairwise_audit() -> dict[str, object]:
    return {
        "audit_schema_version": "RaceNote-Pairwise-Audit-0.1",
        "status": "PASS",
        "pairwise_schema_version": "RaceNote-Pairwise-Comparison-0.1",
        "pairwise_contract_version": "TrendFirst-Pairwise-v0.1",
        "general_evidence_sha256": "a" * 64,
        "target": {
            "date": "2026-09-25",
            "venue": "中山",
            "race_no": 11,
            "race_name": "テストステークス",
        },
        "policy": {
            "priority_relation": (
                "DATA_TREND > RACEREVIEW >= ABILITY_ANCHOR"
            ),
            "numeric_score_used": False,
            "market_visible": False,
            "jrdb_current_consensus_visible": False,
            "training_edge_visible": False,
            "adjacent_pair_coverage_required": True,
            "top_challenger_direct_comparison_required": True,
            "reversal_condition_required": True,
            "lower_priority_override_reason_required": True,
        },
        "draft_order": [3, 1, 2, 4],
        "final_order": [1, 2, 3, 4],
        "order_changes": [],
        "required_pair_keys": [],
        "comparison_count": 5,
        "lower_priority_override_count": 0,
        "comparisons": [],
        "final_order_summary": "trend-first pairwise final.",
        "next_stage": {
            "name": "SCENARIO_ROBUSTNESS",
            "status": "READY",
        },
    }


def _scenario(
    scenario_id: str,
    order: list[int],
    *,
    changed: bool,
    reversal: list[str] | None = None,
) -> dict[str, object]:
    reversals: list[str] = []
    if reversal is not None:
        reversals = reversal
    return {
        "scenario_id": scenario_id,
        "pace": scenario_id,
        "assumption_summary": f"{scenario_id} pace assumption.",
        "order": order,
        "changed_from_pairwise": changed,
        "scenario_summary": f"{scenario_id} scenario comparison.",
        "key_reason_codes": [f"PACE_{scenario_id}"],
        "triggered_reversal_conditions": reversals,
    }


def _payload() -> dict[str, object]:
    pairwise = _pairwise_audit()
    return {
        "scenario_schema_version": SCENARIO_SCHEMA_VERSION,
        "scenario_contract_version": SCENARIO_CONTRACT_VERSION,
        "pairwise_audit_sha256": semantic_sha256(pairwise),
        "target": copy.deepcopy(pairwise["target"]),
        "scenarios": [
            _scenario(
                "SLOW",
                [1, 2, 3, 4],
                changed=False,
            ),
            _scenario(
                "MEDIUM",
                [1, 2, 3, 4],
                changed=False,
            ),
            _scenario(
                "FAST",
                [2, 1, 3, 4],
                changed=True,
                reversal=[
                    "ハイペースで1の先行優位が崩れる場合。",
                ],
            ),
        ],
        "conclusion": {
            "pairwise_axis_status": "CONDITIONAL",
            "main_risk_scenario_ids": ["FAST"],
            "summary": (
                "1はslow/mediumで首位、fastでは2が逆転する。"
            ),
        },
    }


class RaceNoteScenarioRobustnessTest(unittest.TestCase):
    def test_conditional_axis_is_derived_from_three_scenarios(self) -> None:
        audit = validate_scenario_robustness(
            _pairwise_audit(),
            _payload(),
        )

        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(audit["axis_horse_no"], 1)
        self.assertEqual(
            audit["axis_rank1_scenario_count"],
            2,
        )
        self.assertEqual(
            audit["axis_robustness"],
            "CONDITIONAL",
        )
        self.assertEqual(
            audit["risk_scenario_ids"],
            ["FAST"],
        )
        self.assertFalse(
            audit["pairwise_recheck_recommended"]
        )
        horse1 = next(
            item
            for item in audit["horse_sensitivity"]
            if item["horse_no"] == 1
        )
        self.assertEqual(
            horse1["scenario_ranks"],
            {
                "SLOW": 1,
                "MEDIUM": 1,
                "FAST": 2,
            },
        )
        self.assertEqual(horse1["rank_span"], 1)

    def test_axis_is_robust_only_when_first_in_all_scenarios(self) -> None:
        pairwise = _pairwise_audit()
        payload = _payload()
        payload["scenarios"][2] = _scenario(
            "FAST",
            [1, 2, 3, 4],
            changed=False,
        )
        payload["conclusion"] = {
            "pairwise_axis_status": "ROBUST",
            "main_risk_scenario_ids": [],
            "summary": "全paceで1が首位を維持。",
        }

        audit = validate_scenario_robustness(
            pairwise,
            payload,
        )
        self.assertEqual(audit["axis_robustness"], "ROBUST")
        self.assertEqual(
            audit["axis_rank1_scenario_count"],
            3,
        )

    def test_fragile_axis_recommends_pairwise_recheck(self) -> None:
        pairwise = _pairwise_audit()
        payload = _payload()
        payload["scenarios"] = [
            _scenario(
                "SLOW",
                [1, 2, 3, 4],
                changed=False,
            ),
            _scenario(
                "MEDIUM",
                [2, 1, 3, 4],
                changed=True,
                reversal=["中速でも2の差しが届く場合。"],
            ),
            _scenario(
                "FAST",
                [2, 3, 1, 4],
                changed=True,
                reversal=["高速化で1が消耗する場合。"],
            ),
        ]
        payload["conclusion"] = {
            "pairwise_axis_status": "FRAGILE",
            "main_risk_scenario_ids": ["MEDIUM", "FAST"],
            "summary": "1はslowのみ首位。",
        }

        audit = validate_scenario_robustness(
            pairwise,
            payload,
        )
        self.assertEqual(audit["axis_robustness"], "FRAGILE")
        self.assertTrue(
            audit["pairwise_recheck_recommended"]
        )

    def test_changed_order_requires_triggered_reversal_condition(self) -> None:
        payload = _payload()
        payload["scenarios"][2] = _scenario(
            "FAST",
            [2, 1, 3, 4],
            changed=True,
            reversal=[],
        )

        with self.assertRaises(ScenarioRobustnessError):
            validate_scenario_robustness(
                _pairwise_audit(),
                payload,
            )

    def test_declared_axis_status_must_match_outcomes(self) -> None:
        payload = _payload()
        payload["conclusion"]["pairwise_axis_status"] = "ROBUST"

        with self.assertRaises(ScenarioRobustnessError):
            validate_scenario_robustness(
                _pairwise_audit(),
                payload,
            )

    def test_all_three_scenarios_are_required(self) -> None:
        payload = _payload()
        payload["scenarios"] = payload["scenarios"][:2]

        with self.assertRaises(ScenarioRobustnessError):
            validate_scenario_robustness(
                _pairwise_audit(),
                payload,
            )

    def test_pairwise_hash_mismatch_fails_closed(self) -> None:
        payload = _payload()
        payload["pairwise_audit_sha256"] = "0" * 64

        with self.assertRaises(ScenarioRobustnessError):
            validate_scenario_robustness(
                _pairwise_audit(),
                payload,
            )

    def test_scenario_cannot_open_market_via_pairwise_policy(self) -> None:
        pairwise = _pairwise_audit()
        pairwise["policy"]["market_visible"] = True
        payload = _payload()
        payload["pairwise_audit_sha256"] = semantic_sha256(
            pairwise
        )

        with self.assertRaises(ScenarioRobustnessError):
            validate_scenario_robustness(
                pairwise,
                payload,
            )


if __name__ == "__main__":
    unittest.main()
