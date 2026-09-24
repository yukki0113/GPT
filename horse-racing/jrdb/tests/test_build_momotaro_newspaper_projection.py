#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "build_momotaro_newspaper_projection.py"

SPEC = importlib.util.spec_from_file_location(
    "build_momotaro_newspaper_projection",
    MODULE_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("failed to load Momotaro projection module")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MomotaroProjectionTest(unittest.TestCase):
    def _write_source_day(self, root: Path) -> Path:
        day = root / "source"
        races = day / "races"
        races.mkdir(parents=True)

        bundle = {
            "schema_version": "0.1",
            "bundle_kind": "jrdb_pwa_newspaper_race",
            "race": {
                "date": "2026-09-26",
                "venue_code": "09",
                "venue": "阪神",
                "race_no": 1,
                "race_key": "09264601",
                "field_size": 1,
            },
            "metadata": {
                "source_status": {
                    "jrdb_base": {"state": "READY"},
                    "jrdb_history": {"state": "READY"},
                    "keibailuka": {"state": "READY"},
                    "eval": {"state": "READY"},
                    "racenote_prediction": {"state": "READY"},
                    "edge": {"state": "READY"},
                    "my_index": {"state": "READY"},
                }
            },
            "race_notes": {
                "items": [{"label": "予想ペース", "value": "M"}],
                "racenote_short_comment": "個人用短評",
            },
            "horses": [
                {
                    "key": {"horse_no": 1, "frame_no": 1},
                    "basic": {"horse_name": "テストホース"},
                    "jrdb": {"ability": {"idm": 50.0}},
                    "history": [],
                    "addons": {
                        "eval": {"eval": 60},
                        "racenote_prediction": {"mark": "◎"},
                        "keibailuka": {"comment": "イルカコメント"},
                        "my_index": {"training_edge_index": 80.1},
                    },
                    "edge_matches": [{"id": "private-edge"}],
                }
            ],
        }
        race_path = races / "09_01_09264601.json"
        race_path.write_text(
            json.dumps(bundle, ensure_ascii=False),
            encoding="utf-8",
        )

        import hashlib

        raw = race_path.read_bytes()
        manifest = {
            "schema_version": "0.1",
            "manifest_kind": "jrdb_pwa_newspaper_daily_manifest",
            "date": "2026-09-26",
            "revision": 1,
            "generated_at": "2026-09-25T12:00:00+00:00",
            "source_status": bundle["metadata"]["source_status"],
            "completeness": {"expected_races": 1, "ready_races": 1},
            "races": [
                {
                    "race_key": "09264601",
                    "venue_code": "09",
                    "venue": "阪神",
                    "race_no": 1,
                    "path": "races/09_01_09264601.json",
                    "revision": 1,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "size_bytes": len(raw),
                    "horse_count": 1,
                }
            ],
        }
        (day / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        return day

    def _write_prediction_csv(self, root: Path) -> Path:
        path = root / "momotaro.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "date",
                    "venue_code",
                    "race_no",
                    "horse_no",
                    "horse_name",
                    "member",
                    "mark",
                    "confidence",
                    "review_horse",
                    "comment",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "date": "2026-09-26",
                    "venue_code": "09",
                    "race_no": 1,
                    "horse_no": 1,
                    "horse_name": "テストホース",
                    "member": "りょーた",
                    "mark": "◎",
                    "confidence": "S",
                    "review_horse": "",
                    "comment": "本命短評",
                }
            )
            writer.writerow(
                {
                    "date": "2026-09-26",
                    "venue_code": "09",
                    "race_no": 1,
                    "horse_no": 1,
                    "horse_name": "テストホース",
                    "member": "おーじ",
                    "mark": "○",
                    "confidence": "",
                    "review_horse": "1",
                    "comment": "回顧馬短評",
                }
            )
            writer.writerow(
                {
                    "date": "2026-09-26",
                    "venue_code": "09",
                    "race_no": 1,
                    "horse_no": 1,
                    "horse_name": "テストホース",
                    "member": "けんしょー",
                    "mark": "▲",
                    "confidence": "",
                    "review_horse": "",
                    "comment": "けんしょー短評",
                }
            )
        return path

    def test_projection_strips_private_addons_and_keeps_shared_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._write_source_day(root)
            predictions = self._write_prediction_csv(root)
            output = root / "output"

            result = MODULE.build_projection(
                source,
                output,
                momotaro_csv=predictions,
            )

            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["momotaro_rows"], 3)

            projected = json.loads(
                (output / "races" / "09_01_09264601.json").read_text(
                    encoding="utf-8"
                )
            )
            horse = projected["horses"][0]
            addons = horse["addons"]

            self.assertEqual(
                set(addons),
                {"keibailuka", "momotaro"},
            )
            self.assertEqual(
                set(addons["momotaro"]),
                {"ryota", "oji", "kenshow"},
            )
            self.assertEqual(
                addons["keibailuka"]["comment"],
                "イルカコメント",
            )
            self.assertEqual(
                addons["momotaro"]["ryota"]["confidence"],
                "S",
            )
            self.assertTrue(
                addons["momotaro"]["oji"]["review_horse"]
            )
            self.assertEqual(horse["edge_matches"], [])
            self.assertNotIn(
                "racenote_short_comment",
                projected["race_notes"],
            )

            source_status = projected["metadata"]["source_status"]
            self.assertEqual(
                set(source_status),
                {
                    "jrdb_base",
                    "jrdb_history",
                    "keibailuka",
                    "momotaro",
                },
            )

            audit = json.loads(
                (output / "audit.json").read_text(encoding="utf-8")
            )
            self.assertTrue(
                audit["privacy"]["private_addons_removed"]
            )
            self.assertTrue(
                audit["privacy"]["edge_matches_removed"]
            )


if __name__ == "__main__":
    unittest.main()
