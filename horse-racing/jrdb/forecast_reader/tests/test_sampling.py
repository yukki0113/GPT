import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sampling", ROOT / "src/sampling.py")
sampling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sampling)
RULES = json.loads((ROOT / "config/sampling_rules_v1.json").read_text())
TARGET = dict(date="2026-10-25", name="菊花賞", venue="京都", surface="芝",
              distance=3000, race_class="G1", eligibility="3yo", course="outer", weight_rule="fixed")


def race(year, key, **overrides):
    return {**TARGET, "date": f"{year}-10-25", "race_key": key, **overrides}


def test_kyoto_eight_hanshin_two():
    races = [race(y, str(y), venue="阪神" if y in (2021, 2022) else "京都") for y in range(2016, 2026)]
    result = sampling.select(TARGET, races, RULES)
    assert result["exact_count"] == 8
    assert not result["fallback_triggered"]
    assert result["stages"] == []
    assert all(isinstance(k, str) for k in result["exact_race_keys"])


def test_threshold_and_stage_stops():
    exact = [race(y, str(y)) for y in range(2016, 2021)]
    other = race(2024, "other", name="別競走")
    assert sampling.select(TARGET, exact + [other], RULES)["selected_stage"] is None
    result = sampling.select(TARGET, exact[:4] + [other], RULES)
    assert result["selected_stage"] == "S1"
    assert [s["stage"] for s in result["stages"]] == ["S1"]


def test_s2_and_no_relaxation_of_core():
    result = sampling.select(TARGET, [race(2020, "a", name="別", date="2020-09-25"),
                                      race(2021, "b", name="別", venue="阪神")], RULES)
    assert result["selected_stage"] == "S2"
    assert result["supplement_race_keys"] == ["a"]
    assert sampling.select(TARGET, [race(2021, "b", venue="阪神")], RULES)["failure_code"] == "NO_ACCEPTABLE_SUPPLEMENT"


def test_one_per_year_and_leap_day():
    result = sampling.select(TARGET, [race(2020, "b", name="別"), race(2020, "a", name="別")], RULES)
    assert result["supplement_race_keys"] == ["a"]
    assert sampling.seasonal_distance(date(2024, 12, 31), date(2020, 1, 1)) == 1
    assert sampling.seasonal_distance(date(2024, 2, 29), date(2023, 3, 1)) == 1


def test_unknown_and_duplicate_never_match():
    with pytest.raises(ValueError, match="DUPLICATE"):
        sampling.select(TARGET, [race(2020, "x"), race(2021, "x")], RULES)
    result = sampling.select(TARGET, [race(2020, "x", race_class=None)], RULES)
    assert result["exact_count"] == 0
    assert result["failure_code"] == "NO_ACCEPTABLE_SUPPLEMENT"


def test_s3_and_optional_multiple_per_year():
    rows = [race(2020, "a", name="別", course="inner"),
            race(2020, "b", name="別", course="inner")]
    result = sampling.select(TARGET, rows, {**RULES, "supplement_per_year": 0})
    assert result["selected_stage"] == "S3"
    assert result["supplement_race_keys"] == ["a", "b"]


def test_date_windows_and_target_year_exclusion():
    rows = [race(2015, "old"), race(2026, "current"),
            race(2020, "in", name="別", date="2020-10-04"),
            race(2021, "out", name="別", date="2021-10-03")]
    result = sampling.select(TARGET, rows, RULES)
    assert result["exact_count"] == 0
    assert result["supplement_race_keys"] == ["in"]
