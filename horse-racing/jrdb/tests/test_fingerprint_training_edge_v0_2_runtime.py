#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fingerprint_training_edge_v0_2_runtime import (  # noqa: E402
    _prediction_hash,
    validate_fingerprint,
)


def test_prediction_hash_is_deterministic_after_float12_normalization() -> None:
    import numpy as np

    left = np.asarray([0.12345678901234, -0.5, 1.0], dtype=float)
    right = np.asarray([0.12345678901235, -0.5, 1.0], dtype=float)
    assert _prediction_hash(left) == _prediction_hash(right)


def test_validate_fingerprint_accepts_exact_and_rejects_drift() -> None:
    expected = {
        "core_version": "v",
        "training_period": "2013-2025",
        "training_eligible_n": 10,
        "training_semantic_sha256": "a",
        "prediction_normalization_decimals": 12,
        "c_training_prediction_sha256": "b",
        "cab_training_prediction_sha256": "c",
        "runtime_packages": {"numpy": "1"},
    }
    validate_fingerprint(dict(expected), expected)

    actual = dict(expected)
    actual["training_eligible_n"] = 11
    try:
        validate_fingerprint(actual, expected)
    except ValueError as exc:
        assert "training_eligible_n" in str(exc)
    else:
        raise AssertionError("runtime fingerprint drift must fail closed")
