from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import racenote_reader_v054 as v054


def base_candidate(rrdb_version: str):
    return {
        "normal_view": {
            "race": {"date": "2025-07-12"},
            "horses": [{
                "identity": {"horse_no": 3},
                "evidence": {},
                "other_context": {
                    "racereview": {
                        "history_status": "AVAILABLE",
                        "recommendation": {
                            "contract_version": rrdb_version,
                            "status": "NO_MATCH",
                            "signals": [],
                        },
                        "next_watch": {"status": "DEPRECATED"},
                    }
                }
            }]
        },
        "provenance": {"horses": []},
    }


class V054ReaderTest(unittest.TestCase):
    def test_canonical_v05_is_promoted_without_duplicate_old_signal(self):
        result = base_candidate("rrdb-recommendation-signals-v0.5")
        with patch.object(v054.v053, "transform", return_value=copy.deepcopy(result)):
            projected = v054.transform({"not": "used"}, {})
        h = projected["normal_view"]["horses"][0]
        self.assertEqual(h["rrdb_v05"]["contract_version"], "rrdb-recommendation-signals-v0.5")
        self.assertEqual(h["rrdb_v05"]["status"], "NO_MATCH")
        self.assertNotIn("recommendation", h["other_context"]["racereview"])
        self.assertNotIn("next_watch", h["other_context"]["racereview"])

    def test_legacy_v04_does_not_masquerade_as_v05(self):
        result = base_candidate("rrdb-recommendation-signals-v0.4")
        with patch.object(v054.v053, "transform", return_value=copy.deepcopy(result)):
            projected = v054.transform({"not": "used"}, {})
        h = projected["normal_view"]["horses"][0]
        self.assertEqual(h["rrdb_v05"]["status"], "UNAVAILABLE")

    def test_supplied_v05_replaces_legacy_no_double_counting(self):
        result = base_candidate("rrdb-recommendation-signals-v0.4")
        with patch.object(v054.v053, "transform", return_value=copy.deepcopy(result)):
            projected = v054.transform({"not": "used"}, {}, rrdb_by_horse={
                3: {
                    "contract_version": "rrdb-recommendation-signals-v0.5",
                    "status": "MATCHED",
                    "signals": [{"signal_id": "TIME_CLASS_PLUS1"}],
                },
            })
        h = projected["normal_view"]["horses"][0]
        self.assertEqual(len(h["rrdb_v05"]["signals"]), 1)
        self.assertNotIn("recommendation", h["other_context"]["racereview"])

    def test_lap_reader_needs_target_date(self):
        result = base_candidate("rrdb-recommendation-signals-v0.5")
        with patch.object(v054.v053, "transform", return_value=copy.deepcopy(result)):
            with self.assertRaisesRegex(ValueError, "target_date"):
                v054.transform({"not": "used"}, {}, race_lap_reader=object())


if __name__ == "__main__":
    unittest.main()
