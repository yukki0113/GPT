#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from audit_jrdb_training_stage2b_parquet_regression import BASELINE, audit


class Stage2bHistoricalRegressionAuditTest(unittest.TestCase):
    def _result(self) -> dict:
        metrics = {"pooled": {}, "yearly": {}}
        for model, expected in BASELINE["pooled"].items():
            metrics["pooled"][model] = {
                "spearman": expected["spearman"],
                "rmse": expected["rmse"],
                "top_minus_bottom": {
                    "mean_delta": expected["top_bottom_mean_spread"],
                },
            }
            metrics["yearly"][model] = {
                year: {"spearman": value}
                for year, value in BASELINE["yearly_spearman"][model].items()
            }
        return {
            "source_audit": {
                "source_table_rows": BASELINE["source_rows"],
                "selected_min_year": BASELINE["source_min_year"],
                "selected_max_year": BASELINE["source_max_year"],
            },
            "population": copy.deepcopy(BASELINE["population"]),
            "holdout_guard": copy.deepcopy(BASELINE["holdout_guard"]),
            "metrics": metrics,
            "incremental_decision": {
                model: {"classification": value}
                for model, value in BASELINE["classification"].items()
            },
            "named_pattern_diagnostics": {},
        }

    def _resolver(self) -> dict:
        return {
            "rows": BASELINE["source_rows"],
            "min_year": BASELINE["source_min_year"],
            "max_year": BASELINE["source_max_year"],
            "duplicate_keys": BASELINE["source_duplicate_keys"],
        }

    @patch(
        "audit_jrdb_training_stage2b_parquet_regression._named_pattern_digest",
        return_value=BASELINE["named_pattern_identity_count_sha256"],
    )
    def test_exact_baseline_passes(self, _digest) -> None:
        report = audit(self._result(), self._resolver())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["failure_count"], 0)

    @patch(
        "audit_jrdb_training_stage2b_parquet_regression._named_pattern_digest",
        return_value=BASELINE["named_pattern_identity_count_sha256"],
    )
    def test_small_numeric_runtime_drift_within_fixed_tolerance_passes(self, _digest) -> None:
        result = self._result()
        result["metrics"]["pooled"]["M1"]["spearman"] += 4e-5
        result["metrics"]["yearly"]["M3"]["2021"]["spearman"] -= 4e-5
        result["metrics"]["pooled"]["M4"]["top_minus_bottom"]["mean_delta"] += 9e-5
        report = audit(result, self._resolver())
        self.assertEqual(report["status"], "PASS")

    @patch(
        "audit_jrdb_training_stage2b_parquet_regression._named_pattern_digest",
        return_value=BASELINE["named_pattern_identity_count_sha256"],
    )
    def test_classification_change_fails_closed(self, _digest) -> None:
        result = self._result()
        result["incremental_decision"]["M1"]["classification"] = "B_AUXILIARY_ONLY"
        report = audit(result, self._resolver())
        self.assertEqual(report["status"], "FAIL")
        names = {item["name"] for item in report["failures"]}
        self.assertIn("M1.classification", names)

    @patch(
        "audit_jrdb_training_stage2b_parquet_regression._named_pattern_digest",
        return_value="0" * 64,
    )
    def test_named_pattern_identity_change_fails_closed(self, _digest) -> None:
        report = audit(self._result(), self._resolver())
        self.assertEqual(report["status"], "FAIL")
        names = {item["name"] for item in report["failures"]}
        self.assertIn("named_pattern_identity_count_sha256", names)


if __name__ == "__main__":
    unittest.main()
