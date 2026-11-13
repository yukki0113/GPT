"""Regression coverage for the user-facing forecast confirmation threshold."""
import importlib.util
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("forecast_sampling_confirm", BASE / "src" / "sampling.py")
sampling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sampling)
RULES = json.loads((BASE / "config" / "sampling_rules_v1.json").read_text(encoding="utf-8"))


def test_confirmation_threshold_is_five():
    assert RULES["target_races"] == 10
    assert RULES["forecast_confirmation_max_samples"] == 5
    for count in range(0, 6):
        assert sampling.needs_forecast_confirmation({"total_selected": count}, RULES)
    for count in range(6, 11):
        assert not sampling.needs_forecast_confirmation({"total_selected": count}, RULES)


def test_confirmation_threshold_rejects_invalid_counts():
    import pytest
    for count in (-1, True, "5"):
        with pytest.raises(ValueError, match="INVALID_SAMPLE_COUNT"):
            sampling.needs_forecast_confirmation({"total_selected": count}, RULES)


def test_threshold_rejects_invalid_configuration():
    import pytest
    for threshold in (-1, False, "5"):
        with pytest.raises(ValueError, match="INVALID_CONFIRMATION_THRESHOLD"):
            sampling.needs_forecast_confirmation(
                {"total_selected": 7},
                {**RULES, "forecast_confirmation_max_samples": threshold},
            )
