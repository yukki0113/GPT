from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from racenote_freeze_prepared_forecast import validate_prepared_record


class V044CoverageBindingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.reader = {
            "race": {"venue": "東京", "race_no": 1},
            "source_semantic_sha256": "source-sha",
            "horses": [
                {"basic": {"horse_no": n, "horse_name": f"馬{n}"}}
                for n in range(1, 8)
            ],
        }
        ref = lambda n: {"horse_no": n, "horse_name": f"馬{n}"}
        self.record = {
            "schema_version": "RaceNote-Forecast-Research-Record-0.4.4",
            "identity": {"target_date": "2026-02-14", "venue": "東京", "race_no": 1},
            "research": {
                "logic_version": "RaceNote-Human-Context-Reader-0.4.4-candidate",
                "independent_forecast": True,
                "baseline_marks_used_as_input": False,
                "reader_facing_prose_contract": "FORECAST_READER_FACING_PROSE_v0_1",
                "authoring_mode": "MODEL_RACE_BY_RACE_REASONING",
                "prose_origin": "MODEL_AUTHORED_NOT_SCRIPT_GENERATED",
            },
            "source": {
                "racenote_identity": "BTDAY-0043/東京1R",
                "racenote_semantic_sha256": "source-sha",
                "reader_input_policy": "TARGET_DAY_MARKET_OBJECT_REMOVED_BEFORE_FORECAST",
            },
            "prediction": {"axis": ref(1), "marks": {
                "main": ref(1), "second": ref(2), "third": ref(3),
                "others": [ref(4), ref(5)],
            }},
            "decision_trace": {
                "mainline_cases": [{"horse": ref(n), "case": f"馬{n}の直接条件を他馬と比較した。"}
                                   for n in (1, 2, 4, 5)],
                "single_shot_case": {"horse": ref(3), "selected_independently_from_mainline": True},
                "rrdb_evidence": {"reviewed": True, "used_in_decision": False,
                                  "horse_refs": [],
                                  "recommendation_contract_version": "rrdb-recommendation-signals-v0.3"},
                "consistency_pass": {
                    "hierarchy_reviewed": True, "hierarchy_changed": False,
                    "single_shot_promotion_reviewed": True, "single_shot_promoted": False,
                    "coverage_scan_reviewed": True,
                    "coverage_scan": {"unmarked_count": 2,
                                      "direct_condition_candidate_count": 0,
                                      "shortlisted_horse_nos": []},
                    "coverage_best_challenger": None,
                    "coverage_challenger_case": None,
                    "coverage_boundary": {"current_delta2": ref(5),
                                          "direct_condition_comparison": None,
                                          "ability_comparison": None,
                                          "race_model_comparison": None},
                    "coverage_verdict": "NO_ELIGIBLE_CHALLENGER",
                    "coverage_changed": False,
                    "coverage_reason": "直接条件の境界に届く馬がいない。",
                    "change_attribution": "UNCHANGED_AFTER_INDEPENDENT_REVIEW",
                },
            },
        }

    def check(self, record: dict) -> None:
        validate_prepared_record(record, self.reader, "BTDAY-0043", "2026-02-14",
                                 "RaceNote-Human-Context-Reader-0.4.4-candidate")

    def test_complete_prepared_record(self) -> None:
        self.check(self.record)

    def test_incomplete_mainline_is_rejected_before_freeze(self) -> None:
        bad = copy.deepcopy(self.record)
        bad["decision_trace"]["mainline_cases"] = bad["decision_trace"]["mainline_cases"][:2]
        with self.assertRaises(AssertionError):
            self.check(bad)

    def test_scan_must_match_roster(self) -> None:
        bad = copy.deepcopy(self.record)
        bad["decision_trace"]["consistency_pass"]["coverage_scan"]["unmarked_count"] = 3
        with self.assertRaises(AssertionError):
            self.check(bad)

    def test_shortlist_cannot_include_marked_horse(self) -> None:
        bad = copy.deepcopy(self.record)
        bad["decision_trace"]["consistency_pass"]["coverage_scan"]["shortlisted_horse_nos"] = [2]
        with self.assertRaises(AssertionError):
            self.check(bad)


if __name__ == "__main__":
    unittest.main()
