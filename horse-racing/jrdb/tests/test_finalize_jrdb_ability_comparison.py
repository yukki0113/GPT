"""Tests for fail-closed Ability comparison result finalization."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
MODULE_PATH = SRC / "finalize_jrdb_ability_comparison.py"


def _load_module():
    """Load the finalizer directly from its repository path."""
    spec = importlib.util.spec_from_file_location("ability_finalizer", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidate(name: str, values: list[float]) -> dict:
    """Build a compact 2013-2023 candidate fixture."""
    annual = []
    for offset, value in enumerate(values):
        annual.append({"year": 2013 + offset, "primary": value, "row_count": 10, "race_count": 2})
    return {
        "candidate": name,
        "mean_primary": sum(values) / len(values),
        "primary_sd": 0.0,
        "annual": annual,
        "row_count": 110,
        "race_count": 22,
    }


def test_nonfinite_candidate_is_invalid_and_cannot_rank_first() -> None:
    """A non-finite annual fold must fail closed instead of entering top candidates."""
    module = _load_module()
    development_years = list(range(2013, 2024))
    invalid_values = [0.60] * 11
    invalid_values[4] = float("nan")

    report = {
        "status": "PASS",
        "development_years": development_years,
        "holdout_touched": False,
        "2024_2025_predictive_metrics_inspected": False,
        "a0": [_candidate("A0_D070", [0.47] * 11)],
        "ridge": [_candidate("Ridge:valid", [0.48] * 11)],
        "elastic_net": [
            _candidate("ElasticNet:invalid", invalid_values),
            _candidate("ElasticNet:valid", [0.49] * 11),
        ],
    }

    finalized = module.finalize(report)

    assert finalized["status"] == "PASS"
    assert finalized["candidate_validity"]["elastic_net"] == {"total": 2, "valid": 1, "invalid": 1}
    assert finalized["best_elastic_net"]["candidate"] == "ElasticNet:valid"
    assert finalized["elastic_net"][-1]["candidate"] == "ElasticNet:invalid"
    assert finalized["elastic_net"][-1]["selection_status"] == "INVALID_NONFINITE_ANNUAL_PRIMARY"
    assert finalized["elastic_net"][-1]["mean_primary"] is None
    assert all(candidate["candidate"] != "ElasticNet:invalid" for candidate in finalized["top_candidates"])


def test_finite_candidate_metrics_are_recomputed_from_all_eleven_years() -> None:
    """Finalization preserves the equal-year metric contract for valid candidates."""
    module = _load_module()
    values = [0.40 + index * 0.01 for index in range(11)]
    candidate = _candidate("A0_D070", values)
    candidate["mean_primary"] = 999.0

    report = {
        "status": "PASS",
        "development_years": list(range(2013, 2024)),
        "holdout_touched": False,
        "2024_2025_predictive_metrics_inspected": False,
        "a0": [candidate],
        "ridge": [_candidate("Ridge:valid", [0.48] * 11)],
        "elastic_net": [_candidate("ElasticNet:valid", [0.49] * 11)],
    }

    finalized = module.finalize(report)

    assert abs(finalized["best_a0"]["mean_primary"] - 0.45) < 1e-12
    assert finalized["best_a0"]["selection_status"] == "VALID"
    assert len(finalized["paired_vs_best_a0"]) == 2
