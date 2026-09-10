#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC))

from jrdb_newspaper_merge_external import merge_day  # noqa: E402


def _horse(horse_no: int, name: str) -> dict:
    return {
        "key": {"horse_no": horse_no, "frame_no": 1},
        "basic": {"horse_name": name},
        "jrdb": {"marks": {}, "ability": {}, "training": {}, "pace": {}},
        "addons": {"eval": None, "racenote_prediction": None, "keibailuka": None, "my_index": None},
        "history": [],
        "edge_matches": [],
    }


def _write_day(root: Path) -> Path:
    day = root / "day"
    races = day / "races"
    races.mkdir(parents=True)
    bundle = {
        "schema_version": "0.1",
        "bundle_kind": "jrdb_pwa_newspaper_race",
        "metadata": {
            "generated_at": "2026-09-05T00:00:00+00:00",
            "revision": 1,
            "source_status": {
                "jrdb_base": {"state": "READY"},
                "jrdb_history": {"state": "READY", "coverage_complete": True},
                "eval": {"state": "PENDING"},
                "racenote_prediction": {"state": "PENDING"},
                "keibailuka": {"state": "PENDING"},
            },
        },
        "race": {
            "race_key": "01262501",
            "date": "2026-09-05",
            "venue_code": "01",
            "venue": "札幌",
            "race_no": 1,
            "field_size": 2,
        },
        "race_notes": {"items": []},
        "horses": [_horse(1, "カセノメロス"), _horse(2, "シンゼンノト")],
    }
    race_path = races / "01_01_01262501.json"
    race_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "schema_version": "0.1",
        "manifest_kind": "jrdb_pwa_newspaper_daily_manifest",
        "date": "2026-09-05",
        "revision": 1,
        "generated_at": "2026-09-05T00:00:00+00:00",
        "source_status": {
            "jrdb_base": {"state": "READY"},
            "jrdb_history": {"state": "READY"},
            "eval": {"state": "PENDING"},
            "racenote_prediction": {"state": "PENDING"},
            "keibailuka": {"state": "PENDING"},
        },
        "completeness": {"expected_races": 1, "ready_races": 1},
        "races": [{
            "race_key": "01262501",
            "venue_code": "01",
            "venue": "札幌",
            "race_no": 1,
            "path": "races/01_01_01262501.json",
            "revision": 1,
            "sha256": "0" * 64,
            "size_bytes": race_path.stat().st_size,
            "horse_count": 2,
        }],
    }
    (day / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (day / "audit.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    return day


def _write_racenote(path: Path, *, second_name: str = "シンゼンノト", second_rank: int = 1,
                    second_mark: str = "◎") -> None:
    fields = [
        "date", "venue_code", "venue", "race_no", "race_key", "horse_no", "horse_name", "mark",
        "prediction_rank", "confidence", "race_short_comment", "model_version", "source_semantic_sha256",
    ]
    digest = "a" * 64
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([
            {
                "date": "2026-09-05", "venue_code": "01", "venue": "札幌", "race_no": 1,
                "race_key": "01262501", "horse_no": 1, "horse_name": "カセノメロス", "mark": "○",
                "prediction_rank": 2, "confidence": "B", "race_short_comment": "平均的な流れを想定。",
                "model_version": "v0.2-test", "source_semantic_sha256": digest,
            },
            {
                "date": "2026-09-05", "venue_code": "01", "venue": "札幌", "race_no": 1,
                "race_key": "01262501", "horse_no": 2, "horse_name": second_name, "mark": second_mark,
                "prediction_rank": second_rank, "confidence": "B", "race_short_comment": "平均的な流れを想定。",
                "model_version": "v0.2-test", "source_semantic_sha256": digest,
            },
        ])


class NewspaperExternalMergeTest(unittest.TestCase):
    def test_racenote_complete_exact_merge_and_day_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            rn = root / "RaceNote_prediction_20260905_PWA_handoff_v0_1.csv"
            _write_racenote(rn)
            output = root / "merged"

            result = merge_day(day, output, revision=2, racenote_csv=rn)
            bundle = json.loads((output / "races/01_01_01262501.json").read_text(encoding="utf-8"))
            package = json.loads((output / "day-package.json").read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["racenote_prediction"]["merged_races"], 1)
        self.assertEqual(result["racenote_prediction"]["merged_horses"], 2)
        self.assertEqual(bundle["horses"][0]["addons"]["racenote_prediction"]["mark"], "○")
        self.assertEqual(bundle["horses"][0]["addons"]["racenote_prediction"]["prediction_rank"], 2)
        self.assertEqual(bundle["horses"][1]["addons"]["racenote_prediction"]["mark"], "◎")
        self.assertEqual(bundle["race_notes"]["racenote_short_comment"], "平均的な流れを想定。")
        self.assertEqual(bundle["metadata"]["source_status"]["racenote_prediction"]["state"], "READY")
        self.assertEqual(package["bundle_kind"], "jrdb_pwa_newspaper_day_package")
        self.assertEqual(package["manifest"]["source_status"]["racenote_prediction"]["state"], "READY")

    def test_racenote_horse_name_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            rn = root / "rn.csv"
            _write_racenote(rn, second_name="別馬")
            with self.assertRaisesRegex(ValueError, "horse-name mismatch"):
                merge_day(day, root / "merged", revision=2, racenote_csv=rn)

    def test_racenote_rank_mark_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            rn = root / "rn.csv"
            _write_racenote(rn, second_rank=1, second_mark="△")
            with self.assertRaisesRegex(ValueError, "mark/rank mismatch"):
                merge_day(day, root / "merged", revision=2, racenote_csv=rn)

    def test_racenote_incomplete_rank_set_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            rn = root / "rn.csv"
            _write_racenote(rn, second_rank=3, second_mark="▲")
            with self.assertRaisesRegex(ValueError, "ranks are not complete"):
                merge_day(day, root / "merged", revision=2, racenote_csv=rn)


if __name__ == "__main__":
    unittest.main()
