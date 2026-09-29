from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import racenote_history_engine as engine  # noqa: E402
from racenote_analysis_backend import TARGET_COLUMNS  # noqa: E402


class PedigreeP1P2Test(unittest.TestCase):
    def test_pedigree_identity_uses_only_available_fields(self) -> None:
        row = {
            "horse_id": "24103816",
            "sire_name": "サリオス",
            "broodmare_sire_name": "ゼンノロブロイ",
            "sire_line_code": "1206",
            "broodmare_sire_line_code": "1601",
        }
        got = engine.pedigree_identity(row, "24103816")
        self.assertEqual(got["sire_name"], "サリオス")
        self.assertIsNone(got["dam_name"])
        self.assertEqual(got["broodmare_sire_name"], "ゼンノロブロイ")
        self.assertEqual(got["coverage_status"], "PARTIAL")
        self.assertFalse(got["scoring"])

    def test_full_coverage_when_maternal_name_is_available(self) -> None:
        row = {
            "horse_id": "x",
            "sire_name": "父",
            "dam_name": "母",
            "broodmare_sire_name": "母父",
            "sire_line_code": "1",
            "broodmare_sire_line_code": "2",
        }
        got = engine.pedigree_identity(row, "x")
        self.assertEqual(got["coverage_status"], "FULL")

    def test_none_coverage_never_guesses(self) -> None:
        got = engine.pedigree_identity({}, None)
        self.assertEqual(got["coverage_status"], "NONE")
        self.assertIsNone(got["sire_name"])
        self.assertIsNone(got["dam_name"])
        self.assertIsNone(got["broodmare_sire_name"])

    def test_p2_context_keeps_sire_and_broodmare_sire_separate(self) -> None:
        calls = []

        def builder(column, value):
            calls.append((column, value))
            return {
                "starts": 12 if column == "sire_name" else 4,
                "wins": 2 if column == "sire_name" else 0,
                "top3": 5 if column == "sire_name" else 1,
                "sample_size_band": "small",
                "as_of_exclusive": "2026-05-23",
                "distance_ranges": [],
            }

        got = engine.pedigree_historical_context(
            sire_name="父A",
            broodmare_sire_name="母父B",
            statistic_builder=builder,
        )
        self.assertEqual(calls, [("sire_name", "父A"), ("broodmare_sire_name", "母父B")])
        self.assertEqual(got["coverage_status"], "FULL")
        self.assertEqual(got["sire"]["starts"], 12)
        self.assertEqual(got["broodmare_sire"]["starts"], 4)
        self.assertFalse(got["scoring"])
        self.assertEqual(got["small_sample_policy"], "retain_with_sample_size")

    def test_p2_partial_coverage_does_not_guess_missing_broodmare_sire(self) -> None:
        got = engine.pedigree_historical_context(
            sire_name="父A",
            broodmare_sire_name=None,
            statistic_builder=lambda column, value: {"starts": 1},
        )
        self.assertEqual(got["coverage_status"], "PARTIAL")
        self.assertIsNotNone(got["sire"])
        self.assertIsNone(got["broodmare_sire"])

    def test_target_projection_excludes_result_and_market_fields(self) -> None:
        lowered = TARGET_COLUMNS.lower()
        for forbidden in (
            "finish",
            "final_win_odds",
            "final_win_popularity",
            "win_payout",
            "place_payout",
            "abnormal_code",
        ):
            self.assertNotIn(forbidden, lowered)
        for allowed in (
            "horse_id",
            "sire_name",
            "broodmare_sire_name",
            "sire_line_code",
            "broodmare_sire_line_code",
        ):
            self.assertIn(allowed, lowered)


if __name__ == "__main__":
    unittest.main()
