"""Tests for the frozen existing-horse Ability 2024-2025 evaluator."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
MODULE_PATH = SRC / "evaluate_jrdb_ability_holdout.py"


def _load_module():
    """Load the holdout evaluator from its repository path."""
    spec = importlib.util.spec_from_file_location("ability_holdout", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows() -> list[dict]:
    """Create deterministic multi-year rows with finite frozen A1 features."""
    rows: list[dict] = []
    for year in range(2010, 2026):
        for race_index in range(4):
            race_key = f"{year}-R{race_index}"
            for horse_index in range(5):
                recent = 0.30 + horse_index * 0.05 + race_index * 0.01 + (year - 2010) * 0.001
                surface = (horse_index - 2) * 0.01
                weight = (horse_index - 2) * 0.5
                target = 0.35 + 0.60 * recent + 0.20 * surface - 0.002 * weight
                rows.append(
                    {
                        "year": year,
                        "race_key": race_key,
                        "official_runperf_raw": target,
                        "recent_perf_d070": recent,
                        "peak_best1_last5": recent + 0.05,
                        "peak_best2_mean_last5": recent + 0.03,
                        "performance_mad_last5": 0.02 + horse_index * 0.001,
                        "surface_fit_delta_raw": surface,
                        "surface_fit_neff": 3.0 + horse_index,
                        "distance_d200_delta_raw": 0.005 * (horse_index - 2),
                        "distance_d200_neff": 2.0 + horse_index,
                        "course_exact_delta_raw": 0.003 * (race_index - 1),
                        "course_exact_neff": 1.0 + race_index,
                        "jockey_residual_mean_raw": 0.002 * horse_index,
                        "jockey_residual_n": 10 + horse_index,
                        "weight_relative": weight,
                        "career_scored_run_count": 1 + horse_index,
                    }
                )
    return rows


def test_frozen_holdout_year_uses_only_prior_training_years() -> None:
    """The 2024 fit must stop at 2023 and retain all eligible test rows."""
    module = _load_module()
    result = module._evaluate_year(_rows(), 2024)

    assert result["year"] == 2024
    assert result["train_year_max"] == 2023
    assert result["test_row_count"] == 20
    assert result["a1_predicted_row_count"] == result["test_row_count"]
    assert result["a1_prediction_coverage"] == 1.0
    assert result["paired_row_count"] == result["test_row_count"]
    assert result["a1"]["primary"] is not None
    assert result["a0_d070"]["primary"] is not None


def test_confirmation_hyperparameters_are_frozen() -> None:
    """The evaluator constants must match the pre-holdout decision record."""
    module = _load_module()

    assert module.HOLDOUT_YEARS == (2024, 2025)
    assert module.RECENT == "070"
    assert module.BANDWIDTH == 200
    assert module.APTITUDE_K == 0
    assert module.JOCKEY_K == 0
    assert module.ELASTIC_ALPHA == 0.01
    assert module.ELASTIC_L1_RATIO == 0.5
    assert module.RIDGE_ALPHA == 10.0
