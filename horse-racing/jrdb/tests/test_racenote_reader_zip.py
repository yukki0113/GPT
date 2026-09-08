from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(TEST_ROOT))

import racenote_reader_view as reader_view  # noqa: E402
import racenote_reader_zip as reader_zip  # noqa: E402


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


def summary(starts: int, wins: int, top3: int) -> dict[str, object]:
    return {
        "starts": starts,
        "wins": wins,
        "top3": top3,
        "win_rate": 10.0 if starts else None,
        "top3_rate": 30.0 if starts else None,
        "sample_size_band": "small" if starts else "none",
        **copy.deepcopy(STAT_CONTEXT),
    }


def bundle(horse_no: int) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "metadata": {"history_enrichment": {"version": "1.0"}},
        "race": {
            "date": "2024-12-28",
            "venue": "中山",
            "race_no": 11,
            "surface": "芝",
            "distance_m": 2000,
            "race_trends": {"frame": {"1": summary(20, 2, 6)}},
        },
        "horses": [{
            "basic": {"horse_no": horse_no, "horse_name": f"テスト{horse_no}"},
            "recent_runs": [],
            "older_runs": [],
            "historical_profile": {
                **copy.deepcopy(PROFILE_CONTEXT),
                "career": summary(10, 2, 5),
                "same_surface": summary(8, 2, 4),
                "same_distance": summary(3, 1, 2),
                "distance_ranges": [],
                "same_venue": summary(2, 0, 1),
            },
            "history_coverage": {"scope": "jrdb_jra_history"},
            "stats": {
                "sire": {**summary(40, 4, 12), "distance_ranges": []},
                "jockey": {**summary(50, 5, 15), "distance_ranges": []},
            },
        }],
    }


class RaceNoteReaderZipTest(unittest.TestCase):
    def make_zip(self, path: Path, bundle_names: list[str], stale_view: bool = False) -> dict[str, bytes]:
        original: dict[str, bytes] = {}
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "request_manifest.json",
                json.dumps(
                    {"bundle_count": len(bundle_names), "bundles": bundle_names},
                    ensure_ascii=False,
                    indent=2,
                ) + "\n",
            )
            for index, name in enumerate(bundle_names, start=1):
                payload = (
                    json.dumps(bundle(index), ensure_ascii=False, indent=2) + "\n"
                ).encode("utf-8")
                original[name] = payload
                archive.writestr(name, payload)
            if stale_view:
                archive.writestr("reader_view_stale.json", "{}")
        return original

    def test_decorate_preserves_authoritative_bytes_and_roundtrips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "RaceNote.zip"
            output = root / "RaceNote_reader.zip"
            name = "race_bundle_20241228_中山11R.json"
            original = self.make_zip(source, [name])

            report = reader_zip.decorate_request_zip(source, output)
            self.assertEqual(report["reader_view_count"], 1)
            with zipfile.ZipFile(output, "r") as archive:
                self.assertEqual(archive.read(name), original[name])
                view_name = "reader_view_20241228_中山11R.json"
                view = json.loads(archive.read(view_name).decode("utf-8"))
                self.assertEqual(reader_view.expand_reader_view(view), bundle(1))
                manifest = json.loads(archive.read("request_manifest.json").decode("utf-8"))
                self.assertEqual(manifest["reader_view_version"], "0.1")
                self.assertEqual(manifest["reader_view_count"], 1)
                self.assertEqual(
                    manifest["reader_views"][0]["roundtrip_validation"],
                    "PASS",
                )

    def test_multiple_bundles_and_stale_view_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "RaceNote.zip"
            output = root / "RaceNote_reader.zip"
            names = [
                "race_bundle_20241228_中山10R.json",
                "race_bundle_20241228_中山11R.json",
            ]
            self.make_zip(source, names, stale_view=True)
            report = reader_zip.decorate_request_zip(source, output)
            self.assertEqual(report["reader_view_count"], 2)
            with zipfile.ZipFile(output, "r") as archive:
                self.assertNotIn("reader_view_stale.json", archive.namelist())
                self.assertIn("reader_view_20241228_中山10R.json", archive.namelist())
                self.assertIn("reader_view_20241228_中山11R.json", archive.namelist())

    def test_missing_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "broken.zip"
            output = root / "out.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr(
                    "race_bundle_20241228_中山11R.json",
                    json.dumps(bundle(1), ensure_ascii=False),
                )
            with self.assertRaisesRegex(reader_zip.ReaderZipError, "missing request_manifest"):
                reader_zip.decorate_request_zip(source, output)

    def test_in_place_overwrite_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "RaceNote.zip"
            self.make_zip(source, ["race_bundle_20241228_中山11R.json"])
            with self.assertRaisesRegex(reader_zip.ReaderZipError, "output must differ"):
                reader_zip.decorate_request_zip(source, source)


if __name__ == "__main__":
    unittest.main()
