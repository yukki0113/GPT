#!/usr/bin/env python3
"""Regression tests for RaceNote request routing through Archive."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import racenote_archive as archive  # noqa: E402
import racenote_request as router  # noqa: E402

SCHEMA = PROJECT_ROOT / "schema" / "racenote_archive_schema_v1_0.sql"


def bundle_bytes() -> bytes:
    """Return one valid synthetic pre-race base v0.2 bundle."""
    value = {
        "schema_version": "0.2",
        "metadata": {
            "generated_at": "2026-08-28T00:00:00+00:00",
            "data_phase": "pre_race",
        },
        "race": {
            "date": "2025-08-24",
            "venue": "新潟",
            "race_no": 11,
            "field_size": 1,
        },
        "horses": [
            {
                "basic": {"horse_no": 1},
                "recent_runs": [
                    {
                        "race": {
                            "date": "2025-08-01",
                            "venue": "新潟",
                            "race_no": 1,
                        }
                    }
                ],
            }
        ],
    }
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def create_archive(
    path: Path,
    *,
    target_month: str = "202508",
    coverage_mode: str = "full_month",
    publication_status: str = "publishable",
) -> None:
    """Create the minimum verified shard needed by the request router."""
    connection = sqlite3.connect(path)
    try:
        archive.create_schema(connection, SCHEMA)
        archive.set_meta(connection, "archive_schema_version", archive.ARCHIVE_SCHEMA_VERSION)
        archive.set_meta(connection, "base_schema_version", archive.BASE_SCHEMA_VERSION)
        archive.set_meta(connection, "target_month", target_month)
        archive.set_meta(connection, "compression", archive.COMPRESSION)
        archive.set_meta(connection, "semantic_hash_rule", archive.SEMANTIC_HASH_RULE)
        archive.set_meta(connection, "coverage_mode", coverage_mode)
        archive.set_meta(connection, "publication_status", publication_status)
        archive.set_meta(connection, "converter_git_sha", "1234567")
        archive.set_meta(connection, "provenance_status", "complete")
        archive.insert_bundle(
            connection,
            bundle_bytes(),
            source_mode="annual_raw_reconstruction",
            source_ref="synthetic-202508",
        )
        connection.commit()
    finally:
        connection.close()


class RaceNoteRequestArchiveTest(unittest.TestCase):
    """Archive preferred routing must remain safe and reversible."""

    def setUp(self) -> None:
        """Create the canonical historical request used by tests."""
        self.request = router.RaceNoteRequest(
            target_date=date(2025, 8, 24),
            venue="新潟",
            race_no=11,
            today=date(2026, 8, 28),
        )

    def test_publishable_full_month_archive_is_used(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shard = root / "jrdb_racenote_archive_202508_v1_0.sqlite"
            create_archive(shard)

            base_dir, resolution = router.try_archive_base(
                shard,
                self.request,
                root / "restored",
            )
            self.assertIsNotNone(base_dir)
            self.assertEqual(resolution["status"], "used")
            self.assertEqual(resolution["used_backend"], "racenote_archive")
            self.assertEqual(resolution["coverage_mode"], "full_month")
            self.assertEqual(resolution["publication_status"], "publishable")
            self.assertTrue(
                (base_dir / "race_bundle_20250824_新潟11R.json").is_file()
            )

    def test_partial_archive_returns_fallback_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shard = root / "jrdb_racenote_archive_202508_v1_0.sqlite"
            create_archive(
                shard,
                coverage_mode="partial",
                publication_status="test_only",
            )

            base_dir, resolution = router.try_archive_base(
                shard,
                self.request,
                root / "restored",
            )
            self.assertIsNone(base_dir)
            self.assertEqual(resolution["status"], "fallback")
            self.assertEqual(resolution["reason"], "archive_rejected")
            self.assertIn("not publishable", resolution["detail"])

    def test_wrong_month_archive_returns_fallback_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shard = root / "jrdb_racenote_archive_202507_v1_0.sqlite"
            create_archive(shard, target_month="202507")

            base_dir, resolution = router.try_archive_base(
                shard,
                self.request,
                root / "restored",
            )
            self.assertIsNone(base_dir)
            self.assertEqual(resolution["status"], "fallback")
            self.assertEqual(resolution["reason"], "archive_rejected")
            self.assertIn("target month mismatch", resolution["detail"])

    def test_current_request_skips_archive(self) -> None:
        current_request = router.RaceNoteRequest(
            target_date=date(2026, 8, 28),
            venue="新潟",
            race_no=11,
            today=date(2026, 8, 28),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shard = root / "unused.sqlite"
            base_dir, resolution = router.try_archive_base(
                shard,
                current_request,
                root / "restored",
            )
            self.assertIsNone(base_dir)
            self.assertFalse(resolution["attempted"])
            self.assertEqual(resolution["status"], "skipped_non_past")


if __name__ == "__main__":
    unittest.main()
