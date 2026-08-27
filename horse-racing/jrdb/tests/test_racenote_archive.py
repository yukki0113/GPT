#!/usr/bin/env python3
"""Regression tests for RaceNote Archive storage semantics."""
from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import build_racenote_archive as builder  # noqa: E402
import racenote_archive as archive  # noqa: E402
import read_racenote_archive as reader  # noqa: E402

SCHEMA = PROJECT_ROOT / "schema" / "racenote_archive_schema_v1_0.sql"


def base_bundle(
    race_date: str = "2025-08-24",
    venue: str = "新潟",
    race_no: int = 11,
    generated_at: str = "2026-08-27T00:00:00+00:00",
    recent_date: str = "2025-08-01",
) -> dict:
    """Return the smallest realistic base v0.2 bundle needed by Archive tests."""
    return {
        "schema_version": "0.2",
        "metadata": {
            "generated_at": generated_at,
            "data_phase": "pre_race",
        },
        "race": {
            "date": race_date,
            "venue": venue,
            "race_no": race_no,
            "field_size": 1,
        },
        "horses": [
            {
                "basic": {"horse_no": 1},
                "recent_runs": [
                    {
                        "race": {
                            "date": recent_date,
                            "venue": venue,
                            "race_no": 1,
                        }
                    }
                ],
            }
        ],
    }


def write_bundle(path: Path, value: dict) -> bytes:
    """Write formatted JSON exactly as a converter-like artifact."""
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


class RaceNoteArchiveTest(unittest.TestCase):
    """Archive hash, build, lookup and leakage regression tests."""

    def test_semantic_hash_ignores_only_generated_at(self) -> None:
        first = base_bundle(generated_at="2026-08-27T00:00:00+00:00")
        second = base_bundle(generated_at="2026-08-27T12:34:56+00:00")
        self.assertEqual(
            archive.semantic_sha256(first),
            archive.semantic_sha256(second),
        )

        changed = copy.deepcopy(second)
        changed["race"]["race_no"] = 12
        self.assertNotEqual(
            archive.semantic_sha256(first),
            archive.semantic_sha256(changed),
        )

    def test_future_recent_run_is_rejected(self) -> None:
        value = base_bundle(recent_date="2025-08-24")
        with self.assertRaises(archive.RaceNoteArchiveError):
            archive.validate_base_bundle(value)

    def test_provenance_labels_reject_urls_paths_and_external_ids(self) -> None:
        self.assertEqual(builder.validate_source_ref("paci-202605"), "paci-202605")
        self.assertEqual(builder.validate_source_ref("annual-raw-2025"), "annual-raw-2025")
        self.assertIsNone(builder.validate_source_ref(None))
        self.assertIsNone(builder.validate_source_ref("   "))

        invalid_refs = (
            "https://drive.google.com/file/d/example",
            "drive.google.com-file",
            "folder/source",
            "C:\\source\\file",
            "label with spaces",
        )
        for value in invalid_refs:
            with self.subTest(value=value):
                with self.assertRaises(builder.BuildError):
                    builder.validate_source_ref(value)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "sources.json"
            manifest.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "source_type": "PACI",
                                "source_period": "202605",
                                "filename": "folder/PACI260509.zip",
                                "sha256": "0" * 64,
                                "role": "base",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaises(builder.BuildError):
                builder.source_inputs_from_manifest(manifest)

    def test_build_lookup_and_reader_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_dir = root / "bundles"
            output = root / "jrdb_racenote_archive_202508_v1_0.sqlite"
            report_path = root / "validation.json"
            restored = root / "restored"

            first_path = bundle_dir / "race_bundle_20250824_新潟11R.json"
            second_path = bundle_dir / "race_bundle_20250824_新潟12R.json"
            other_path = bundle_dir / "race_bundle_20250906_札幌1R.json"
            first_bytes = write_bundle(first_path, base_bundle(race_no=11))
            second_bytes = write_bundle(second_path, base_bundle(race_no=12))
            write_bundle(
                other_path,
                base_bundle(
                    race_date="2025-09-06",
                    venue="札幌",
                    race_no=1,
                    recent_date="2025-08-30",
                ),
            )

            source_manifest = root / "sources.json"
            source_manifest.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "source_type": "ANNUAL_RAW",
                                "source_period": "2025",
                                "filename": "BAC_2025.zip",
                                "sha256": "0" * 64,
                                "role": "target_race_base",
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            build_args = argparse.Namespace(
                bundle_dir=bundle_dir,
                target_month="202508",
                output=output,
                source_mode="annual_raw_reconstruction",
                source_ref="synthetic-2025",
                source_manifest=source_manifest,
                converter_git_sha="1234567",
                schema=SCHEMA,
                expected_race_count=2,
                replace=False,
                strict_input_month=False,
                validation_report=report_path,
            )
            build_report = builder.build(build_args)
            self.assertEqual(build_report["status"], "PASS")
            self.assertEqual(build_report["selected_bundle_count"], 2)
            self.assertEqual(build_report["skipped_other_month_count"], 1)
            self.assertTrue(build_report["publishable"])
            self.assertEqual(build_report["verified_bundle_count"], 2)
            self.assertEqual(build_report["source_ref"], "synthetic-2025")

            connection = archive.open_archive(output)
            try:
                validation = archive.validate_archive(connection, full_scan=True)
                self.assertEqual(validation["status"], "PASS")
                all_bundles = archive.lookup(connection, "2025-08-24")
                self.assertEqual(len(all_bundles), 2)
                race_bundle = archive.lookup(
                    connection,
                    "2025-08-24",
                    venue_code="04",
                    race_no=11,
                )
                self.assertEqual(len(race_bundle), 1)
                self.assertEqual(race_bundle[0].json_bytes, first_bytes)
            finally:
                connection.close()

            read_args = argparse.Namespace(
                archive=output,
                date="20250824",
                venue="新潟",
                race=None,
                output_dir=restored,
                full_validate=True,
            )
            read_report = reader.read(read_args)
            self.assertEqual(read_report["status"], "PASS")
            self.assertEqual(read_report["bundle_count"], 2)
            self.assertEqual(
                (restored / "race_bundle_20250824_新潟11R.json").read_bytes(),
                first_bytes,
            )
            self.assertEqual(
                (restored / "race_bundle_20250824_新潟12R.json").read_bytes(),
                second_bytes,
            )

    def test_reader_rejects_wrong_month_shard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_dir = root / "bundles"
            output = root / "jrdb_racenote_archive_202508_v1_0.sqlite"
            write_bundle(
                bundle_dir / "race_bundle_20250824_新潟11R.json",
                base_bundle(),
            )
            build_args = argparse.Namespace(
                bundle_dir=bundle_dir,
                target_month="202508",
                output=output,
                source_mode="annual_raw_reconstruction",
                source_ref=None,
                source_manifest=None,
                converter_git_sha="1234567",
                schema=SCHEMA,
                expected_race_count=1,
                replace=False,
                strict_input_month=False,
                validation_report=root / "validation.json",
            )
            builder.build(build_args)

            read_args = argparse.Namespace(
                archive=output,
                date="20250906",
                venue=None,
                race=None,
                output_dir=root / "restored",
                full_validate=False,
            )
            with self.assertRaises(archive.RaceNoteArchiveError):
                reader.read(read_args)


if __name__ == "__main__":
    unittest.main()
