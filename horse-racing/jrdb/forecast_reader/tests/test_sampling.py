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
    assert result["fallback_triggered"]
    assert len(result["stages"]) == 4
    assert all(isinstance(k, str) for k in result["exact_race_keys"])



def test_cumulative_ten_and_multiple_per_year():
    rows = [race(2024, "exact")]
    rows += [race(2020, f"s1{i}", name="別") for i in range(3)]
    rows += [race(2021, f"s2{i}", name="別", weight_rule="handicap") for i in range(3)]
    rows += [race(2022, f"s3{i}", name="別", weight_rule="handicap", eligibility="older") for i in range(3)]
    result = sampling.select(TARGET, rows, RULES)
    assert result["total_selected"] == 10
    assert result["sample_shortfall"] == 0
    assert [x["added_count"] for x in result["stages"]] == [3, 3, 3]


def test_s4_42_days_and_shortfall():
    rows = [race(2020, "a", name="別", date="2020-09-25"),
            race(2021, "b", name="別", date="2021-09-25", weight_rule="handicap"),
            race(2022, "c", name="別", date="2022-09-25", eligibility="older", weight_rule="handicap"),
            race(2023, "outside", name="別", date="2023-08-30")]
    result = sampling.select(TARGET, rows, RULES)
    assert result["selected_stage"] == "S4"
    assert result["supplement_race_keys"] == ["a", "b", "c"]
    assert result["sample_shortfall"] == 7


@pytest.mark.parametrize("field,value", [("venue","阪神"), ("surface","ダート"),
                                         ("distance",2800), ("course","inner"),
                                         ("race_class","G2")])
def test_core_conditions_remain_fixed(field, value):
    result = sampling.select(TARGET, [race(2020, "x", name="別", **{field:value})], RULES)
    assert not result["supplement_race_keys"]
    assert result["sample_shortfall"] == 10


def test_unknown_duplicate_and_leap():
    with pytest.raises(ValueError, match="DUPLICATE"):
        sampling.select(TARGET, [race(2020,"x"), race(2021,"x")], RULES)
    assert not sampling.select(TARGET, [race(2020,"x",name="別",eligibility=None)], RULES)["supplement_race_keys"]
    assert sampling.seasonal_distance(date(2024,12,31),date(2020,1,1)) == 1
    assert sampling.seasonal_distance(date(2024,2,29),date(2023,3,1)) == 1
