#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from racenote_edge_performance_adapter import (  # noqa: E402
    EdgePerformanceAdapterError,
    adapt_matcher_row,
)


def _match(
    edge_id: str,
    *,
    level: str = "CONFIRMED",
    signal: str = "POSITIVE",
    role: str = "PRIMARY",
) -> dict[str, object]:
    return {
        "edge_id": edge_id,
        "performance_evidence_level": level,
        "value_evidence_level": "CONFIRMED",
        "redundancy_group_id": "DISTANCE:1600",
        "presentation": {
            "performance": {
                "role": role,
                "conflict": False,
            },
            "value": {
                "role": "PRIMARY",
                "conflict": False,
            },
        },
        "evidence": {
            "family": "DISTANCE",
            "performance_signal": signal,
            "value_signal": "POSITIVE",
            "performance_q_value": 0.04,
            "value_q_value": 0.03,
        },
    }


class RaceNoteEdgePerformanceAdapterTest(unittest.TestCase):
    def test_projects_only_performance_channel(self) -> None:
        row = {
            "key": {
                "horse_no": 3,
                "race_horse_key": "06261103",
            },
            "edge_matches": [_match("E1")],
        }

        result = adapt_matcher_row(row)

        self.assertEqual(result["status"], "USED")
        self.assertEqual(
            result["value_channel_status"],
            "DROPPED_BEFORE_FORECAST",
        )
        self.assertFalse(
            result["consumer_recomputed_edge_conditions"]
        )
        match = result["matches"][0]
        self.assertEqual(
            match["performance_evidence_level"],
            "CONFIRMED",
        )
        self.assertEqual(match["signal"], "POSITIVE")
        self.assertNotIn("value_signal", match)
        self.assertNotIn("value_evidence_level", match)
        self.assertNotIn("value_q_value", match)

    def test_none_performance_channel_is_not_served(self) -> None:
        row = {
            "key": {
                "horse_no": 3,
                "race_horse_key": "06261103",
            },
            "edge_matches": [
                _match(
                    "E1",
                    level="NONE",
                )
            ],
        }

        result = adapt_matcher_row(row)
        self.assertEqual(result["status"], "NO_MATCH")
        self.assertEqual(result["matches"], [])

    def test_conflict_role_is_preserved(self) -> None:
        row = {
            "key": {
                "horse_no": 3,
                "race_horse_key": "06261103",
            },
            "edge_matches": [
                _match(
                    "E1",
                    level="SUGGESTIVE",
                    signal="NEGATIVE",
                    role="CONFLICT",
                )
            ],
        }

        result = adapt_matcher_row(row)
        match = result["matches"][0]
        self.assertEqual(
            match["performance_evidence_level"],
            "SUGGESTIVE",
        )
        self.assertEqual(
            match["presentation_role"],
            "CONFLICT",
        )

    def test_invalid_performance_level_fails_closed(self) -> None:
        row = {
            "key": {
                "horse_no": 3,
                "race_horse_key": "06261103",
            },
            "edge_matches": [
                _match(
                    "E1",
                    level="RESEARCH_ONLY",
                )
            ],
        }

        with self.assertRaises(EdgePerformanceAdapterError):
            adapt_matcher_row(row)


if __name__ == "__main__":
    unittest.main()
