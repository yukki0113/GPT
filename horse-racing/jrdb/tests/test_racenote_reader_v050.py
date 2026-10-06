from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import racenote_reader_v050 as candidate
import racenote_reader_view as v046

POLICY = Path(__file__).resolve().parents[1] / "docs" / "racenote" / "research-work" / "results" / "stage_c" / "reader_feature_policy_v0_5_candidate.json"
BINDING = Path(__file__).resolve().parents[1] / "config" / "racenote_reader_v050_binding.json"


def clean_view(horse: dict | None = None, surface: str = "芝") -> dict:
    source = {
        "schema_version": "1.0",
        "metadata": {"data_phase": "pre_race"},
        "race": {"date": "2026-10-06", "venue": "東京", "race_no": 1, "surface": surface, "distance_m": 1600},
        "horses": [horse or {"basic": {"horse_no": 1, "horse_name": "Fixture"}}],
    }
    return v046.build_reader_view(source)


def set_path(horse: dict, path: str, value: object) -> None:
    parts = path.split(".")
    node = horse
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


class CandidateReaderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.binding = candidate.load_binding(BINDING)
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))

    def test_all_73_policy_entries_bind_and_every_value_is_accounted_for(self) -> None:
        candidate.validate_policy_binding(self.binding, self.policy)
        horse = {"basic": {"horse_no": 1, "horse_name": "Fixture"}}
        for row in self.binding["entries"]:
            set_path(horse, row["source_path"], 10)
        view = candidate.transform(clean_view(horse), self.binding)
        shown = {
            fid
            for tiers in view["normal_view"]["horses"][0]["evidence"].values()
            for fields in tiers.values()
            for fid in fields
        }
        detail = {item["feature_id"] for item in view["provenance"]["horses"][0]["detail"]}
        self.assertEqual(shown | detail, {r["feature_id"] for r in self.binding["entries"]})
        self.assertFalse(shown & detail)
        self.assertEqual(len(shown | detail), 73)
        hidden = {r["feature_id"] for r in self.binding["entries"] if r["tier"] == "REDUNDANT_HIDDEN"}
        self.assertFalse(shown & hidden)
        self.assertTrue(hidden <= detail)

    def test_missing_is_not_synthesized_and_source_provenance_is_retained(self) -> None:
        horse = {"basic": {"horse_no": 1}, "training": {"analysis": {"training_index": 54}},
                 "ability": {"distance_fit": None}, "condition": {"rest_reason": "休養"}}
        view = candidate.transform(clean_view(horse), self.binding)
        detail = view["provenance"]["horses"][0]
        self.assertIn("cha_clock_index_total", detail["missing_feature_ids"])
        self.assertIsNone(detail["divergence"])
        self.assertNotIn("cha_clock_index_total", {x["feature_id"] for x in detail["detail"]})
        states = {x["feature_id"]: x["state"] for x in detail["missing_features"]}
        self.assertEqual(states["distance_fit"], "null")
        self.assertEqual(states["cha_clock_index_total"], "absent")
        self.assertEqual(view["normal_view"]["horses"][0]["evidence"]["TRAINING_CONDITION"]["C"]["cyb_training_index"], 54)
        self.assertEqual(view["normal_view"]["horses"][0]["other_context"]["condition"]["rest_reason"], "休養")

    def test_cha_cyb_divergence_is_explicit(self) -> None:
        horse = {
            "basic": {"horse_no": 1},
            "training": {
                "analysis": {"training_index": 54},
                "main_workout": {"clock_index": {"total": 55}},
            },
        }
        view = candidate.transform(clean_view(horse), self.binding)
        p = view["provenance"]["horses"][0]
        self.assertEqual(p["divergence"]["type"], "CHA_CYB_TRAINING_DIVERGENCE")
        self.assertEqual(next(x for x in p["detail"] if x["feature_id"] == "cha_clock_index_total")["value"], 55)

    def test_suitability_is_conditional_on_surface(self) -> None:
        horse = {"basic": {"horse_no": 1}, "ability": {"surface_fit": {"turf": "○", "dirt": "△"}}}
        view = candidate.transform(clean_view(horse, "芝"), self.binding)
        shown = view["normal_view"]["horses"][0]["evidence"]["SUITABILITY"]["C"]
        self.assertIn("turf_fit", shown)
        self.assertNotIn("dirt_fit", shown)
        self.assertIn("dirt_fit", {x["feature_id"] for x in view["provenance"]["horses"][0]["detail"]})

    def test_non_fit_context_is_hidden_by_default_with_provenance(self) -> None:
        horse = {
            "basic": {"horse_no": 1},
            "pace": {"start_index": 8, "late_break_rate": 3},
            "condition": {"farm": {"rank": "A"}},
            "training": {
                "main_workout": {"course": "南W", "clock": {"front": 12}},
                "analysis": {"course_counts": {"wood": 2}, "training_index": 54},
            },
            "jrdb_ratings": {"jockey_index": 10},
        }
        view = candidate.transform(clean_view(horse), self.binding)
        normal_ids = {
            fid
            for tiers in view["normal_view"]["horses"][0]["evidence"].values()
            for fields in tiers.values()
            for fid in fields
        }
        detail_ids = {entry["feature_id"] for entry in view["provenance"]["horses"][0]["detail"]}
        gated = {
            "start_index", "late_break_rate", "farm_rank", "cha_course",
            "cha_clock_front", "cyb_course_count_wood",
        }
        self.assertFalse(normal_ids & gated)
        self.assertTrue(gated <= detail_ids)
        self.assertTrue({"jockey_index", "cyb_training_index"} <= normal_ids)

    def test_same_clean_input_and_v046_non_regression(self) -> None:
        clean = clean_view({"basic": {"horse_no": 1}, "ability": {"idm": 60, "total_index": 58}})
        before = copy.deepcopy(clean)
        original_bytes = candidate.compact_bytes(clean)
        view = candidate.transform(clean, self.binding)
        self.assertEqual(clean, before)
        self.assertEqual(candidate.compact_bytes(clean), original_bytes)
        self.assertEqual(v046.expand_reader_view(clean)["horses"][0]["ability"]["idm"], 60)
        self.assertEqual(view["candidate_version"], candidate.VERSION)
        self.assertNotEqual(view["candidate_version"], "RaceNote-Human-Context-Reader-0.4.6-candidate")

    def test_target_market_and_result_are_rejected(self) -> None:
        for key in ("market", "target_result", "win_payout", "result"):
            clean = clean_view()
            clean["horses"][0][key] = {"value": 1}
            with self.assertRaises(candidate.CandidateReaderError):
                candidate.transform(clean, self.binding)

    def test_current_pointer_remains_v046(self) -> None:
        pointer = Path(__file__).resolve().parents[1] / "config" / "racenote_forecast_logic_current.json"
        self.assertNotIn(candidate.VERSION, pointer.read_text(encoding="utf-8"))

    def test_committed_clean_reader_structural_integration(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "backtests" / "BTDAY-0048" / "20260207" / "forecast_prep" / "reader" / "racenote_reader_20260207_東京1R.json"
        clean = json.loads(fixture.read_text(encoding="utf-8"))
        transformed = candidate.transform(clean, self.binding)
        measured = candidate.metrics(clean, transformed, self.binding)
        self.assertGreater(measured["duplicate_representations_removed_from_normal"], 0)
        self.assertEqual(measured["source_families_in_normal"], ["BAC", "CHA", "CYB", "KYI"])
        self.assertEqual(len(transformed["normal_view"]["horses"]), len(clean["horses"]))
        self.assertEqual(len(transformed["provenance"]["horses"]), len(clean["horses"]))


if __name__ == "__main__":
    unittest.main()
