#!/usr/bin/env python3
"""Regression tests for the predeclared RunPerf comparison reviewer."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

SRC_DIR: Path = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from review_jrdb_runperf_comparison import review  # noqa: E402


def _candidate(
    name: str,
    family: str,
    values: list[float],
    coverage: float = 0.96,
    coefficients: list[float] | None = None,
) -> dict[str, Any]:
    yearly = [
        {
            "year": 2013 + index,
            "primary_rank_score": value,
        }
        for index, value in enumerate(values)
    ]
    coefficient_history: list[dict[str, Any]] = []
    if coefficients is not None:
        coefficient_history = [
            {
                "test_year": 2013 + index,
                "coefficients": {"time_raw_bias": value},
            }
            for index, value in enumerate(coefficients)
        ]
    return {
        "candidate": name,
        "family": family,
        "baseline_method": "EXPANDING" if family.startswith("T") else None,
        "time_variant": "RAW" if family.startswith("T") else None,
        "development_year_count": len(values),
        "positive_primary_year_count": sum(1 for value in values if value > 0.0),
        "mean_primary_rank_score": sum(values) / len(values),
        "std_primary_rank_score": 0.01,
        "mean_same_condition_rank_score": sum(values) / len(values) - 0.02,
        "mean_top_pick_win_rate": 0.2,
        "mean_top_pick_top3_rate": 0.45,
        "mean_coverage": coverage,
        "yearly": yearly,
        "coefficient_history": coefficient_history,
    }


class RunPerfReviewerTest(unittest.TestCase):
    """Protect eligibility and holdout rules before real development review."""

    def _comparison(self) -> dict[str, Any]:
        return {
            "status": "PASS",
            "protocol": {
                "holdout_touched": False,
                "locked_holdout_years": [2024, 2025],
            },
            "all_candidates": [
                _candidate("T1|EXPANDING|RAW", "T1", [0.41, 0.42], coefficients=[0.02, 0.03]),
                _candidate("T3|EXPANDING|RAW", "T3", [0.50, 0.51], coefficients=[0.04, 0.05]),
                _candidate("B1", "B1", [0.40, 0.39], coverage=0.99),
                _candidate("B0", "B0", [0.38, 0.37], coverage=0.99),
                _candidate("J1", "J1", [0.45, 0.44]),
                _candidate("J0", "J0", [0.35, 0.34]),
            ],
        }

    def test_conditional_and_jrdb_winners_do_not_displace_independent_core(self) -> None:
        """T3/J1 may score higher but cannot silently become the independent RunPerf core."""
        report = review(self._comparison())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["best_independent_candidate"]["family"], "T1")
        self.assertEqual(report["best_conditional_diagnostic"]["family"], "T3")
        self.assertEqual(report["best_jrdb_benchmark"]["family"], "J1")
        paired = report["paired_primary_differences"]["best_vs_B1"]
        self.assertEqual(paired["positive_year_count"], 2)
        stability = report["best_candidate_coefficient_stability"]["time_raw_bias"]
        self.assertEqual(stability["adjacent_sign_flip_count"], 0)
        self.assertEqual(stability["positive_count"], 2)

    def test_holdout_touch_is_rejected(self) -> None:
        """Reviewer must fail closed if comparison metadata says holdout was touched."""
        comparison = self._comparison()
        comparison["protocol"]["holdout_touched"] = True
        with self.assertRaises(ValueError):
            review(comparison)


if __name__ == "__main__":
    unittest.main()
