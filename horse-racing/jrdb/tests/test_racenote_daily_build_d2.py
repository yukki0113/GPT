from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import build_racenote_daily as daily  # noqa: E402


def sample_bundle() -> dict:
    return {
        "schema_version": "1.0",
        "metadata": {
            "generated_at": "2026-09-30T00:00:00Z",
            "history_enrichment": {
                "version": "1.0",
                "analysis_source": {
                    "kind": "PARQUET",
                    "backend": "parquet_duckdb",
                    "path": "/runtime/a",
                    "manifest_path": "/runtime/a/manifest.json",
                    "generation_id": "analysis-test",
                    "min_race_date": "2016-01-01",
                    "max_race_date": "2026-09-27",
                    "rows": 100,
                    "query_count": 8,
                    "parquet_scan_count": 8,
                },
            },
        },
        "race": {
            "date": "2026-05-23",
            "venue": "東京",
            "race_no": 1,
            "surface": "芝",
            "distance_m": 1600,
        },
        "horses": [
            {
                "basic": {"horse_no": 1, "horse_name": "A", "horse_id": "H1"},
                "pedigree": {"sire_name": "父A", "scoring": False},
                "pedigree_context": {"coverage_status": "PARTIAL", "scoring": False},
            }
        ],
    }


class FakeAnalysis:
    source_info = {
        "kind": "PARQUET",
        "backend": "parquet_duckdb",
        "path": "/analysis/current",
        "manifest_path": "/analysis/current/manifest.json",
        "generation_id": "analysis-test",
        "min_race_date": "2016-01-01",
        "max_race_date": "2026-09-27",
        "rows": 100,
    }

    def metrics(self):
        return {"query_count": 12, "parquet_scan_count": 7}


class DailyBuildD2Test(unittest.TestCase):
    def test_migration_hash_ignores_execution_only_metadata(self) -> None:
        left = sample_bundle()
        right = copy.deepcopy(left)
        right["metadata"]["generated_at"] = "2026-09-30T01:02:03Z"
        source = right["metadata"]["history_enrichment"]["analysis_source"]
        source["path"] = "/other/runtime"
        source["manifest_path"] = "/other/runtime/manifest.json"
        source["query_count"] = 999
        source["parquet_scan_count"] = 888

        self.assertEqual(
            daily.evidence_semantic_sha256(left),
            daily.evidence_semantic_sha256(right),
        )

        right["horses"][0]["pedigree"]["sire_name"] = "父B"
        self.assertNotEqual(
            daily.evidence_semantic_sha256(left),
            daily.evidence_semantic_sha256(right),
        )

    def test_history_stage_calls_bulk_enrichment_once(self) -> None:
        bases = [
            {"race": {"venue": "東京", "race_no": 1}, "horses": []},
            {"race": {"venue": "東京", "race_no": 2}, "horses": []},
        ]
        enriched = [
            ({"metadata": {"history_enrichment": {}}, "race": {"venue": "東京", "race_no": 1}, "horses": []}, []),
            ({"metadata": {"history_enrichment": {}}, "race": {"venue": "東京", "race_no": 2}, "horses": []}, ["w"]),
        ]
        with mock.patch.object(
            daily.history,
            "enrich_production_many",
            return_value=enriched,
        ) as bulk:
            got, report = daily.enrich_history_bundles(bases, FakeAnalysis())

        bulk.assert_called_once_with(
            bases,
            mock.ANY,
            daily.history.DEFAULT_STATS_WINDOW_YEARS,
        )
        self.assertEqual(len(got), 2)
        self.assertEqual(report["warning_count"], 1)
        self.assertEqual(
            got[0]["metadata"]["history_enrichment"]["analysis_source"]["generation_id"],
            "analysis-test",
        )
        self.assertEqual(
            got[0]["metadata"]["history_enrichment"]["analysis_source"]["query_count"],
            12,
        )

    def test_base_stage_parses_paci_once(self) -> None:
        parsed = {
            "BAC": [
                {"date_raw": "260523", "race_key_raw": "R1"},
                {"date_raw": "260523", "race_key_raw": "R2"},
            ],
            "KYI": [
                {"race_key_raw": "R1"},
                {"race_key_raw": "R2"},
            ],
            "CHA": [],
            "CYB": [],
            "ZED": [],
            "ZKB": [],
        }

        class FakeAudit:
            def __init__(self):
                from collections import Counter
                self.bundle_errors = []
                self.warnings = Counter()
                self.target_result_contamination = 0

        class FakeBuilder:
            def __init__(self, _parsed, _audit):
                pass

            def build(self, bac, horses):
                race_no = 1 if bac["race_key_raw"] == "R1" else 2
                return {
                    "schema_version": "0.2",
                    "metadata": {},
                    "race": {
                        "date": "2026-05-23",
                        "venue": "東京",
                        "race_no": race_no,
                    },
                    "horses": [{"basic": {"horse_no": 1}} for _ in horses],
                }

        with tempfile.TemporaryDirectory() as tmp:
            paci = Path(tmp) / "PACI260523.zip"
            paci.write_bytes(b"x")
            with (
                mock.patch.object(daily.jrdb, "Audit", FakeAudit),
                mock.patch.object(daily.jrdb, "parse_zip", return_value=parsed) as parse_zip,
                mock.patch.object(daily.jrdb, "ymd", return_value="2026-05-23"),
                mock.patch.object(daily.jrdb, "BundleBuilder", FakeBuilder),
                mock.patch.object(
                    daily.jrdb,
                    "race_key_parts",
                    side_effect=[
                        {"venue_code": "05", "race_no": 1},
                        {"venue_code": "05", "race_no": 2},
                    ],
                ),
                mock.patch.object(daily.jrdb, "decode", return_value="東京"),
            ):
                bundles, report = daily.build_base_bundles(
                    paci,
                    "2026-05-23",
                )

        parse_zip.assert_called_once_with(paci, mock.ANY)
        self.assertEqual(len(bundles), 2)
        self.assertEqual(report["race_count"], 2)
        self.assertEqual(report["horse_count"], 2)

    def test_build_through_history_opens_analysis_once(self) -> None:
        bases = [
            {
                "metadata": {},
                "race": {"date": "2026-05-23", "venue": "東京", "race_no": 1},
                "horses": [],
            }
        ]
        fake_analysis = mock.Mock()
        fake_analysis.close = mock.Mock()
        enriched = [sample_bundle()]

        with (
            mock.patch.object(
                daily,
                "build_base_bundles",
                return_value=(bases, {"race_count": 1, "horse_count": 0}),
            ),
            mock.patch.object(
                daily,
                "open_analysis_backend",
                return_value=fake_analysis,
            ) as opener,
            mock.patch.object(
                daily,
                "enrich_history_bundles",
                return_value=(
                    enriched,
                    {"race_count": 1, "horse_count": 1, "warning_count": 0},
                ),
            ),
        ):
            got, report = daily.build_through_history(
                paci_path=Path("PACI260523.zip"),
                target_date="2026-05-23",
                analysis_root=Path("analysis"),
            )

        opener.assert_called_once_with(
            analysis_root=Path("analysis"),
            backend="parquet",
        )
        fake_analysis.close.assert_called_once()
        self.assertEqual(got, enriched)
        self.assertEqual(report["status"], "D2_PASS")
        self.assertEqual(report["stages"]["base"], "PASS")
        self.assertEqual(report["stages"]["history"], "PASS")
        self.assertEqual(report["stages"]["rrdb"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
