from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "evaluate_jrdb_runperf_holdout.py"
SPEC = importlib.util.spec_from_file_location("evaluate_jrdb_runperf_holdout", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("failed to load holdout evaluator module")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _row(year: int, delta: float, coverage: float = 0.966) -> dict[str, Any]:
    """Build one compact synthetic holdout row for classification tests."""
    return {
        "year": year,
        "delta_primary_vs_B1": delta,
        "selected": {"coverage": coverage},
        "coefficient_snapshot": {
            "coefficients": {
                "time_raw_bias": 0.025,
                "prev_margin_score": 0.097,
            }
        },
    }


def test_specification_is_frozen() -> None:
    assert MODULE.SELECTED_CANDIDATE == "T1|EXPANDING|RAW"
    assert MODULE.BASELINE_METHOD == "EXPANDING"
    assert MODULE.SELECTED_FEATURES == ("time_raw_bias", "prev_margin_score")
    assert MODULE.HOLDOUT_YEARS == (2024, 2025)
    assert MODULE.MIN_COVERAGE == 0.95


def test_classify_pass_strong() -> None:
    classification, reasons = MODULE._classify([
        _row(2024, 0.008),
        _row(2025, 0.004),
    ])
    assert classification == "PASS_STRONG"
    assert reasons


def test_classify_pass_mixed() -> None:
    classification, reasons = MODULE._classify([
        _row(2024, 0.008),
        _row(2025, -0.002),
    ])
    assert classification == "PASS_MIXED"
    assert reasons


def test_classify_fail_when_mean_nonpositive() -> None:
    classification, reasons = MODULE._classify([
        _row(2024, 0.002),
        _row(2025, -0.004),
    ])
    assert classification == "FAIL"
    assert any("mean holdout primary delta" in reason for reason in reasons)


def test_classify_fail_when_coverage_breaks_gate() -> None:
    classification, reasons = MODULE._classify([
        _row(2024, 0.008, coverage=0.949),
        _row(2025, 0.006),
    ])
    assert classification == "FAIL"
    assert any("coverage" in reason for reason in reasons)


def test_classify_fail_when_coefficient_sign_breaks() -> None:
    row_2024 = _row(2024, 0.008)
    row_2025 = _row(2025, 0.006)
    row_2025["coefficient_snapshot"]["coefficients"]["time_raw_bias"] = -0.001
    classification, reasons = MODULE._classify([row_2024, row_2025])
    assert classification == "FAIL"
    assert any("coefficients" in reason for reason in reasons)
