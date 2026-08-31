#!/usr/bin/env python3
"""Regression tests for fitted RunPerf as-of coefficient snapshots."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SRC_DIR: Path = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from fit_jrdb_runperf_coefficient_snapshot import fit_snapshot  # noqa: E402


class RunPerfSnapshotFitterTest(unittest.TestCase):
    """Ensure target-year outcomes are not needed to freeze the next snapshot."""

    def _build_database(self, path: Path) -> None:
        connection = sqlite3.connect(path)
        try:
            connection.executescript(
                """
                CREATE TABLE race_runperf_observation(
                  race_key TEXT PRIMARY KEY,
                  race_date TEXT,
                  year INTEGER,
                  surface_code TEXT,
                  distance_m INTEGER
                );
                CREATE TABLE runner_runperf_features(
                  baseline_method TEXT,
                  race_key TEXT,
                  horse_no INTEGER,
                  horse_id TEXT,
                  finish_percentile REAL,
                  margin_per_1000m_sec REAL,
                  weight_relative_kg REAL,
                  time_residual_no_bias_sec REAL,
                  time_residual_raw_bias_sec REAL,
                  time_residual_k2_bias_sec REAL,
                  time_residual_k4_bias_sec REAL,
                  time_residual_k8_bias_sec REAL,
                  jrdb_raw_score REAL,
                  jrdb_idm REAL,
                  finish INTEGER
                );
                """
            )
            for year in range(2010, 2014):
                race_key = f"R{year}"
                connection.execute(
                    "INSERT INTO race_runperf_observation VALUES(?,?,?,?,?)",
                    (race_key, f"{year}-01-01", year, "1", 1600),
                )
                for horse_no in range(1, 7):
                    finish = horse_no
                    finish_percentile = (6 - finish) / 5.0
                    margin = (finish - 1) * 0.3
                    time_value = 1.5 - (finish - 1) * 0.2
                    values: tuple[Any, ...] = (
                        "EXPANDING",
                        race_key,
                        horse_no,
                        f"H{horse_no:02d}",
                        finish_percentile,
                        margin,
                        0.0,
                        time_value,
                        time_value,
                        time_value,
                        time_value,
                        time_value,
                        50.0,
                        50.0,
                        finish,
                    )
                    connection.execute(
                        "INSERT INTO runner_runperf_features VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        values,
                    )
            connection.commit()
        finally:
            connection.close()

    def test_2024_snapshot_uses_pairs_only_through_2023(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "runperf.sqlite"
            self._build_database(database_path)
            report = fit_snapshot(
                database_path,
                "T1",
                "EXPANDING",
                "RAW",
                2013,
                2014,
            )
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["target_year"], 2014)
            self.assertEqual(report["coefficient_asof_through_year"], 2013)
            self.assertFalse(report["holdout_outcomes_read"])
            self.assertGreater(report["training_pair_count"], 0)
            self.assertIn("time_raw_bias", report["coefficients"])
            self.assertIn("prev_margin_score", report["coefficients"])

    def test_target_year_must_be_next_year(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "runperf.sqlite"
            self._build_database(database_path)
            with self.assertRaises(ValueError):
                fit_snapshot(
                    database_path,
                    "T1",
                    "EXPANDING",
                    "RAW",
                    2013,
                    2015,
                )


if __name__ == "__main__":
    unittest.main()
