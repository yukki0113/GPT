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

from jrdb_newspaper_merge_external import load_racenote, merge_day  # noqa: E402


def _write_csv(path: Path, *, with_comment_column: bool = True, bad_top3: bool = False,
               bad_non_top3: bool = False) -> None:
    fields = [
        "date", "venue_code", "venue", "race_no", "race_key", "horse_no", "horse_name", "mark",
        "prediction_rank", "confidence", "race_short_comment",
    ]
    if with_comment_column:
        fields.append("horse_short_comment")
    fields += ["model_version", "source_semantic_sha256"]
    digest = "b" * 64
    rows = []
    marks = {1: "◎", 2: "○", 3: "▲", 4: "△"}
    names = ["テストイチ", "テストニ", "テストサン", "テストヨン"]
    for rank, name in enumerate(names, start=1):
        row = {
            "date": "2026-09-05",
            "venue_code": "01",
            "venue": "札幌",
            "race_no": 1,
            "race_key": "01262501",
            "horse_no": rank,
            "horse_name": name,
            "mark": marks[rank],
            "prediction_rank": rank,
            "confidence": "B",
            "race_short_comment": "平均的な流れを想定。",
            "model_version": "v0.2-test",
            "source_semantic_sha256": digest,
        }
        if with_comment_column:
            row["horse_short_comment"] = f"{name}の短評" if rank <= 3 else ""
        rows.append(row)
    if with_comment_column and bad_top3:
        rows[1]["horse_short_comment"] = ""
    if with_comment_column and bad_non_top3:
        rows[3]["horse_short_comment"] = "4位馬には入れてはいけない短評"

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_day(root: Path) -> Path:
    day = root / "day"
    races = day / "races"
    races.mkdir(parents=True)
    horses = []
    for horse_no, name in enumerate(["テストイチ", "テストニ", "テストサン", "テストヨン"], start=1):
        horses.append({
            "key": {"horse_no": horse_no, "frame_no": 1},
            "basic": {"horse_name": name},
            "jrdb": {"marks": {}, "ability": {}, "training": {}, "pace": {}},
            "addons": {"eval": None, "racenote_prediction": None, "keibailuka": None, "my_index": None},
            "history": [],
            "edge_matches": [],
        })
    bundle = {
        "schema_version": "0.1",
        "bundle_kind": "jrdb_pwa_newspaper_race",
        "metadata": {
            "generated_at": "2026-09-05T00:00:00+00:00",
            "revision": 1,
            "source_status": {
                "jrdb_base": {"state": "READY"},
                "jrdb_history": {"state": "READY"},
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
            "field_size": 4,
        },
        "race_notes": {"items": []},
        "horses": horses,
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
            "horse_count": 4,
        }],
    }
    (day / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (day / "audit.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    return day


class RaceNoteHorseCommentExtensionTest(unittest.TestCase):
    def test_legacy_v01_without_comment_column_remains_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            path = Path(tmp_name) / "legacy.csv"
            _write_csv(path, with_comment_column=False)
            index, races, _ = load_racenote(path)
        self.assertEqual(len(index), 4)
        self.assertFalse(next(iter(races.values()))["horse_comment_enabled"])

    def test_comment_extension_merges_top3_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            csv_path = root / "rn.csv"
            _write_csv(csv_path)
            result = merge_day(day, root / "merged", revision=2, racenote_csv=csv_path)
            bundle = json.loads((root / "merged/races/01_01_01262501.json").read_text(encoding="utf-8"))
        comments = [
            horse["addons"]["racenote_prediction"].get("horse_short_comment")
            for horse in bundle["horses"]
        ]
        self.assertEqual(comments[:3], ["テストイチの短評", "テストニの短評", "テストサンの短評"])
        self.assertIsNone(comments[3])
        self.assertTrue(result["racenote_prediction"]["horse_comment_extension"])
        self.assertEqual(result["racenote_prediction"]["expected_horse_comments"], 3)
        self.assertEqual(result["racenote_prediction"]["merged_horse_comments"], 3)

    def test_top3_comment_missing_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            path = Path(tmp_name) / "rn.csv"
            _write_csv(path, bad_top3=True)
            with self.assertRaisesRegex(ValueError, "horse_short_comment required"):
                load_racenote(path)

    def test_non_top3_comment_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            path = Path(tmp_name) / "rn.csv"
            _write_csv(path, bad_non_top3=True)
            with self.assertRaisesRegex(ValueError, "must be blank outside top-3"):
                load_racenote(path)


if __name__ == "__main__":
    unittest.main()
