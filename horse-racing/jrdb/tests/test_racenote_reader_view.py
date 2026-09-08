from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(TEST_ROOT))

import racenote_reader_view as reader_view  # noqa: E402


STAT_CONTEXT = {
    "period": {"from_year": 2020, "to_year": 2024},
    "as_of_exclusive": "2024-12-28",
    "track_condition_scope": "all_conditions",
    "source": "JRDB Stats Mart + Analysis Lite YTD",
}
PROFILE_CONTEXT = {
    "source": "JRDB Analysis Lite",
    "source_window_start": "2016-01-01",
    "as_of_exclusive": "2024-12-28",
}


def summary(starts: int, wins: int, top3: int, **overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "starts": starts,
        "wins": wins,
        "top3": top3,
        "win_rate": 10.0 if starts else None,
        "top3_rate": 30.0 if starts else None,
        "sample_size_band": "small" if starts else "none",
        **copy.deepcopy(STAT_CONTEXT),
    }
    value.update(overrides)
    return value


def profile() -> dict[str, object]:
    return {
        **copy.deepcopy(PROFILE_CONTEXT),
        "career": {
            "starts": 10,
            "wins": 2,
            "top3": 5,
            "win_rate": 20.0,
            "top3_rate": 50.0,
            "sample_size_band": "small",
        },
        "same_surface": {
            "starts": 8,
            "wins": 2,
            "top3": 4,
            "win_rate": 25.0,
            "top3_rate": 50.0,
            "sample_size_band": "small",
        },
        "same_distance": {
            "starts": 3,
            "wins": 1,
            "top3": 2,
            "win_rate": 33.3,
            "top3_rate": 66.7,
            "sample_size_band": "small",
        },
        "distance_ranges": [],
        "same_venue": {
            "starts": 2,
            "wins": 0,
            "top3": 1,
            "win_rate": 0.0,
            "top3_rate": 50.0,
            "sample_size_band": "small",
        },
    }


def bundle() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "metadata": {
            "generated_at": "2026-09-08T00:00:00Z",
            "history_enrichment": {"version": "1.0"},
        },
        "race": {
            "date": "2024-12-28",
            "venue": "中山",
            "race_no": 11,
            "surface": "芝",
            "distance_m": 2000,
            "race_trends": {
                "frame": {
                    "1": summary(20, 2, 6),
                    "2": summary(18, 1, 5),
                }
            },
        },
        "horses": [
            {
                "basic": {"horse_no": 1, "horse_name": "テストホースA"},
                "recent_runs": [{"date": "2024-11-30", "finish": 1}],
                "older_runs": [],
                "historical_profile": profile(),
                "history_coverage": {"scope": "jrdb_jra_history"},
                "stats": {
                    "sire": {
                        **summary(40, 4, 12),
                        "distance_ranges": [summary(15, 2, 5)],
                    },
                    "jockey": {
                        **summary(50, 5, 15),
                        "distance_ranges": [summary(20, 3, 8)],
                    },
                },
            },
            {
                "basic": {"horse_no": 2, "horse_name": "テストホースB"},
                "recent_runs": [],
                "older_runs": [],
                "historical_profile": profile(),
                "history_coverage": {"scope": "jrdb_jra_history"},
                "stats": {
                    "sire": {
                        **summary(30, 3, 10),
                        "distance_ranges": [],
                    },
                    "jockey": {
                        **summary(60, 6, 20),
                        "distance_ranges": [],
                    },
                },
            },
        ],
    }


class RaceNoteReaderViewTest(unittest.TestCase):
    def test_uniform_contexts_are_hoisted_and_roundtrip_is_exact(self) -> None:
        source = bundle()
        view = reader_view.build_reader_view(source)

        self.assertEqual(view["view_version"], "0.1")
        self.assertEqual(view["shared_context"]["stats"], STAT_CONTEXT)
        self.assertEqual(
            view["shared_context"]["historical_profile"],
            PROFILE_CONTEXT,
        )
        restored = reader_view.expand_reader_view(view)
        self.assertEqual(restored, source)
        self.assertEqual(
            reader_view.semantic_sha256(restored),
            view["source_semantic_sha256"],
        )

    def test_source_is_not_mutated(self) -> None:
        source = bundle()
        before = copy.deepcopy(source)
        reader_view.build_reader_view(source)
        self.assertEqual(source, before)

    def test_mixed_stat_context_is_not_hoisted(self) -> None:
        source = bundle()
        source["horses"][1]["stats"]["jockey"]["source"] = "different"
        view = reader_view.build_reader_view(source)
        self.assertNotIn("stats", view["shared_context"])
        self.assertEqual(reader_view.expand_reader_view(view), source)

    def test_mixed_profile_context_is_not_hoisted(self) -> None:
        source = bundle()
        source["horses"][1]["historical_profile"]["source_window_start"] = "2017-01-01"
        view = reader_view.build_reader_view(source)
        self.assertNotIn("historical_profile", view["shared_context"])
        self.assertEqual(reader_view.expand_reader_view(view), source)

    def test_null_profile_does_not_block_context_hoist_for_observed_profiles(self) -> None:
        source = bundle()
        source["horses"][1]["historical_profile"] = None
        view = reader_view.build_reader_view(source)
        self.assertEqual(
            view["shared_context"]["historical_profile"],
            PROFILE_CONTEXT,
        )
        self.assertEqual(reader_view.expand_reader_view(view), source)

    def test_tampering_is_detected_by_semantic_hash(self) -> None:
        view = reader_view.build_reader_view(bundle())
        view["horses"][0]["basic"]["horse_name"] = "改ざん"
        with self.assertRaisesRegex(
            reader_view.ReaderViewError,
            "expanded semantic hash mismatch",
        ):
            reader_view.expand_reader_view(view)

    def test_wrong_source_schema_is_rejected(self) -> None:
        source = bundle()
        source["schema_version"] = "9.9"
        with self.assertRaisesRegex(
            reader_view.ReaderViewError,
            "requires RaceNote schema 1.0",
        ):
            reader_view.build_reader_view(source)

    def test_compact_writer_roundtrips_json(self) -> None:
        view = reader_view.build_reader_view(bundle())
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "reader_view.json"
            reader_view.write_reader_view(output, view)
            text = output.read_text(encoding="utf-8")
            self.assertNotIn("\n  ", text)
            self.assertEqual(json.loads(text), view)


if __name__ == "__main__":
    unittest.main()