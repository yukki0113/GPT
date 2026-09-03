"""Regression test for the frozen Existing-Horse Ability feature metadata contract."""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from build_jrdb_official_existing_ability import _complete_feature_names
from compare_jrdb_ability_models import _feature_vector


def test_frozen_feature_vector_has_one_name_per_numeric_column() -> None:
    """The already-frozen 22-column model matrix must be fully self-describing."""
    row = {
        "recent_perf_d070": 0.30,
        "peak_best1_last5": 0.50,
        "peak_best2_mean_last5": 0.45,
        "performance_mad_last5": 0.08,
        "surface_fit_delta_raw": 0.02,
        "surface_fit_neff": 2.0,
        "distance_d200_delta_raw": 0.03,
        "distance_d200_neff": 2.0,
        "course_exact_delta_raw": 0.01,
        "course_exact_neff": 1.0,
        "jockey_residual_mean_raw": 0.02,
        "jockey_residual_n": 4,
        "weight_relative": 0.0,
        "career_scored_run_count": 3,
    }

    values, legacy_names = _feature_vector(row, "070", 200, 0, 0)
    names = _complete_feature_names(values, legacy_names)

    assert len(values) == 22
    assert len(names) == len(values)
    assert names[-1] == "log1p_career_missing"
    assert values[-1] == 0.0
