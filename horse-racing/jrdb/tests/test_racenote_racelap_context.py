from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import racenote_rrdb_enrichment as rrdb  # noqa: E402


def context(key: str, race_date: str) -> dict:
    return {
        "race": {
            "race_key": key,
            "race_date": race_date,
            "surface_code": "1",
            "distance_m": 1600,
        },
        "coverage": {
            "status": "AVAILABLE",
            "lap_count": 8,
            "comparable_200m_lap_count": 8,
            "partial_first_segment": False,
            "early_late_delta_available": True,
            "optional_srb_context_available": True,
        },
        "shape": {
            "early3f_sec": 35.0,
            "late3f_sec": 34.5,
            "early_late_delta_sec": -0.5,
            "lap_std_sec": 0.4,
            "lap_range_sec": 1.2,
            "fastest_lap_sec": 10.9,
            "fastest_segment_no": 6,
            "max_accel_sec": 0.8,
            "max_decel_sec": 0.6,
            "last_vs_best_sec": 0.2,
            "last3_slope_sec_per_segment": -0.1,
            "pace_up_remaining_furlongs": 3,
        },
        "srb_context": {
            "track_bias": {"straight": "middle"},
            "race_comment": "test",
        },
        "policy": {
            "leader_based": True,
            "individual_sectionals": False,
            "score_status": "NO_ADDITIVE_SCORE",
            "target_race_usage": "HISTORICAL_ONLY_AS_OF_EXCLUSIVE",
        },
        "provenance": {
            "source_kind": "JRDB_SRB",
            "archive": "SED261012.zip",
        },
    }


class FakeRaceLapReader:
    def __init__(self, values: dict[str, dict | None]) -> None:
        self.values = values
        self.calls: list[list[str]] = []

    def get_race_contexts(self, keys):
        keys = list(keys)
        self.calls.append(keys)
        return {key: self.values.get(key) for key in dict.fromkeys(keys)}


class RaceNoteRaceLapContextTest(unittest.TestCase):
    def test_recent_runs_are_enriched_with_one_batch_lookup(self) -> None:
        bundles = [
            {
                "schema_version": "1.0",
                "race": {"date": "2026-10-17", "venue": "東京", "race_no": 1},
                "horses": [
                    {
                        "basic": {"horse_no": 1},
                        "recent_runs": [
                            {"race": {"race_key": "05264501", "date": "2026-10-12"}},
                            {"race": {"race_key": "05264502", "date": "2026-10-11"}},
                        ],
                    },
                    {
                        "basic": {"horse_no": 2},
                        "recent_runs": [
                            {"race": {"race_key": "05264501", "date": "2026-10-12"}},
                        ],
                    },
                ],
            }
        ]
        reader = FakeRaceLapReader({
            "05264501": context("05264501", "2026-10-12"),
            "05264502": context("05264502", "2026-10-11"),
        })
        got = copy.deepcopy(bundles)
        report = rrdb._attach_race_lap_contexts(got, reader, "2026-10-17")

        self.assertEqual(len(reader.calls), 1)
        self.assertEqual(
            reader.calls[0],
            ["05264501", "05264502", "05264501"],
        )
        self.assertEqual(report["requested_run_count"], 3)
        self.assertEqual(report["unique_race_key_count"], 2)
        self.assertEqual(report["found_run_count"], 3)
        self.assertEqual(report["missing_run_count"], 0)

        structure = got[0]["horses"][0]["recent_runs"][0]["race_structure"]
        self.assertEqual(structure["source"], "JRDB_RaceLapReader_v0.1")
        self.assertEqual(structure["lap_shape"]["early_late_delta_sec"], -0.5)
        self.assertEqual(structure["srb_context"]["race_comment"], "test")
        self.assertEqual(
            structure["policy"]["target_race_usage"],
            "HISTORICAL_ONLY_AS_OF_EXCLUSIVE",
        )

    def test_missing_race_lap_is_explicit_not_fabricated(self) -> None:
        bundle = {
            "schema_version": "1.0",
            "race": {"date": "2026-10-17"},
            "horses": [
                {
                    "recent_runs": [
                        {"race": {"race_key": "05264501", "date": "2026-10-12"}}
                    ]
                }
            ],
        }
        reader = FakeRaceLapReader({"05264501": None})
        report = rrdb._attach_race_lap_contexts([bundle], reader, "2026-10-17")
        structure = bundle["horses"][0]["recent_runs"][0]["race_structure"]
        self.assertEqual(structure["coverage"]["status"], "NOT_FOUND")
        self.assertIsNone(structure["lap_shape"])
        self.assertEqual(report["missing_run_count"], 1)

    def test_target_or_future_run_fails_closed(self) -> None:
        bundle = {
            "schema_version": "1.0",
            "race": {"date": "2026-10-17"},
            "horses": [
                {
                    "recent_runs": [
                        {"race": {"race_key": "05264501", "date": "2026-10-17"}}
                    ]
                }
            ],
        }
        with self.assertRaises(rrdb.RRDBEnrichmentError):
            rrdb._attach_race_lap_contexts(
                [bundle],
                FakeRaceLapReader({}),
                "2026-10-17",
            )

    def test_reader_date_mismatch_fails_closed(self) -> None:
        bundle = {
            "schema_version": "1.0",
            "race": {"date": "2026-10-17"},
            "horses": [
                {
                    "recent_runs": [
                        {"race": {"race_key": "05264501", "date": "2026-10-12"}}
                    ]
                }
            ],
        }
        reader = FakeRaceLapReader({
            "05264501": context("05264501", "2026-10-11"),
        })
        with self.assertRaises(rrdb.RRDBEnrichmentError):
            rrdb._attach_race_lap_contexts([bundle], reader, "2026-10-17")


if __name__ == "__main__":
    unittest.main()
