#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jrdb_result_query import ResultQueryError
from jrdb_result_query_runner import (
    build_materialization_plan,
    execute_materialized,
    source_archive_names,
)


class ResultQueryRunnerTests(unittest.TestCase):
    def test_current_daily_names(self):
        self.assertEqual(
            source_archive_names(dt.date(2026, 9, 6)),
            {"SED":"SED260906.zip","HJC":"HJC260906.zip"},
        )

    def test_historical_annual_names(self):
        self.assertEqual(
            source_archive_names(dt.date(2024, 9, 29)),
            {"SED":"SED_2024.zip","HJC":"HJC_2024.zip"},
        )

    def test_plan_points_to_native_drive_and_runtime_cache(self):
        plan = build_materialization_plan("2026-09-06")
        self.assertEqual(plan["coverage"], "daily_raw")
        self.assertFalse(plan["web_fallback_allowed_before_drive_check"])
        by = {x["family"]: x for x in plan["files"]}
        self.assertEqual(
            by["SED"]["drive_path"],
            "/Google Drive/GPT/horse-racing/00_raw/SED/SED260906.zip",
        )
        self.assertEqual(
            by["HJC"]["drive_path"],
            "/Google Drive/GPT/horse-racing/00_raw/HJC/HJC260906.zip",
        )
        self.assertTrue(by["SED"]["local_path"].endswith("/20260906/SED260906.zip"))

    def test_missing_materialized_raw_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ResultQueryError) as ctx:
                execute_materialized(
                    date="2026-09-06",
                    venue="阪神",
                    race_no=10,
                    local_root=Path(tmp),
                )
        message = str(ctx.exception)
        self.assertIn("has not been materialized", message)
        self.assertIn("Do not use Web", message)


if __name__ == "__main__":
    unittest.main()
