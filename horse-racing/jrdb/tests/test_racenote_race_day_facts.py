#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from racenote_race_day_facts import (  # noqa: E402
    RaceDayFactsError,
    attach_race_day_facts,
    validate_race_day_facts,
)


def _independent() -> dict[str, object]:
    return {
        "view_kind": "INDEPENDENT",
        "race": {
            "date": "2026-09-20",
            "venue": "中山",
            "race_no": 11,
            "post_time": "15:45",
            "race_name": "オールカマー",
        },
        "policy": {
            "current_jrdb_consensus_visible": False,
            "current_market_visible": False,
            "training_edge_visible": False,
        },
    }


class RaceNoteRaceDayFactsTest(unittest.TestCase):
    def test_valid_independent_facts_are_attached(self) -> None:
        facts = {
            "source_kind": "JRA_OFFICIAL_PRE_RACE",
            "as_of": "2026-09-20T14:30:00+09:00",
            "weather": "雨",
            "track_condition": "重",
            "result_independent": True,
        }

        result = attach_race_day_facts(
            _independent(),
            facts,
        )
        attached = result["race"]["race_day_facts"]

        self.assertEqual(
            attached["source_kind"],
            "JRA_OFFICIAL_PRE_RACE",
        )
        self.assertEqual(attached["weather"], "雨")
        self.assertEqual(attached["track_condition"], "重")
        self.assertTrue(attached["result_independent"])

    def test_result_dependent_facts_fail_closed(self) -> None:
        facts = {
            "source_kind": "RESULT_DERIVED",
            "as_of": "2026-09-20T16:00:00+09:00",
            "weather": "雨",
            "track_condition": "重",
            "result_independent": False,
        }

        with self.assertRaises(RaceDayFactsError):
            validate_race_day_facts(facts)

    def test_as_of_requires_timezone(self) -> None:
        facts = {
            "source_kind": "PRE_RACE_SOURCE",
            "as_of": "2026-09-20T14:30:00",
            "weather": "雨",
            "track_condition": "重",
            "result_independent": True,
        }

        with self.assertRaises(RaceDayFactsError):
            validate_race_day_facts(facts)

    def test_at_least_one_race_day_value_is_required(self) -> None:
        facts = {
            "source_kind": "PRE_RACE_SOURCE",
            "as_of": "2026-09-20T14:30:00+09:00",
            "weather": "",
            "track_condition": "",
            "result_independent": True,
        }

        with self.assertRaises(RaceDayFactsError):
            validate_race_day_facts(facts)

    def test_unknown_fields_fail_closed(self) -> None:
        facts = {
            "source_kind": "PRE_RACE_SOURCE",
            "as_of": "2026-09-20T14:30:00+09:00",
            "weather": "雨",
            "track_condition": "重",
            "result_independent": True,
            "result_finish_order": [8, 1, 4],
        }

        with self.assertRaises(RaceDayFactsError):
            validate_race_day_facts(facts)

    def test_non_independent_view_is_rejected(self) -> None:
        view = _independent()
        view["view_kind"] = "FULL"

        with self.assertRaises(RaceDayFactsError):
            attach_race_day_facts(
                view,
                {
                    "source_kind": "PRE_RACE_SOURCE",
                    "as_of": "2026-09-20T14:30:00+09:00",
                    "weather": "雨",
                    "track_condition": "重",
                    "result_independent": True,
                },
            )


if __name__ == "__main__":
    unittest.main()
