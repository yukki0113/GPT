#!/usr/bin/env python3
"""Regression tests for the RunPerf development comparator."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import numpy as np

SRC_DIR: Path = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from compare_jrdb_runperf_candidates import _rankdata, compare  # noqa: E402


class RunPerfComparatorTest(unittest.TestCase):
    """Protect walk-forward chronology, holdout isolation, and candidate coverage."""

    def _build_synthetic_database(self, path: Path) -> None:
        """Create a small five-year database with stable horse ordering."""
        connection: sqlite3.Connection = sqlite3.connect(path)
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
            for year in range(2010, 2015):
                race_key: str = f"R{year}"
                connection.execute(
                    "INSERT INTO race_runperf_observation VALUES(?,?,?,?,?)",
                    (race_key, f"{year}-01-01", year, "1", 1600),
                )
                for horse_no in range(1, 11):
                    finish: int = horse_no
                    finish_percentile: float = (10 - finish) / 9.0
                    margin: float = (finish - 1) * 0.25
                    weight: float = (11 - horse_no) * 0.2
                    time_value: float = 2.0 - (finish - 1) * 0.15
                    raw_score: float = 60.0 + (10 - finish) * 2.0
                    idm: float = 55.0 + (10 - finish) * 2.2
                    values: tuple[Any, ...] = (
                        "EXPANDING",
                        race_key,
                        horse_no,
                        f"H{horse_no:02d}",
                        finish_percentile,
                        margin,
                        weight,
                        time_value,
                        time_value + 0.10,
                        time_value + 0.05,
                        time_value + 0.02,
                        time_value + 0.01,
                        raw_score,
                        idm,
                        finish,
                    )
                    connection.execute(
                        "INSERT INTO runner_runperf_features VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        values,
                    )
            connection.commit()
        finally:
            connection.close()

    def test_average_rankdata_handles_ties(self) -> None:
        """Tied observations must receive average ranks."""
        values: np.ndarray = np.asarray([10.0, 10.0, 20.0, 30.0], dtype=np.float64)
        ranks: np.ndarray = _rankdata(values)
        np.testing.assert_allclose(ranks, np.asarray([1.5, 1.5, 3.0, 4.0]))

    def test_compare_runs_walk_forward_and_rejects_holdout(self) -> None:
        """Development run must generate 24 candidates for one method and reject 2024."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path: Path = Path(temporary_directory) / "synthetic.sqlite"
            self._build_synthetic_database(database_path)
            report: dict[str, Any] = compare(database_path, 2013, 2014, ["EXPANDING"])

            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["candidate_count"], 24)
            self.assertFalse(report["protocol"]["holdout_touched"])
            self.assertGreater(report["best_by_family"]["B0"]["mean_primary_rank_score"], 0.9)
            self.assertEqual(report["best_by_family"]["T3"]["development_year_count"], 2)
            self.assertGreater(
                report["best_by_family"]["T3"]["mean_primary_rank_score"],
                0.9,
            )

            with self.assertRaises(ValueError):
                compare(database_path, 2013, 2024, ["EXPANDING"])


if __name__ == "__main__":
    unittest.main()
