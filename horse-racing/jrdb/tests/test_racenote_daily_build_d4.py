#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import build_racenote_daily as daily


def bundle(race_no: int, horse_name: str = "A") -> dict:
    return {
        "schema_version": "1.0",
        "metadata": {
            "generated_at": "2026-09-30T00:00:00Z",
            "history_enrichment": {},
        },
        "race": {
            "date": "2026-05-23",
            "venue": "東京",
            "race_no": race_no,
            "race_key": f"05261{race_no:02d}",
        },
        "horses": [
            {
                "horse_no": 1,
                "basic": {"horse_name": horse_name},
                "racereview": {
                    "history": [
                        {"race_date": "2026-05-01", "review": "ok"}
                    ]
                },
            }
        ],
    }


def report() -> dict:
    return {
        "base": {
            "target_date": "2026-05-23",
            "date_raw": "20260523",
            "race_count": 1,
            "target_result_contamination": 0,
            "record_counts": {"BAC": 1, "KYI": 1},
            "warnings": [],
        },
        "history": {
            "warnings": [],
            "analysis_source": {
                "backend": "parquet",
                "generation_id": "analysis-test",
            },
        },
        "rrdb": {
            "rrdb_source": {
                "mode": "generation_root",
                "generation_id": "rrdb-test",
            },
            "rrdb_generation_id": "rrdb-test",
            "next_watch_rule_version": "rules-test",
        },
        "stages": {
            "base": "PASS",
            "history": "PASS",
            "rrdb": "PASS",
            "reader": "NOT_RUN",
            "validation": "NOT_RUN",
            "package": "NOT_RUN",
        },
    }


class DailyBuildD4Test(unittest.TestCase):
    def test_reader_view_roundtrip_and_package(self) -> None:
        bundles = [bundle(1)]
        views, reader_report = daily.build_reader_views(bundles)
        self.assertEqual(reader_report["roundtrip_validation"], "PASS")
        self.assertEqual(len(views), 1)

        rep = report()
        rep["reader"] = reader_report
        validation = daily.validate_daily_bundles(
            bundles, views, rep, "2026-05-23"
        )
        self.assertEqual(validation["status"], "PASS")
        self.assertFalse(validation["firewall"]["target_result_exposed"])
        self.assertEqual(validation["firewall"]["rrdb_as_of_violations"], 0)

        with tempfile.TemporaryDirectory() as tmp:
            packaged = daily.write_daily_package(
                bundles=bundles,
                views=views,
                report=rep,
                validation=validation,
                target_date="2026-05-23",
                output_root=Path(tmp),
            )
            manifest_path = Path(packaged["manifest"])
            validation_path = Path(packaged["validation_report"])
            self.assertTrue(manifest_path.is_file())
            self.assertTrue(validation_path.is_file())
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["counts"]["races_built"], 1)
            self.assertEqual(payload["counts"]["reader_views"], 1)
            self.assertEqual(payload["stages"]["package"], "PASS")

    def test_rrdb_future_row_fails_validation(self) -> None:
        bundles = [bundle(1)]
        bundles[0]["horses"][0]["racereview"]["history"].append(
            {"race_date": "2026-05-23", "review": "leak"}
        )
        views, _ = daily.build_reader_views(bundles)
        validation = daily.validate_daily_bundles(
            bundles, views, report(), "2026-05-23"
        )
        self.assertEqual(validation["status"], "FAIL")
        self.assertEqual(validation["firewall"]["rrdb_as_of_violations"], 1)

    def test_target_result_contamination_fails_validation(self) -> None:
        bundles = [bundle(1)]
        views, _ = daily.build_reader_views(bundles)
        rep = report()
        rep["base"]["target_result_contamination"] = 1
        validation = daily.validate_daily_bundles(
            bundles, views, rep, "2026-05-23"
        )
        self.assertEqual(validation["status"], "FAIL")
        self.assertTrue(validation["firewall"]["target_result_exposed"])


if __name__ == "__main__":
    unittest.main()
