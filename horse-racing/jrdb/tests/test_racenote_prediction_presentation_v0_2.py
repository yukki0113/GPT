#!/usr/bin/env python3
"""Focused tests for Edge-aware RaceNote presentation evidence v0.2."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import racenote_prediction_presentation_v0_2 as target


class PresentationV02Test(unittest.TestCase):
    """Validate that presentation reveals, but never changes, frozen axis decisions."""

    def test_axis_change_is_exposed_for_axis_and_displaced_base(self) -> None:
        base_payload = {
            "version": "racenote-presentation-evidence-0.1",
            "result_data_used": False,
            "race_comment_brief": {"rendering_contract": {}},
            "horse_comment_briefs": [
                {"mark": "◎", "horse_no": 9, "horse_name": "A"},
                {"mark": "○", "horse_no": 2, "horse_name": "B"},
                {"mark": "▲", "horse_no": 6, "horse_name": "C"},
            ],
        }
        prediction = {
            "v0_2_control": {"axis_horse_no": 2},
            "v1_1_P_candidate": {
                "axis_horse_no": 9,
                "axis_changed": True,
                "axis_good_guard": 0.04,
                "base_axis_polarity": "NEGATIVE",
                "selected_axis_polarity": "POSITIVE",
            },
            "edge_diagnostics": [
                {
                    "horse_no": 2,
                    "performance_edge_polarity": "NEGATIVE",
                    "family_vote_sum": -1,
                    "performance_family_votes": {"COURSE": -2, "PEDIGREE": 1},
                    "axis_eligible": True,
                    "good_gap_from_base_axis": 0.0,
                    "active_unexpired_match_count": 4,
                },
                {
                    "horse_no": 9,
                    "performance_edge_polarity": "POSITIVE",
                    "family_vote_sum": 3,
                    "performance_family_votes": {"COURSE": 2, "TRANSITION": 1},
                    "axis_eligible": True,
                    "good_gap_from_base_axis": 0.034,
                    "active_unexpired_match_count": 2,
                },
            ],
        }
        with patch.object(target.base, "build_presentation_brief", return_value=base_payload):
            result = target.build_presentation_brief({}, prediction)

        self.assertEqual(result["version"], target.VERSION)
        self.assertFalse(result["result_data_used"])
        self.assertEqual(
            result["horse_comment_briefs"][0]["edge_context"]["mark_decision_role"],
            "edge_promoted_to_axis",
        )
        self.assertEqual(
            result["horse_comment_briefs"][1]["edge_context"]["mark_decision_role"],
            "base_axis_displaced_by_edge_comparison",
        )
        self.assertEqual(
            result["race_comment_brief"]["axis_decision"]["selected_axis_horse_no"],
            9,
        )

    def test_inconsistent_axis_changed_fails_closed(self) -> None:
        prediction = {
            "v0_2_control": {"axis_horse_no": 2},
            "v1_1_P_candidate": {"axis_horse_no": 9, "axis_changed": False},
        }
        with self.assertRaisesRegex(ValueError, "axis_changed"):
            target._axis_context(prediction)


if __name__ == "__main__":
    unittest.main()
